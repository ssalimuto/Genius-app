#!/usr/bin/env python3
"""
Safe MT5 Bot v2 - multi-strategy bot for a Pocket Option MT5 account via MetaApi REST.

Modes (pick with "mode" in config.json or --mode NAME):
  trend    EMA200 trend + N-bar breakout, ATR stop and ATR target.
  meanrev  Pullback in the EMA200 trend: RSI(2) oversold/overbought OR close outside the
           Bollinger band (20, 2). Exit when price closes back over the 5-bar average,
           after a time limit, or at the ATR stop.
  grid     SAFE capped grid/DCA in the EMA200 trend: starts on an RSI(2) pullback, adds at
           most max_levels-1 more entries, every level the SAME lot (never martingale),
           one hard basket stop for all levels (sent to the broker on every order),
           basket target = average entry + tp_atr * ATR. Whole basket risk <= 1%.
  auto     Regime filter: ADX(14) >= adx_th -> trend rules, ADX < adx_th -> meanrev rules.

Risk guards (all modes): 1% risk per trade (for grid: per whole basket), skip if the
0.01-lot minimum would risk more than 3%, 3% daily loss limit, 15% drawdown kill switch,
max 3 orders a day, STOP / STOP.txt file kill switch, dry run by default, live orders
only with --live AND "i_accept_risk": true AND the mode passed walk-forward for that symbol.

Usage:
  python safe_mt5_bot.py backtest            # walk-forward test of every mode (1h + daily)
  python safe_mt5_bot.py status              # phone-friendly: balance, positions, today's P/L, allowed?
  python safe_mt5_bot.py check               # raw account info, no trades
  python safe_mt5_bot.py run                 # dry run with the config mode
  python safe_mt5_bot.py run --mode meanrev  # dry run with another mode
  python safe_mt5_bot.py run --live          # real orders (only if every guard allows)
  python safe_mt5_bot.py once                # one check then exit (cloud runner); BOT_QUIET=1 hides details

Token: environment variable METAAPI_TOKEN (never in the code or config).
No guarantee of profit. Trading can lose all the money in the account.
"""
import json, math, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ("trend", "meanrev", "grid", "auto")
TAG = "safe_mt5_bot"

DEFAULT_PARAMS = {
    "trend":   {"ema": 200, "breakout": 20, "atr": 14, "sl_atr": 2.0, "tp_atr": 3.0},
    "meanrev": {"ema": 200, "atr": 14, "rsi_lo": 10, "bb_k": 2.0, "sl_atr": 2.5, "tp_atr": 3.0, "max_bars": 24},
    "grid":    {"ema": 200, "atr": 14, "rsi_lo": 10, "spacing_atr": 1.0, "max_levels": 3, "tp_atr": 0.5, "max_bars": 72},
    "auto":    {"ema": 200, "atr": 14, "adx_th": 25, "breakout": 20, "sl_atr": 2.0, "tp_atr": 3.0,
                "rsi_lo": 10, "bb_k": 2.0, "mr_sl_atr": 2.5, "max_bars": 24},
}

DEFAULT_CONFIG = {
    "metaapi_token_env": "METAAPI_TOKEN",
    "metaapi_account_id": "",
    "region": "new-york",
    "symbols": ["EURUSD"],
    "timeframe": "1h",
    "mode": "trend",
    "risk_per_trade_pct": 1.0,
    "max_risk_per_trade_pct": 3.0,
    "daily_loss_limit_pct": 3.0,
    "max_drawdown_pct": 15.0,
    "max_trades_per_day": 3,
    "params": DEFAULT_PARAMS,
    "spread_pips": {"EURUSD": 1.2, "GBPUSD": 1.6, "USDJPY": 1.4},
    "slippage_pips": 0.3,
    "i_accept_risk": False,
    "poll_seconds": 60,
}

# ---------------------------------------------------------------- indicators
def ema(values, n):
    out, k, e = [], 2 / (n + 1), None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(e)
    return out

def sma(values, n):
    out, s = [], 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(s / min(i + 1, n))
    return out

def stdev(values, n):
    out = []
    for i in range(len(values)):
        w = values[max(0, i - n + 1):i + 1]
        m = sum(w) / len(w)
        out.append(math.sqrt(sum((x - m) ** 2 for x in w) / len(w)))
    return out

def atr(highs, lows, closes, n):
    out, a = [], None
    for i in range(len(closes)):
        pc = closes[i - 1] if i else closes[i]
        tr = max(highs[i] - lows[i], abs(highs[i] - pc), abs(lows[i] - pc))
        a = tr if a is None else (a * (n - 1) + tr) / n
        out.append(a)
    return out

def rsi(closes, n=2):
    out, up, dn = [50.0], None, None
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        u, d = max(ch, 0), max(-ch, 0)
        up = u if up is None else (up * (n - 1) + u) / n
        dn = d if dn is None else (dn * (n - 1) + d) / n
        out.append(100.0 if dn == 0 else 100 - 100 / (1 + up / dn))
    return out

def adx(highs, lows, closes, n=14):
    out = [0.0]; tr_s = pdm_s = mdm_s = None; a = None
    for i in range(1, len(closes)):
        upm, dnm = highs[i] - highs[i - 1], lows[i - 1] - lows[i]
        pdm = upm if upm > dnm and upm > 0 else 0.0
        mdm = dnm if dnm > upm and dnm > 0 else 0.0
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        if tr_s is None:
            tr_s, pdm_s, mdm_s = tr, pdm, mdm
        else:
            tr_s = tr_s - tr_s / n + tr; pdm_s = pdm_s - pdm_s / n + pdm; mdm_s = mdm_s - mdm_s / n + mdm
        pdi = 100 * pdm_s / tr_s if tr_s else 0; mdi = 100 * mdm_s / tr_s if tr_s else 0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if pdi + mdi else 0
        a = dx if a is None else (a * (n - 1) + dx) / n
        out.append(a)
    return out

def indicators(bars, p):
    c = [b["c"] for b in bars]; h = [b["h"] for b in bars]; l = [b["l"] for b in bars]
    k = p.get("bb_k", 2.0); mid = sma(c, 20); sd = stdev(c, 20)
    return {"c": c, "h": h, "l": l, "E": ema(c, p.get("ema", 200)), "A": atr(h, l, c, p.get("atr", 14)),
            "R": rsi(c, 2), "S5": sma(c, 5), "BBU": [m + k * s for m, s in zip(mid, sd)],
            "BBL": [m - k * s for m, s in zip(mid, sd)], "ADX": adx(h, l, c, 14)}

WARMUP = 210

def pip_size(symbol):
    return 0.01 if "JPY" in symbol.upper() else 0.0001

def pip_value_per_lot(symbol, price):
    # USD value of 1 pip for 1.00 lot (100,000 units), USD account
    s = symbol.upper()[:6]
    if s.endswith("USD"):
        return 10.0
    if s.startswith("USD"):
        return 100000 * pip_size(s) / price
    return 10.0

# ---------------------------------------------------------------- strategy signals
# A signal is evaluated on CLOSED bar i and returns a dict or None:
#   {"side", "kind": "trend"|"mr"|"grid", "sl_d", "tp_d"}
def _trend_sig(I, i, p):
    c, E, h, l = I["c"], I["E"], I["h"], I["l"]; n = p["breakout"]
    if i < n + 5:
        return None
    hi = max(h[i - n:i]); lo = min(l[i - n:i]); a = I["A"][i]
    if c[i] > E[i] and E[i] > E[i - 4] and c[i] > hi:
        return {"side": "buy", "kind": "trend", "sl_d": p["sl_atr"] * a, "tp_d": p["tp_atr"] * a}
    if c[i] < E[i] and E[i] < E[i - 4] and c[i] < lo:
        return {"side": "sell", "kind": "trend", "sl_d": p["sl_atr"] * a, "tp_d": p["tp_atr"] * a}
    return None

def _mr_sig(I, i, p, sl_key="sl_atr"):
    c, E, R = I["c"], I["E"], I["R"]; a = I["A"][i]; lo = p["rsi_lo"]
    sl_d, tp_d = p[sl_key] * a, p.get("tp_atr", 3.0) * a
    if c[i] > E[i] and E[i] > E[i - 4] and (R[i] < lo or c[i] < I["BBL"][i]):
        return {"side": "buy", "kind": "mr", "sl_d": sl_d, "tp_d": tp_d}
    if c[i] < E[i] and E[i] < E[i - 4] and (R[i] > 100 - lo or c[i] > I["BBU"][i]):
        return {"side": "sell", "kind": "mr", "sl_d": sl_d, "tp_d": tp_d}
    return None

def _grid_sig(I, i, p):
    c, E, R = I["c"], I["E"], I["R"]; lo = p["rsi_lo"]
    if c[i] > E[i] and E[i] > E[i - 4] and R[i] < lo:
        side = "buy"
    elif c[i] < E[i] and E[i] < E[i - 4] and R[i] > 100 - lo:
        side = "sell"
    else:
        return None
    sp = p["spacing_atr"] * I["A"][i]; L = p["max_levels"]
    return {"side": side, "kind": "grid", "spacing": sp, "sl_d": sp * L, "tp_d": p["tp_atr"] * I["A"][i]}

def entry_signal(mode, I, i, p):
    if mode == "trend":
        return _trend_sig(I, i, p)
    if mode == "meanrev":
        return _mr_sig(I, i, p)
    if mode == "grid":
        return _grid_sig(I, i, p)
    if mode == "auto":
        if I["ADX"][i] >= p["adx_th"]:
            return _trend_sig(I, i, p)
        return _mr_sig(I, i, p, "mr_sl_atr")
    raise ValueError(mode)

def mr_exit_now(I, i, side, bars_held, p):
    """Mean-reversion discretionary exit on closed bar i."""
    if bars_held >= p["max_bars"]:
        return True
    return I["c"][i] > I["S5"][i] if side == "buy" else I["c"][i] < I["S5"][i]

def lot_size(balance, risk_pct, max_risk_pct, stop_pips, pv):
    """Returns (lots, actual_risk_usd) or (0, reason) when trade must be skipped.
    stop_pips may be the SUM of stop distances of all grid levels (basket worst case)."""
    want = balance * risk_pct / 100
    per_001 = stop_pips * pv * 0.01
    if per_001 <= 0:
        return 0, "bad stop"
    lots = math.floor(want / per_001 + 1e-9) * 0.01
    if lots < 0.01:
        if per_001 <= balance * max_risk_pct / 100:
            lots = 0.01
        else:
            return 0, f"min lot 0.01 risks ${per_001:.2f} = {per_001 / balance * 100:.0f}% of balance (limit {max_risk_pct}%)"
    return round(lots, 2), round(lots / 0.01 * per_001, 2)

def grid_risk_pips(sig, ps):
    """Worst case if every level fills and the hard stop is hit: spacing * L(L+1)/2."""
    L = round(sig["sl_d"] / sig["spacing"])
    return sig["spacing"] * L * (L + 1) / 2 / ps

# ---------------------------------------------------------------- backtest
def load_yahoo(path):
    d = json.load(open(path))["chart"]["result"][0]
    q = d["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(d["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c})
    return bars

def backtest(bars, symbol, mode, p, cfg, start=WARMUP, start_balance=1000.0):
    """Trades only from bar index `start` (earlier bars are indicator warm-up).
    Costs: spread + slippage paid once per order (at entry). Stops fill at the worse of
    stop price and bar open (gaps). Stop is checked before target (pessimistic)."""
    ps = pip_size(symbol)
    cost = (cfg["spread_pips"].get(symbol, 1.5) + cfg["slippage_pips"]) * ps
    I = indicators(bars, p); c = I["c"]
    bal = peak = start_balance; maxdd = 0.0; trades = []
    pos = None   # {"side","kind","fills":[(price,lots)],"pv","sl","tp","opened","spacing"}
    day, day_start, day_trades = None, bal, 0
    start = max(start, WARMUP)

    def pnl_at(px):
        sgn = 1 if pos["side"] == "buy" else -1
        return sum(sgn * (px - e) / ps * pos["pv"] * lots for e, lots in pos["fills"])

    for i in range(start, len(bars)):
        b = bars[i]
        d = datetime.fromtimestamp(b["t"], timezone.utc).date()
        eq_open = bal + (pnl_at(b["o"]) if pos else 0)
        if d != day:
            day, day_start, day_trades = d, eq_open, 0
        closed_now = False
        if pos:  # intrabar stop / target, stop first
            hit = None; buy = pos["side"] == "buy"
            if buy and b["l"] <= pos["sl"]: hit = min(b["o"], pos["sl"])
            elif not buy and b["h"] >= pos["sl"]: hit = max(b["o"], pos["sl"])
            elif buy and b["h"] >= pos["tp"]: hit = max(b["o"], pos["tp"]) if b["o"] >= pos["tp"] else pos["tp"]
            elif not buy and b["l"] <= pos["tp"]: hit = min(b["o"], pos["tp"]) if b["o"] <= pos["tp"] else pos["tp"]
            if hit is None and pos["kind"] in ("mr", "grid"):
                held = i - pos["opened"]
                if pos["kind"] == "mr" and mr_exit_now(I, i, pos["side"], held, p):
                    hit = c[i]
                elif pos["kind"] == "grid" and held >= p["max_bars"]:
                    hit = c[i]
            if hit is not None:
                r = pnl_at(hit); bal += r; trades.append(r); pos = None; closed_now = True
        if pos and pos["kind"] == "grid" and len(pos["fills"]) < p["max_levels"]:
            first = pos["fills"][0][0]; n = len(pos["fills"]); sgn = 1 if pos["side"] == "buy" else -1
            level = first - sgn * n * pos["spacing"]
            if (c[i] - level) * sgn <= 0 and day_trades < cfg["max_trades_per_day"] \
                    and (day_start - (bal + pnl_at(c[i]))) / day_start * 100 < cfg["daily_loss_limit_pct"]:
                e = c[i] + sgn * cost
                pos["fills"].append((e, pos["fills"][0][1])); day_trades += 1   # same lot: no martingale
                avg = sum(x for x, _ in pos["fills"]) / len(pos["fills"])
                pos["tp"] = avg + sgn * pos["tp_d"]
        eq = bal + (pnl_at(c[i]) if pos else 0)
        peak = max(peak, eq); dd = (peak - eq) / peak * 100; maxdd = max(maxdd, dd)
        if dd >= cfg["max_drawdown_pct"]:   # kill switch: flatten and stop for good
            if pos:
                r = pnl_at(c[i]); bal += r; trades.append(r); pos = None
            break
        if pos or closed_now:
            continue
        if (day_start - bal) / day_start * 100 >= cfg["daily_loss_limit_pct"]: continue
        if day_trades >= cfg["max_trades_per_day"]: continue
        sig = entry_signal(mode, I, i, p)
        if not sig: continue
        side = sig["side"]; sgn = 1 if side == "buy" else -1
        entry = c[i] + sgn * cost; pv = pip_value_per_lot(symbol, c[i])
        risk_pips = grid_risk_pips(sig, ps) if sig["kind"] == "grid" else sig["sl_d"] / ps
        lots, _ = lot_size(bal, cfg["risk_per_trade_pct"], cfg["max_risk_per_trade_pct"], risk_pips, pv)
        if not lots: continue
        pos = {"side": side, "kind": sig["kind"], "fills": [(entry, lots)], "pv": pv, "opened": i,
               "sl": entry - sgn * sig["sl_d"], "tp": entry + sgn * sig["tp_d"],
               "tp_d": sig["tp_d"], "spacing": sig.get("spacing")}
        day_trades += 1
    if pos:
        r = pnl_at(c[-1]); bal += r; trades.append(r)
    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) else (99.0 if wins else 0.0)
    return {"trades": len(trades), "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "profit_factor": round(pf, 2), "return_pct": round((bal - start_balance) / start_balance * 100, 1),
            "max_dd_pct": round(maxdd, 1)}

def param_grid(mode):
    """Deliberately small grids (4-8 settings) to limit overfitting."""
    if mode == "trend":
        return [{"ema": 200, "atr": 14, "breakout": b, "sl_atr": s, "tp_atr": t}
                for b in (20, 40) for s in (1.5, 2.0) for t in (2.0, 3.0)]
    if mode == "meanrev":
        return [{"ema": 200, "atr": 14, "bb_k": 2.0, "tp_atr": 3.0, "rsi_lo": r, "sl_atr": s, "max_bars": m}
                for r in (5, 10) for s in (1.5, 2.5) for m in (12, 24)]
    if mode == "grid":
        return [{"ema": 200, "atr": 14, "rsi_lo": 10, "max_levels": 3, "max_bars": 72, "spacing_atr": s, "tp_atr": t}
                for s in (0.75, 1.25) for t in (0.5, 1.0)]
    if mode == "auto":
        return [{"ema": 200, "atr": 14, "breakout": 20, "tp_atr": 3.0, "bb_k": 2.0, "max_bars": 24,
                 "adx_th": a, "sl_atr": s, "rsi_lo": r, "mr_sl_atr": 2.5}
                for a in (20, 25) for s in (1.5, 2.0) for r in (5, 10)]
    raise ValueError(mode)

def passes(r):
    return r["profit_factor"] > 1.2 and r["return_pct"] > 0 and r["max_dd_pct"] < 15 and r["trades"] >= 20

def walk_forward(cfg, frames=(("1h", "{}.json"), ("1d", "{}_1d.json")), symbols=("EURUSD", "GBPUSD", "USDJPY")):
    rows = []
    for tf, pattern in frames:
        for sym in symbols:
            path = os.path.join(HERE, pattern.format(sym))
            if not os.path.exists(path):
                continue
            bars = load_yahoo(path); cut = int(len(bars) * 0.7)
            for mode in MODES:
                best, best_p = None, None
                for p in param_grid(mode):
                    r = backtest(bars[:cut], sym, mode, p, cfg)
                    if r["trades"] >= 30 and (best is None or r["profit_factor"] > best["profit_factor"]):
                        best, best_p = r, p
                if not best_p:
                    rows.append({"tf": tf, "symbol": sym, "mode": mode, "params": None, "in_sample": None,
                                 "oos": None, "pass": False, "note": "under 30 trades on old data"})
                    continue
                oos = backtest(bars, sym, mode, best_p, cfg, start=cut)   # earlier bars = warm-up only
                rows.append({"tf": tf, "symbol": sym, "mode": mode, "params": best_p, "in_sample": best,
                             "oos": oos, "pass": passes(oos)})
    return rows

def run_backtest(cfg):
    print("Walk-forward: settings picked on OLD 70%, judged on UNSEEN newest 30%.")
    print("Costs: spread + %.1f pip slippage per order. Swap not included.\n" % cfg["slippage_pips"])
    rows = walk_forward(cfg)
    print(f"{'tf':3} {'mode':8} {'pair':7} {'PF':>5} {'ret%':>6} {'maxDD%':>6} {'trades':>6}  verdict")
    for r in rows:
        o = r["oos"]
        if not o:
            print(f"{r['tf']:3} {r['mode']:8} {r['symbol']:7}   n/a  {r['note']}"); continue
        print(f"{r['tf']:3} {r['mode']:8} {r['symbol']:7} {o['profit_factor']:5.2f} {o['return_pct']:6.1f} "
              f"{o['max_dd_pct']:6.1f} {o['trades']:6}  {'PASS' if r['pass'] else 'FAIL'}")
    json.dump(rows, open(os.path.join(HERE, "wf_results.json"), "w"), indent=1)
    print("\nSaved wf_results.json (the live loop only trades mode+symbol pairs that PASSED here).")
    return rows

def validated(cfg, mode, sym):
    """Params for mode/symbol if that combination passed walk-forward on the config timeframe."""
    path = os.path.join(HERE, "wf_results.json")
    if not os.path.exists(path):
        return None
    tf = "1d" if cfg["timeframe"] in ("1d", "D1") else "1h"
    for r in json.load(open(path)):
        if r["mode"] == mode and r["symbol"] == sym.split(".")[0][:6] and r["tf"] == tf and r["pass"]:
            return r["params"]
    return None

# ---------------------------------------------------------------- MetaApi REST
class MetaApi:
    def __init__(self, cfg):
        self.token = os.environ.get(cfg["metaapi_token_env"], "")
        self.acc = cfg["metaapi_account_id"] or os.environ.get("METAAPI_ACCOUNT_ID", ""); r = os.environ.get("METAAPI_REGION") or cfg["region"]
        if not self.token or not self.acc:
            sys.exit("Set the METAAPI_TOKEN environment variable and metaapi_account_id in config.json first.")
        self.client = f"https://mt-client-api-v1.{r}.agiliumtrade.ai/users/current/accounts/{self.acc}"
        self.market = f"https://mt-market-data-client-api-v1.{r}.agiliumtrade.ai/users/current/accounts/{self.acc}"

    def _req(self, url, method="GET", body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"auth-token": self.token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MetaApi {e.code}: {e.read()[:200].decode(errors='ignore')}")

    def account(self):   return self._req(self.client + "/account-information")
    def positions(self): return self._req(self.client + "/positions") or []
    def deals(self, start, end):
        f = "%Y-%m-%dT%H:%M:%S.000Z"
        return self._req(f"{self.client}/history-deals/time/{start.strftime(f)}/{end.strftime(f)}") or []
    def candles(self, sym, tf, n=300):
        return self._req(f"{self.market}/historical-market-data/symbols/{sym}/timeframes/{tf}/candles?limit={n}")
    def order(self, sym, side, lots, sl, tp, comment=TAG):
        body = {"actionType": "ORDER_TYPE_BUY" if side == "buy" else "ORDER_TYPE_SELL",
                "symbol": sym, "volume": lots, "stopLoss": sl, "comment": comment[:26]}
        if tp is not None:
            body["takeProfit"] = tp
        return self._req(self.client + "/trade", "POST", body)
    def close(self, position_id):
        return self._req(self.client + "/trade", "POST", {"actionType": "POSITION_CLOSE_ID", "positionId": position_id})
    def modify(self, position_id, sl, tp):
        return self._req(self.client + "/trade", "POST", {"actionType": "POSITION_MODIFY", "positionId": position_id,
                                                         "stopLoss": sl, "takeProfit": tp})

# ---------------------------------------------------------------- state + guards
STATE_PATH = os.environ.get("BOT_STATE_PATH") or os.path.join(HERE, "state.json")

def load_state():
    try:
        return json.load(open(STATE_PATH))
    except Exception:
        return {}

def save_state(st):
    json.dump(st, open(STATE_PATH, "w"), indent=1)

def stop_file():
    return os.path.exists(os.path.join(HERE, "STOP")) or os.path.exists(os.path.join(HERE, "STOP.txt"))

def update_day(st, eq):
    today = datetime.now(timezone.utc).date().isoformat()
    st["peak"] = max(st.get("peak", eq), eq)
    if st.get("day") != today:
        st.update({"day": today, "day_start": eq, "day_trades": 0})
    return st

def guard_reasons(cfg, st, eq, live):
    """Reasons trading is NOT allowed right now (empty list = allowed)."""
    why = []
    if stop_file(): why.append("STOP file present")
    dd = (st["peak"] - eq) / st["peak"] * 100 if st.get("peak") else 0
    if dd >= cfg["max_drawdown_pct"]: why.append(f"kill switch: drawdown {dd:.1f}% >= {cfg['max_drawdown_pct']}%")
    dl = (st["day_start"] - eq) / st["day_start"] * 100 if st.get("day_start") else 0
    if dl >= cfg["daily_loss_limit_pct"]: why.append(f"daily loss {dl:.1f}% >= {cfg['daily_loss_limit_pct']}%")
    if st.get("day_trades", 0) >= cfg["max_trades_per_day"]: why.append("max trades for today reached")
    if live and not cfg["i_accept_risk"]: why.append('"i_accept_risk" is false')
    return why

QUIET = os.environ.get("BOT_QUIET") == "1"   # cloud runner: public logs show only ran / signal / skipped

def log(msg, kind="info"):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {msg}"
    if QUIET:
        if kind != "info":
            print(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC  {kind}")
        return
    print(line)
    with open(os.path.join(HERE, "bot_log.txt"), "a") as f:
        f.write(line + "\n")

def get_bars(api, sym, tf, n=400):
    raw = api.candles(sym, tf, n) or []
    return [{"o": b["open"], "h": b["high"], "l": b["low"], "c": b["close"], "t": b["time"]} for b in raw][:-1]

# ---------------------------------------------------------------- status (phone friendly)
def status(cfg):
    api = MetaApi(cfg); info = api.account(); st = update_day(load_state(), info["equity"]); cur = info.get("currency", "")
    now = datetime.now(timezone.utc); midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    realized = 0.0
    try:
        for d in api.deals(midnight, now):
            realized += d.get("profit", 0) + d.get("commission", 0) + d.get("swap", 0)
    except Exception as e:
        realized = None; print("(could not read today's deals:", e, ")")
    pos = api.positions(); floating = sum(p.get("profit", 0) for p in pos)
    print(f"Balance {info['balance']:.2f} {cur} | Equity {info['equity']:.2f}")
    print(f"Today P/L: closed {'?' if realized is None else f'{realized:+.2f}'} | open {floating:+.2f}")
    print(f"Open positions: {len(pos)}")
    for p in pos:
        side = "BUY" if "BUY" in p.get("type", "") else "SELL"
        print(f"  {p['symbol']} {side} {p['volume']} @ {p['openPrice']}  P/L {p.get('profit', 0):+.2f}")
    mode = cfg["mode"]; why = guard_reasons(cfg, st, info["equity"], live=True)
    for sym in cfg["symbols"]:
        p = validated(cfg, mode, sym)
        if not p:
            why.append(f"{mode} has not passed walk-forward on {sym}"); continue
        try:
            bars = get_bars(api, sym, cfg["timeframe"]); I = indicators(bars, p); a = I["A"][-1]
            sl_d = (grid_risk_pips({"spacing": p["spacing_atr"] * a, "sl_d": p["spacing_atr"] * a * p["max_levels"]},
                                   pip_size(sym)) * pip_size(sym)) if mode == "grid" else p.get("sl_atr", 2.0) * a
            lots, r = lot_size(info["balance"], cfg["risk_per_trade_pct"], cfg["max_risk_per_trade_pct"],
                               sl_d / pip_size(sym), pip_value_per_lot(sym, bars[-1]["c"]))
            if not lots: why.append(f"{sym}: {r}")
        except Exception as e:
            why.append(f"{sym}: could not check lot size ({e})")
    print(f"Mode: {mode} | Trades today: {st.get('day_trades', 0)}/{cfg['max_trades_per_day']}")
    print("Trading allowed: YES" if not why else "Trading allowed: NO")
    for w in why:
        print("  - " + w)

# ---------------------------------------------------------------- live loop
def run(cfg, live, mode):
    if live and not cfg["i_accept_risk"]:
        sys.exit('Live mode refused: set "i_accept_risk": true in config.json after a PASS backtest and 2+ weeks on demo.')
    params = {}
    for sym in cfg["symbols"]:
        p = validated(cfg, mode, sym)
        if p is None:
            if live:
                sys.exit(f"Live mode refused: mode '{mode}' did not pass walk-forward on {sym}. Run backtest first.")
            p = cfg["params"].get(mode, DEFAULT_PARAMS[mode])
        params[sym] = p
    api = MetaApi(cfg); info = api.account(); st = update_day(load_state(), info["equity"]); save_state(st)
    last_bar = {}
    log(f"Started ({'LIVE' if live else 'DRY RUN'}) mode={mode}. Balance {info['balance']} {info.get('currency', '')}")
    while True:
        if stop_file():
            log("STOP file found. Bot stopped."); return
        try:
            info = api.account(); eq = info["equity"]; st = update_day(st, eq); save_state(st)
            dd = (st["peak"] - eq) / st["peak"] * 100
            if dd >= cfg["max_drawdown_pct"]:
                log(f"KILL SWITCH: drawdown {dd:.1f}% from peak. Bot stopped."); return
            mine = [x for x in api.positions() if str(x.get("comment", "")).startswith(TAG)]
            for sym in cfg["symbols"]:
                p = params[sym]
                bars = get_bars(api, sym, cfg["timeframe"])
                if len(bars) < WARMUP or last_bar.get(sym) == bars[-1]["t"]:
                    continue
                last_bar[sym] = bars[-1]["t"]
                I = indicators(bars, p); i = len(bars) - 1; price = bars[-1]["c"]
                ps = pip_size(sym); pv = pip_value_per_lot(sym, price)
                held_pos = [x for x in mine if x["symbol"] == sym]
                blocked = guard_reasons(cfg, st, eq, live)
                if held_pos:
                    manage(api, cfg, st, live, sym, held_pos, I, i, p, bars, blocked)
                    continue
                if blocked:
                    continue
                sig = entry_signal(mode, I, i, p)
                if not sig:
                    continue
                side = sig["side"]; sgn = 1 if side == "buy" else -1
                risk_pips = grid_risk_pips(sig, ps) if sig["kind"] == "grid" else sig["sl_d"] / ps
                lots, risk = lot_size(info["balance"], cfg["risk_per_trade_pct"], cfg["max_risk_per_trade_pct"], risk_pips, pv)
                if not lots:
                    log(f"{sym} {side} {sig['kind']} signal SKIPPED: {risk}"); continue
                sl = round(price - sgn * sig["sl_d"], 5); tp = round(price + sgn * sig["tp_d"], 5)
                comment = f"{TAG}:{sig['kind']}"
                if sig["kind"] == "grid":
                    st.setdefault("grid", {})[sym] = {"first": price, "spacing": sig["spacing"], "sl": sl,
                                                      "tp_d": sig["tp_d"], "levels": 1, "side": side}
                if live:
                    r = api.order(sym, side, lots, sl, tp, comment)
                    log(f"{sym} {side.upper()} {sig['kind']} {lots} lots SL {sl} TP {tp} risk ${risk} -> {r}")
                else:
                    log(f"[dry run] would {side.upper()} {sym} ({sig['kind']}) {lots} lots SL {sl} TP {tp} risk ${risk}")
                st["day_trades"] += 1; save_state(st)
        except Exception as e:
            log(f"Error (will retry): {e}")
        time.sleep(cfg["poll_seconds"])

def manage(api, cfg, st, live, sym, held, I, i, p, bars, blocked):
    """Exits for meanrev / grid positions and capped grid adds. Trend uses broker SL/TP only."""
    kind = str(held[0].get("comment", "")).split(":")[-1]
    side = "buy" if "BUY" in held[0].get("type", "") else "sell"; sgn = 1 if side == "buy" else -1
    opened = min(datetime.fromisoformat(str(x["time"]).replace("Z", "+00:00")) for x in held)
    tf_sec = 86400 if cfg["timeframe"] in ("1d", "D1") else 3600
    held_bars = int((datetime.now(timezone.utc) - opened) / timedelta(seconds=tf_sec))
    exit_now = (kind == "mr" and mr_exit_now(I, i, side, held_bars, p)) or \
               (kind == "grid" and held_bars >= p.get("max_bars", 72))
    if exit_now:
        for x in held:
            if live: api.close(x["id"])
            log(f"{'' if live else '[dry run] would '}close {sym} {kind} position {x['id']}", "exit" + ("" if live else " (dry run)"))
        st.get("grid", {}).pop(sym, None); save_state(st); return
    g = st.get("grid", {}).get(sym)
    if kind != "grid" or not g or blocked or g["levels"] >= p["max_levels"]:
        return
    level = g["first"] - sgn * g["levels"] * g["spacing"]; price = I["c"][i]
    if (price - level) * sgn > 0:
        return
    lots = held[0]["volume"]   # SAME lot as level 1: never martingale
    entries = [x["openPrice"] for x in held] + [price]
    tp = round(sum(entries) / len(entries) + sgn * g["tp_d"], 5)
    if live:
        api.order(sym, side, lots, g["sl"], tp, f"{TAG}:grid")
        for x in held:
            api.modify(x["id"], g["sl"], tp)
    log(f"{'' if live else '[dry run] would '}add grid level {g['levels'] + 1}/{p['max_levels']} {sym} {side} "
        f"{lots} lots, basket stop {g['sl']}, basket TP {tp}", "grid add" + ("" if live else " (dry run)"))
    g["levels"] += 1; st["day_trades"] += 1; save_state(st)

# ---------------------------------------------------------------- news filter (safety filter, not an edge)
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_WINDOW_MIN = 60

def _ff_time(s):
    import re
    s = str(s or "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::\d{2})?([+-]\d{2}):?(\d{2})", s)
    if m:
        d, hh, mm, oh, om = m.groups(); h = int(hh)
    else:
        m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s*([AP]M).*?UTC([+-]\d{2}):?(\d{2})", s, re.I)
        if not m:
            return None
        d, hh, mm, ap, oh, om = m.groups(); h = int(hh) % 12 + (12 if ap.upper() == "PM" else 0)
    off = int(oh[1:]) * 60 + int(om); off = -off if oh.startswith("-") else off
    y, mo, da = map(int, d.split("-"))
    return datetime(y, mo, da, h, int(mm), tzinfo=timezone.utc) - timedelta(minutes=off)

def load_news(st):
    """Weekly high-impact calendar. Kept in state so a busy feed falls back to the last copy (max 8 days)."""
    try:
        req = urllib.request.Request(FF_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = json.loads(r.read())
        ev = [{"t": t.timestamp(), "cur": str(e.get("country", "")).upper()} for e in raw
              if e.get("impact") == "High" and (t := _ff_time(e.get("date")))]
        st["news"] = {"at": time.time(), "events": ev}
        return ev
    except Exception:
        n = st.get("news")
        if n and time.time() - n["at"] < 8 * 86400:
            return n["events"]
        return None

def news_blocked(sym, events, now=None):
    if events is None:
        return True        # calendar unknown: no new trades (safety)
    now = (now or datetime.now(timezone.utc)).timestamp()
    curs = (sym[:3].upper(), sym[3:6].upper())
    return any(e["cur"] in curs and abs(e["t"] - now) <= NEWS_WINDOW_MIN * 60 for e in events)

# ---------------------------------------------------------------- one pass (cloud runner)
def once(cfg, live, mode):
    """One check, then exit. Same guards as run(). Remembers the last closed bar per symbol in state."""
    if os.environ.get("BOT_STOP", "").lower() == "true" or stop_file():
        log("STOP set", "stopped"); return
    if not os.environ.get(cfg["metaapi_token_env"]) or not (cfg["metaapi_account_id"] or os.environ.get("METAAPI_ACCOUNT_ID")):
        log("no secrets", "skipped: secrets not set"); return
    if live and not cfg["i_accept_risk"]:
        live = False
    params = {}
    for sym in cfg["symbols"]:
        p = validated(cfg, mode, sym)
        if p is None:
            if live:
                log("not validated", "skipped: %s %s not walk-forward PASS, dry run" % (mode, sym)); live = False
            p = cfg["params"].get(mode, DEFAULT_PARAMS[mode])
        params[sym] = p
    api = MetaApi(cfg); info = api.account(); eq = info["equity"]
    st = update_day(load_state(), eq); news = load_news(st)
    log("ran", "ran (%s)" % ("live" if live else "dry run"))
    dd = (st["peak"] - eq) / st["peak"] * 100
    if dd >= cfg["max_drawdown_pct"]:
        save_state(st); log("kill switch", "stopped: kill switch"); return
    mine = [x for x in api.positions() if str(x.get("comment", "")).startswith(TAG)]
    st.setdefault("last_bar", {})
    for sym in cfg["symbols"]:
        p = params[sym]
        bars = get_bars(api, sym, cfg["timeframe"])
        if len(bars) < WARMUP:
            continue
        new_bar = st["last_bar"].get(sym) != bars[-1]["t"]
        st["last_bar"][sym] = bars[-1]["t"]
        I = indicators(bars, p); i = len(bars) - 1; price = bars[-1]["c"]
        ps, pv = pip_size(sym), pip_value_per_lot(sym, price)
        held = [x for x in mine if x["symbol"] == sym]
        blocked = guard_reasons(cfg, st, eq, live)
        if news_blocked(sym, news):
            blocked.append("news")
        if held:
            if new_bar:
                manage(api, cfg, st, live, sym, held, I, i, p, bars, blocked)
            continue
        if not new_bar:
            continue
        sig = entry_signal(mode, I, i, p)
        if not sig:
            log("no signal", "no signal"); continue
        if blocked:
            if "news" in blocked:
                st["last_bar"].pop(sym, None)     # look again after the news window
            log("blocked", "signal skipped: %s" % ("news window" if "news" in blocked else "risk guard")); continue
        side = sig["side"]; sgn = 1 if side == "buy" else -1
        risk_pips = grid_risk_pips(sig, ps) if sig["kind"] == "grid" else sig["sl_d"] / ps
        lots, risk = lot_size(info["balance"], cfg["risk_per_trade_pct"], cfg["max_risk_per_trade_pct"], risk_pips, pv)
        if not lots:
            log(f"{sym} skipped: {risk}", "signal skipped: 3% risk guard"); continue
        sl = round(price - sgn * sig["sl_d"], 5); tp = round(price + sgn * sig["tp_d"], 5)
        if sig["kind"] == "grid":
            st.setdefault("grid", {})[sym] = {"first": price, "spacing": sig["spacing"], "sl": sl,
                                              "tp_d": sig["tp_d"], "levels": 1, "side": side}
        if live:
            api.order(sym, side, lots, sl, tp, f"{TAG}:{sig['kind']}")
            log(f"{sym} {side} {lots}", "signal: live order sent")
        else:
            log(f"[dry run] would {side} {sym} {lots}", "signal: dry run (no order)")
        st["day_trades"] += 1
    save_state(st)

def load_config():
    path = os.path.join(HERE, "config.json")
    if not os.path.exists(path):
        json.dump(DEFAULT_CONFIG, open(path, "w"), indent=2)
    cfg = dict(DEFAULT_CONFIG); cfg.update(json.load(open(path)))
    if os.environ.get("BOT_ACCEPT_RISK") == "1":   # cloud runner: the repo variable LIVE=true is the owner's acceptance
        cfg["i_accept_risk"] = True
    if "trend" not in cfg["params"]:   # old v1 flat params -> trend params
        cfg["params"] = dict(DEFAULT_PARAMS, trend=dict(DEFAULT_PARAMS["trend"], **cfg["params"]))
    return cfg

if __name__ == "__main__":
    cfg = load_config(); cmd = sys.argv[1] if len(sys.argv) > 1 else "backtest"
    mode = sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else cfg["mode"]
    if mode not in MODES:
        sys.exit(f"Unknown mode '{mode}'. Choose one of {MODES}.")
    if cmd == "backtest":
        run_backtest(cfg)
    elif cmd == "status":
        status(cfg)
    elif cmd == "check":
        api = MetaApi(cfg); print(json.dumps(api.account(), indent=2)); print("Open positions:", api.positions())
    elif cmd == "run":
        run(cfg, "--live" in sys.argv, mode)
    elif cmd == "once":
        try:
            once(cfg, "--live" in sys.argv, mode)
        except Exception as e:
            log(f"error {e}", "error (details hidden in public logs)")
    else:
        print(__doc__)
