"""Ssalimuto Profits - trading logic (no screen code).

The strategy, lot sizing and risk guards are the same as the desktop Safe MT5 Bot.
Everything here runs on the phone. Your MetaApi token is only ever sent to MetaApi's own
API hosts (*.agiliumtrade.ai); public prices come from Yahoo Finance with no login.

No bot can promise no losses. Trading can lose all the money in an account.
Made by Ssali Muto.
"""
import base64
import hashlib
import hmac
import json
import math
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
MODES = ("trend", "meanrev", "grid", "auto")
PAIRS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "XAUUSD")
MAIN_PAIRS = ("EURUSD", "GBPUSD", "USDJPY")
YAHOO_SYMBOL = {"XAUUSD": "GC=F"}      # gold: Yahoo has no spot XAUUSD, the gold future is used for prices and tests
RATES = {"USDJPY": 150.0, "GBPUSD": 1.30, "EURUSD": 1.10}   # updated from live prices for cross-pair pip values
TAG = "safe_mt5_bot"          # same tag as the desktop/cloud bot, so they see each other's trades
LIVE_PHRASE = "I ACCEPT THE RISK"
NO_PROMISE = "No bot can promise no losses."
PRACTICE_START = 1000.0
TF_SECONDS = {"1d": 86400, "1h": 3600}

DEFAULT_PARAMS = {
    "trend":   {"ema": 200, "breakout": 20, "atr": 14, "sl_atr": 2.0, "tp_atr": 3.0},
    "meanrev": {"ema": 200, "atr": 14, "rsi_lo": 10, "bb_k": 2.0, "sl_atr": 2.5, "tp_atr": 3.0, "max_bars": 24},
    "grid":    {"ema": 200, "atr": 14, "rsi_lo": 10, "spacing_atr": 1.0, "max_levels": 3, "tp_atr": 0.5, "max_bars": 72},
    "auto":    {"ema": 200, "atr": 14, "adx_th": 25, "breakout": 20, "sl_atr": 2.0, "tp_atr": 3.0,
                "rsi_lo": 10, "bb_k": 2.0, "mr_sl_atr": 2.5, "max_bars": 24},
}

RISK = {
    "risk_per_trade_pct": 1.0,      # aim to risk 1% of the balance per trade
    "max_risk_per_trade_pct": 3.0,  # skip a trade if even 0.01 lot would risk more than 3%
    "daily_loss_limit_pct": 3.0,    # stop for the day after losing 3%
    "max_drawdown_pct": 15.0,       # kill switch: stop for good at 15% below the peak
    "max_trades_per_day": 3,
    "spread_pips": {"EURUSD": 1.2, "GBPUSD": 1.6, "USDJPY": 1.4, "AUDUSD": 1.4, "USDCAD": 1.8, "USDCHF": 1.7,
                    "NZDUSD": 1.9, "EURGBP": 1.5, "EURJPY": 2.0, "GBPJPY": 2.8, "XAUUSD": 30.0},
    "slippage_pips": 0.3,
}

MODE_NAMES = {"trend": "Trend", "meanrev": "Mean reversion", "grid": "Safe grid", "auto": "Auto (ADX)"}


# ---------------------------------------------------------------- walk-forward results
def load_wf(path=None):
    path = path or os.path.join(HERE, "wf_results.json")
    try:
        rows = json.load(open(path))
    except Exception:
        return {}
    out = {}
    for r in rows:
        if isinstance(r, dict):
            out[(r["tf"], r["mode"], r["symbol"])] = (bool(r["pass"]), r.get("params"))
        else:
            tf, mode, sym, ok, p = r
            out[(tf, mode, sym)] = (bool(ok), p)
    return out

WF = load_wf()

def wf_passed(mode, sym, tf):
    return WF.get((tf, mode, sym), (False, None))[0]

def params_for(mode, sym, tf):
    p = WF.get((tf, mode, sym), (False, None))[1]
    return dict(p) if p else dict(DEFAULT_PARAMS[mode])

def passed_list():
    return [(tf, m, s) for (tf, m, s), (ok, _) in sorted(WF.items()) if ok]
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
    s = symbol.upper()
    if s.startswith("XAU"):
        return 0.01
    return 0.01 if "JPY" in s else 0.0001

def pip_value_per_lot(symbol, price):
    # USD value of 1 pip for 1.00 lot (100,000 units; gold 100 oz), USD account
    s = symbol.upper()[:6]
    if s.startswith("XAU"):
        return 1.0
    if s.endswith("USD"):
        return 10.0
    if s.startswith("USD"):
        return 100000 * pip_size(s) / price
    if s.endswith("JPY"):
        return 1000.0 / RATES["USDJPY"]
    if s.endswith("GBP"):
        return 10.0 * RATES["GBPUSD"]
    return 10.0

def exact_pip_value(symbol):
    """Live sizing only where the pip value needs no other rate (pairs with USD)."""
    s = symbol.upper()[:6]
    return "USD" in (s[:3], s[3:]) and not s.startswith("XAU")

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


# ---------------------------------------------------------------- network
def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

_SSL = None

def ssl_ctx():
    global _SSL
    if _SSL is None:
        _SSL = _ssl_ctx()
    return _SSL


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a redirect while carrying the MetaApi token (it could point anywhere)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


METAAPI_SUFFIX = ".agiliumtrade.ai"


def metaapi_host_ok(url):
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme == "https" and host.endswith(METAAPI_SUFFIX) and "@" not in u.netloc


class MetaApiError(Exception):
    pass


def plain_http_error(code, text=""):
    t = (text or "").lower()
    if code in (401, 403):
        return "MetaApi did not accept the token. Copy a fresh token from metaapi.cloud and paste it in Settings."
    if code == 404:
        return "MetaApi could not find that account id in this region. Check the account id, or press Test connection to find the region."
    if code == 429:
        return "MetaApi says too many requests. Wait a few minutes and try again."
    if code in (502, 503, 504) or "not connected" in t or "timeout" in t:
        return "Your MT5 account is not connected at MetaApi right now. On metaapi.cloud make sure it is Deployed and Connected."
    if code == 400 and "symbol" in t:
        return "The broker does not know that symbol. Check the symbol ending in Settings."
    return "MetaApi answered with error %s." % code


def http_json(url, headers=None, method="GET", body=None, timeout=25, token=None):
    """GET/POST JSON. When `token` is given the URL must be a MetaApi host and redirects are refused."""
    hdr = {"User-Agent": "Mozilla/5.0 (Linux; Android 11) SsalimutoProfits/1.0", "Accept": "application/json"}
    hdr.update(headers or {})
    if not host_allowed(url, token is not None):
        raise (MetaApiError if token is not None else RuntimeError)(
            "Blocked: this app only talks to MetaApi and the public price and news feeds.")
    if token is not None:
        hdr["auth-token"] = token
        opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=ssl_ctx()))
    else:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx()))
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=hdr)
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        try:
            txt = e.read()[:300].decode(errors="ignore")
        except Exception:
            txt = ""
        if token is not None:
            raise MetaApiError(plain_http_error(e.code, txt))
        raise RuntimeError("The server answered with error %s. It will try again later." % e.code)
    except urllib.error.URLError:
        raise (MetaApiError if token is not None else RuntimeError)(
            "No internet, or the server could not be reached. Check your data or Wi-Fi.")
    except (TimeoutError, OSError):
        raise (MetaApiError if token is not None else RuntimeError)("The server took too long to answer. Try again.")


# ---------------------------------------------------------------- public prices (no login)
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}=X?interval={iv}&range={rng}"
_CACHE = {}


def yahoo_chart(sym, tf="1d", max_age=240):
    key = (sym, tf)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    ysym = YAHOO_SYMBOL.get(sym)
    url = (YAHOO.format(sym=sym, iv="1d" if tf == "1d" else "1h", rng="2y" if tf == "1d" else "120d") if not ysym else
           YAHOO.replace("{sym}=X", ysym).format(iv="1d" if tf == "1d" else "1h", rng="2y" if tf == "1d" else "120d"))
    d = http_json(url)["chart"]["result"][0]
    out = parse_yahoo(d)
    _CACHE[key] = (time.time(), out)
    return out


def parse_yahoo(d, now=None):
    """-> {"price", "bars" (closed bars only), "all": every bar}"""
    q = d["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(d.get("timestamp") or []):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append({"t": int(t), "o": o, "h": h, "l": l, "c": c})
    meta = d.get("meta", {})
    price = meta.get("regularMarketPrice") or (bars[-1]["c"] if bars else None)
    iv = 86400 if meta.get("dataGranularity", "1d") == "1d" else 3600
    now = now or time.time()
    closed = [b for b in bars if b["t"] + iv <= now]
    return {"price": price, "bars": closed, "all": bars}


def public_prices(pairs=PAIRS):
    out = {}
    for s in pairs:
        try:
            out[s] = yahoo_chart(s, "1d", max_age=120)["price"]
        except Exception:
            out[s] = None
    for k in ("USDJPY", "GBPUSD", "EURUSD"):
        if out.get(k):
            RATES[k] = out[k]
    return out


# ---------------------------------------------------------------- MetaApi (your own token, your own account)
REGIONS = ("new-york", "london", "singapore", "vint-hill")


class MetaApi:
    def __init__(self, token, account_id, region="new-york", suffix=""):
        self.token = (token or "").strip()
        self.acc = (account_id or "").strip()
        self.region = region or "new-york"
        self.suffix = suffix or ""
        if not self.token or not self.acc:
            raise MetaApiError("Add your MetaApi token and account id in Settings first.")
        if not all(ch.isalnum() or ch in "-_" for ch in self.acc):
            raise MetaApiError("The account id should only have letters, numbers and dashes.")

    @property
    def client(self):
        return "https://mt-client-api-v1.%s.agiliumtrade.ai/users/current/accounts/%s" % (self.region, self.acc)

    @property
    def market(self):
        return "https://mt-market-data-client-api-v1.%s.agiliumtrade.ai/users/current/accounts/%s" % (self.region, self.acc)

    def _req(self, url, method="GET", body=None):
        return http_json(url, method=method, body=body, token=self.token)

    def provisioning(self):
        return self._req("https://mt-provisioning-api-v1.agiliumtrade.ai/users/current/accounts/%s" % self.acc)

    def sym(self, s):
        return s + self.suffix

    def account(self):
        return self._req(self.client + "/account-information")

    def positions(self):
        return self._req(self.client + "/positions") or []

    def deals(self, start, end):
        f = "%Y-%m-%dT%H:%M:%S.000Z"
        return self._req("%s/history-deals/time/%s/%s" % (self.client, start.strftime(f), end.strftime(f))) or []

    def price(self, s):
        r = self._req("%s/symbols/%s/current-price" % (self.client, urllib.parse.quote(self.sym(s))))
        return (r["bid"] + r["ask"]) / 2

    def quote(self, s):
        """-> (mid price, spread in pips)"""
        r = self._req("%s/symbols/%s/current-price" % (self.client, urllib.parse.quote(self.sym(s))))
        return (r["bid"] + r["ask"]) / 2, (r["ask"] - r["bid"]) / pip_size(s)

    def candles(self, s, tf, n=400):
        return self._req("%s/historical-market-data/symbols/%s/timeframes/%s/candles?limit=%d"
                         % (self.market, urllib.parse.quote(self.sym(s)), tf, n))

    def bars(self, s, tf, n=400):
        raw = self.candles(s, tf, n) or []
        bars = [{"o": b["open"], "h": b["high"], "l": b["low"], "c": b["close"], "t": b["time"]} for b in raw]
        return bars[:-1]   # the newest candle is still forming

    def order(self, s, side, lots, sl, tp, comment=TAG):
        body = {"actionType": "ORDER_TYPE_BUY" if side == "buy" else "ORDER_TYPE_SELL",
                "symbol": self.sym(s), "volume": lots, "stopLoss": sl, "comment": comment[:26]}
        if tp is not None:
            body["takeProfit"] = tp
        return self._req(self.client + "/trade", "POST", body)

    def close(self, position_id):
        return self._req(self.client + "/trade", "POST", {"actionType": "POSITION_CLOSE_ID", "positionId": position_id})

    def modify(self, position_id, sl, tp):
        return self._req(self.client + "/trade", "POST", {"actionType": "POSITION_MODIFY", "positionId": position_id,
                                                         "stopLoss": sl, "takeProfit": tp})


def test_connection(token, account_id, region="new-york", suffix=""):
    """-> (ok, message, region_found, info)"""
    try:
        api = MetaApi(token, account_id, region, suffix)
    except MetaApiError as e:
        return False, str(e), region, None
    try:
        prov = api.provisioning() or {}
        api.region = prov.get("region") or region
        state = prov.get("state", "")
        if state and state != "DEPLOYED":
            return False, ("The account is %s at MetaApi. Open metaapi.cloud and press Deploy, then wait a minute."
                           % state.lower()), api.region, None
        if prov.get("connectionStatus") and prov["connectionStatus"] != "CONNECTED":
            return False, ("MetaApi is not connected to your MT5 account yet (%s). Check the MT5 login, "
                           "investor/master password and server PoTrade-MT5 on metaapi.cloud."
                           % prov["connectionStatus"].lower()), api.region, None
    except MetaApiError as e:
        if "did not accept" in str(e):
            return False, str(e), region, None
    try:
        info = api.account()
        msg = "Connected. Balance %.2f %s, equity %.2f." % (info.get("balance", 0), info.get("currency", ""),
                                                          info.get("equity", 0))
        return True, msg, api.region, info
    except MetaApiError as e:
        return False, str(e), api.region, None


# ---------------------------------------------------------------- guards (same rules as the bot)
def today_utc(now=None):
    return (now or datetime.now(timezone.utc)).date().isoformat()


def update_day(st, eq, now=None):
    t = today_utc(now)
    st["peak"] = max(st.get("peak", eq), eq)
    if st.get("day") != t:
        st.update({"day": t, "day_start": eq, "day_trades": 0})
    return st


def guard_reasons(st, eq, stopped=False, live=False, accepted=True):
    why = []
    if stopped:
        why.append("STOP is on (press Resume to allow trading again)")
    if st.get("killed"):
        why.append("kill switch was hit: drawdown reached %.0f%%" % RISK["max_drawdown_pct"])
    dd = (st["peak"] - eq) / st["peak"] * 100 if st.get("peak") else 0
    if dd >= RISK["max_drawdown_pct"]:
        why.append("kill switch: drawdown %.1f%% >= %.0f%%" % (dd, RISK["max_drawdown_pct"]))
    dl = (st["day_start"] - eq) / st["day_start"] * 100 if st.get("day_start") else 0
    if dl >= RISK["daily_loss_limit_pct"]:
        why.append("daily loss %.1f%% >= %.0f%% (trading again tomorrow)" % (dl, RISK["daily_loss_limit_pct"]))
    if st.get("day_trades", 0) >= RISK["max_trades_per_day"]:
        why.append("max %d trades for today reached" % RISK["max_trades_per_day"])
    if live and not accepted:
        why.append('you have not typed "%s"' % LIVE_PHRASE)
    return why


def stop_distance(mode, p, a, sym):
    """Price distance the worst-case stop is away (grid: whole basket)."""
    if mode == "grid":
        sp = p["spacing_atr"] * a
        return grid_risk_pips({"spacing": sp, "sl_d": sp * p["max_levels"]}, pip_size(sym)) * pip_size(sym)
    if mode == "auto":
        return max(p.get("sl_atr", 2.0), p.get("mr_sl_atr", 2.5)) * a
    return p.get("sl_atr", 2.0) * a


def min_lot_check(balance, mode, sym, tf, bars):
    """(ok, text): can this balance trade 0.01 lot within the 3% guard right now?"""
    if not bars or len(bars) < 30:
        return False, "%s: not enough price history to size the trade" % sym
    p = params_for(mode, sym, tf)
    a = indicators(bars, p)["A"][-1]
    d = stop_distance(mode, p, a, sym)
    lots, r = lot_size(balance, RISK["risk_per_trade_pct"], RISK["max_risk_per_trade_pct"],
                       d / pip_size(sym), pip_value_per_lot(sym, bars[-1]["c"]))
    if not lots:
        need = d / pip_size(sym) * pip_value_per_lot(sym, bars[-1]["c"]) * 0.01 / (RISK["max_risk_per_trade_pct"] / 100)
        return False, "%s: %s. You need about $%.0f." % (sym, r, need)
    return True, "%s: %.2f lot risks $%.2f" % (sym, lots, r)


def live_locks(connected, balance, mode, tf, syms, phrase, bars_by_sym):
    """Every reason live trading stays locked (empty = unlocked)."""
    why = []
    if not connected:
        why.append("MetaApi is not connected (Settings > Test connection)")
    if not syms:
        why.append("no pair chosen")
    for s in syms:
        if not wf_passed(mode, s, tf):
            why.append("%s on %s %s is not tested PASS, so practice only (passed: %s)"
                       % (MODE_NAMES[mode], s, "daily" if tf == "1d" else "hourly",
                          ", ".join("%s %s" % (MODE_NAMES[m], x) for t, m, x in passed_list() if exact_pip_value(x))))
        elif not exact_pip_value(s):
            why.append("%s is a cross pair or gold: practice only for now (pip value is not exact)" % s)
    if connected and balance is not None:
        for s in syms:
            ok, txt = min_lot_check(balance, mode, s, tf, bars_by_sym.get(s))
            if not ok:
                why.append("balance too small for the 3%% guard: %s" % txt)
    if (phrase or "").strip() != LIVE_PHRASE:
        why.append('type "%s" to accept the risk' % LIVE_PHRASE)
    return why


# ---------------------------------------------------------------- signals explained
def _f(sym, x):
    return ("%.3f" if "JPY" in sym else "%.5f") % x


def explain(mode, sym, tf, bars):
    """-> {"side": "buy"/"sell"/None, "title", "text"} for the newest CLOSED bar."""
    unit = "day" if tf == "1d" else "hour"
    if not bars or len(bars) < 60:
        return {"side": None, "title": "No data", "text": "Not enough price history yet."}
    p = params_for(mode, sym, tf)
    I = indicators(bars, p)
    i = len(bars) - 1
    sig = entry_signal(mode, I, i, p)
    c, E, R, A = I["c"][i], I["E"][i], I["R"][i], I["A"][i]
    up = c > E and E > I["E"][i - 4]
    dn = c < E and E < I["E"][i - 4]
    trend = ("UPTREND: price %s is above the 200-%s average %s and that average is rising." % (_f(sym, c), unit, _f(sym, E))
             if up else
             "DOWNTREND: price %s is below the 200-%s average %s and that average is falling." % (_f(sym, c), unit, _f(sym, E))
             if dn else
             "NO CLEAR TREND: price %s and the 200-%s average %s disagree, so the bot stays out." % (_f(sym, c), unit, _f(sym, E)))
    use = mode
    extra = ""
    if mode == "auto":
        use = "trend" if I["ADX"][i] >= p["adx_th"] else "meanrev"
        extra = "ADX is %.0f (%s %d), so it uses the %s rules. " % (
            I["ADX"][i], ">=" if use == "trend" else "<", p["adx_th"], "trend" if use == "trend" else "mean reversion")
    if use == "trend":
        n = p["breakout"]
        hi, lo = max(I["h"][i - n:i]), min(I["l"][i - n:i])
        wait = ("It needs a close above the %d-%s high %s to buy." % (n, unit, _f(sym, hi)) if up else
                "It needs a close below the %d-%s low %s to sell." % (n, unit, _f(sym, lo)) if dn else "")
    else:
        lo_r = p["rsi_lo"]
        if up:
            wait = ("It buys a dip: RSI(2) is %.0f (needs under %d)%s." %
                    (R, lo_r, "" if mode == "grid" else " or a close below the lower band %s" % _f(sym, I["BBL"][i])))
        elif dn:
            wait = ("It sells a bounce: RSI(2) is %.0f (needs over %d)%s." %
                    (R, 100 - lo_r, "" if mode == "grid" else " or a close above the upper band %s" % _f(sym, I["BBU"][i])))
        else:
            wait = ""
    if sig:
        side = sig["side"]
        sl = c - (1 if side == "buy" else -1) * sig["sl_d"]
        title = "%s signal" % side.upper()
        text = "%s%s %s The rule fired on the last closed %s. Stop about %s." % (extra, trend, wait, unit, _f(sym, sl))
    else:
        side = None
        title = "Wait"
        text = "%s%s %s Atr is %s." % (extra, trend, wait, _f(sym, A))
        text = text.replace(" Atr is", " Typical daily move (ATR) is" if tf == "1d" else " Typical hourly move (ATR) is")
    return {"side": side, "title": title, "text": " ".join(text.split())}


# ---------------------------------------------------------------- practice (paper) trading
def new_practice():
    return {"balance": PRACTICE_START, "peak": PRACTICE_START, "positions": {}, "history": [],
            "last_bar": {}, "killed": False, "day_trades": 0, "started": datetime.now(timezone.utc).isoformat()}


def _pnl(pos, px):
    sgn = 1 if pos["side"] == "buy" else -1
    ps = pip_size(pos["sym"])
    return sum(sgn * (px - e) / ps * pos["pv"] * lots for e, lots in pos["fills"])


def practice_equity(ps, prices):
    eq = ps["balance"]
    for s, pos in ps["positions"].items():
        px = prices.get(s)
        if px:
            eq += _pnl(pos, px)
    return eq


def _close_paper(ps, sym, px, why, now):
    pos = ps["positions"].pop(sym)
    r = round(_pnl(pos, px), 2)
    ps["balance"] = round(ps["balance"] + r, 2)
    ps["history"].insert(0, {"sym": sym, "side": pos["side"], "kind": pos["kind"], "mode": pos.get("mode"),
                             "lots": round(sum(l for _, l in pos["fills"]), 2), "levels": len(pos["fills"]),
                             "entry": pos["fills"][0][0], "exit": px, "pnl": r, "why": why,
                             "opened": pos["opened_at"], "closed": now.isoformat()})
    del ps["history"][300:]
    return "Practice: closed %s %s (%s) %+.2f USD" % (sym, pos["side"].upper(), why, r)


def practice_step(ps, mode, tf, syms, market, now=None, follow=True, stopped=False, news=False):
    """One check. market = {sym: {"price": px, "bars": closed bars}}. Returns a list of plain events.
    news: event list from fetch_news() (None = feed unavailable: practice still trades; False = no check)."""
    now = now or datetime.now(timezone.utc)
    ev = []
    prices = {s: m.get("price") for s, m in market.items()}
    eq = practice_equity(ps, prices)
    update_day(ps, eq, now)
    dd = (ps["peak"] - eq) / ps["peak"] * 100 if ps["peak"] else 0
    if dd >= RISK["max_drawdown_pct"] and not ps.get("killed"):
        for s in list(ps["positions"]):
            if prices.get(s):
                ev.append(_close_paper(ps, s, prices[s], "kill switch", now))
        ps["killed"] = True
        ev.append("Practice KILL SWITCH: drawdown %.1f%%. Practice trading stopped (Reset to start again)." % dd)
        return ev
    for s in list(ps["positions"]):
        pos = ps["positions"][s]
        m = market.get(s) or {}
        px, bars = m.get("price"), m.get("bars") or []
        if not px:
            continue
        buy = pos["side"] == "buy"
        p = params_for(pos.get("mode", mode), s, pos.get("tf", tf))
        new = [b for b in bars if b["t"] > pos.get("seen_t", pos["opened_t"])]
        hit = None
        for b in new:   # closed bars since the last look: stop first (pessimistic), then target
            if buy and b["l"] <= pos["sl"] or not buy and b["h"] >= pos["sl"]:
                hit = (pos["sl"], "stop loss"); break
            if buy and b["h"] >= pos["tp"] or not buy and b["l"] <= pos["tp"]:
                hit = (pos["tp"], "take profit"); break
        if not hit:
            if buy and px <= pos["sl"] or not buy and px >= pos["sl"]:
                hit = (px, "stop loss")
            elif buy and px >= pos["tp"] or not buy and px <= pos["tp"]:
                hit = (px, "take profit")
        if not hit and new and pos["kind"] in ("mr", "grid"):
            I = indicators(bars, p)
            i = len(bars) - 1
            held = len([b for b in bars if b["t"] > pos["opened_t"]])
            if pos["kind"] == "mr" and mr_exit_now(I, i, pos["side"], held, p):
                hit = (px, "back to average" if held < p["max_bars"] else "time limit")
            elif pos["kind"] == "grid" and held >= p.get("max_bars", 72):
                hit = (px, "time limit")
        if new:
            pos["seen_t"] = bars[-1]["t"]
        if hit:
            ev.append(_close_paper(ps, s, hit[0], hit[1], now))
            continue
        # capped grid add: SAME lot as level 1 (never martingale), only when guards allow
        if pos["kind"] == "grid" and len(pos["fills"]) < p["max_levels"] and follow and not \
                guard_reasons(ps, practice_equity(ps, prices), stopped):
            sgn = 1 if buy else -1
            level = pos["fills"][0][0] - sgn * len(pos["fills"]) * pos["spacing"]
            if (px - level) * sgn <= 0:
                cost = (RISK["spread_pips"].get(s, 1.5) + RISK["slippage_pips"]) * pip_size(s)
                pos["fills"].append([px + sgn * cost, pos["fills"][0][1]])
                avg = sum(e for e, _ in pos["fills"]) / len(pos["fills"])
                pos["tp"] = avg + sgn * pos["tp_d"]
                ps["day_trades"] += 1
                ev.append("Practice: grid level %d/%d on %s" % (len(pos["fills"]), p["max_levels"], s))
    if not follow or stopped:
        return ev
    for s in syms:
        m = market.get(s) or {}
        px, bars = m.get("price"), m.get("bars") or []
        if not px or len(bars) < WARMUP:
            continue
        key = "%s|%s|%s" % (mode, tf, s)
        if ps["last_bar"].get(key) == bars[-1]["t"]:
            continue          # already looked at this closed bar
        ps["last_bar"][key] = bars[-1]["t"]
        if s in ps["positions"]:
            continue
        p = params_for(mode, s, tf)
        I = indicators(bars, p)
        sig = entry_signal(mode, I, len(bars) - 1, p)
        if not sig:
            continue
        why = guard_reasons(ps, practice_equity(ps, prices), stopped)
        nb = news_block(s, news, now) if news else None
        if nb:
            why.append(nb)
            ps["last_bar"].pop(key, None)   # look at this bar again after the news window
        if why:
            ev.append("Practice: %s %s signal skipped (%s)" % (s, sig["side"].upper(), why[0]))
            continue
        side = sig["side"]; sgn = 1 if side == "buy" else -1
        cost = (RISK["spread_pips"].get(s, 1.5) + RISK["slippage_pips"]) * pip_size(s)
        entry = px + sgn * cost
        pv = pip_value_per_lot(s, px)
        risk_pips = grid_risk_pips(sig, pip_size(s)) if sig["kind"] == "grid" else sig["sl_d"] / pip_size(s)
        lots, risk = lot_size(ps["balance"], RISK["risk_per_trade_pct"], RISK["max_risk_per_trade_pct"], risk_pips, pv)
        if not lots:
            ev.append("Practice: %s %s skipped (%s)" % (s, side.upper(), risk))
            continue
        ps["positions"][s] = {"sym": s, "side": side, "kind": sig["kind"], "mode": mode, "tf": tf,
                              "fills": [[entry, lots]], "pv": pv, "sl": entry - sgn * sig["sl_d"],
                              "tp": entry + sgn * sig["tp_d"], "tp_d": sig["tp_d"], "spacing": sig.get("spacing"),
                              "opened_t": bars[-1]["t"], "seen_t": bars[-1]["t"], "opened_at": now.isoformat(),
                              "risk": risk}
        ps["day_trades"] += 1
        ev.append("Practice: %s %s %.2f lot at %s, stop %s, risk $%.2f" % (
            side.upper(), s, lots, _f(s, entry), _f(s, ps["positions"][s]["sl"]), risk))
    return ev


def practice_summary(ps, prices):
    eq = practice_equity(ps, prices)
    closed = [h["pnl"] for h in ps["history"]]
    wins = [x for x in closed if x > 0]
    today = today_utc()
    today_closed = sum(h["pnl"] for h in ps["history"] if h["closed"][:10] == today)
    return {"balance": ps["balance"], "equity": round(eq, 2), "pl_total": round(eq - PRACTICE_START, 2),
            "pl_today": round(today_closed + (eq - ps["balance"]), 2), "trades": len(closed),
            "win_rate": round(len(wins) / len(closed) * 100) if closed else 0, "open": len(ps["positions"])}


# ---------------------------------------------------------------- real account status + live step
def account_status(api, st, mode, tf, syms, stopped, accepted, now=None, news=False):
    now = now or datetime.now(timezone.utc)
    info = api.account()
    update_day(st, info["equity"], now)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    realized = 0.0
    try:
        for d in api.deals(midnight, now):
            realized += d.get("profit", 0) + d.get("commission", 0) + d.get("swap", 0)
    except Exception:
        realized = None
    pos = api.positions()
    floating = sum(p.get("profit", 0) for p in pos)
    why = guard_reasons(st, info["equity"], stopped, live=True, accepted=accepted)
    bars = {}
    for s in syms:
        nb = news_block(s, news, now) if news is not False else None
        if nb:
            why.append(nb)
        if not wf_passed(mode, s, tf):
            why.append("%s did not pass walk-forward on %s" % (MODE_NAMES[mode], s))
            continue
        try:
            bars[s] = api.bars(s, tf)
            ok, txt = min_lot_check(info["balance"], mode, s, tf, bars[s])
            if not ok:
                why.append(txt)
        except Exception as e:
            why.append("%s: could not check lot size (%s)" % (s, e))
    return {"balance": info["balance"], "equity": info["equity"], "currency": info.get("currency", ""),
            "positions": pos, "realized": realized, "floating": floating,
            "today": None if realized is None else realized + floating, "why": why, "bars": bars}


def live_step(api, st, mode, tf, syms, stopped, accepted, now=None, news=False):
    """One live check: the bot's run-loop body. Real orders. Call only when live_locks() is empty."""
    now = now or datetime.now(timezone.utc)
    ev = []
    info = api.account()
    eq = info["equity"]
    update_day(st, eq, now)
    dd = (st["peak"] - eq) / st["peak"] * 100 if st.get("peak") else 0
    if dd >= RISK["max_drawdown_pct"]:
        st["killed"] = True
        return ["LIVE KILL SWITCH: drawdown %.1f%% from the peak. Live trading stopped." % dd]
    mine = [x for x in api.positions() if str(x.get("comment", "")).startswith(TAG)]
    st.setdefault("last_bar", {})
    for s in syms:
        if not wf_passed(mode, s, tf) or not exact_pip_value(s):
            continue          # never trade live what did not pass walk-forward
        p = params_for(mode, s, tf)
        bars = api.bars(s, tf)
        if len(bars) < WARMUP:
            continue
        key = "%s|%s|%s" % (mode, tf, s)
        new_bar = st["last_bar"].get(key) != bars[-1]["t"]
        st["last_bar"][key] = bars[-1]["t"]
        I = indicators(bars, p); i = len(bars) - 1; price = bars[-1]["c"]
        ps_, pv = pip_size(s), pip_value_per_lot(s, price)
        held = [x for x in mine if str(x.get("symbol", "")).startswith(s)]
        blocked = guard_reasons(st, eq, stopped, live=True, accepted=accepted)
        nb = news_block(s, news, now) if news is not False else None
        if nb:
            blocked.append(nb)
        if held:
            if new_bar:
                ev += live_manage(api, st, s, held, I, i, p, tf, blocked, now)
            continue
        if not new_bar:
            continue
        sig = entry_signal(mode, I, i, p)
        if not sig:
            continue
        if blocked:
            if nb:   # look at this bar again on the next check, once the news window has passed
                st["last_bar"].pop(key, None)
            ev.append("LIVE: %s %s signal skipped (%s)" % (s, sig["side"].upper(), blocked[0]))
            continue
        side = sig["side"]; sgn = 1 if side == "buy" else -1
        risk_pips = grid_risk_pips(sig, ps_) if sig["kind"] == "grid" else sig["sl_d"] / ps_
        lots, risk = lot_size(info["balance"], RISK["risk_per_trade_pct"], RISK["max_risk_per_trade_pct"], risk_pips, pv)
        if not lots:
            ev.append("LIVE: %s %s signal skipped: %s" % (s, side.upper(), risk)); continue
        nd = 3 if "JPY" in s else 5
        sl = round(price - sgn * sig["sl_d"], nd); tp = round(price + sgn * sig["tp_d"], nd)
        if sig["kind"] == "grid":
            st.setdefault("grid", {})[s] = {"first": price, "spacing": sig["spacing"], "sl": sl,
                                            "tp_d": sig["tp_d"], "levels": 1, "side": side}
        api.order(s, side, lots, sl, tp, "%s:%s" % (TAG, sig["kind"]))
        st["day_trades"] = st.get("day_trades", 0) + 1
        ev.append("LIVE: %s %s %.2f lot, stop %s, target %s, risk $%.2f" % (side.upper(), s, lots, sl, tp, risk))
    return ev


def live_manage(api, st, s, held, I, i, p, tf, blocked, now):
    ev = []
    kind = str(held[0].get("comment", "")).split(":")[-1]
    side = "buy" if "BUY" in held[0].get("type", "") else "sell"; sgn = 1 if side == "buy" else -1
    opened = min(datetime.fromisoformat(str(x["time"]).replace("Z", "+00:00")) for x in held)
    held_bars = int((now - opened) / timedelta(seconds=TF_SECONDS.get(tf, 86400)))
    if (kind == "mr" and mr_exit_now(I, i, side, held_bars, p)) or (kind == "grid" and held_bars >= p.get("max_bars", 72)):
        for x in held:
            api.close(x["id"])
        st.get("grid", {}).pop(s, None)
        return ["LIVE: closed %s (%s exit)" % (s, "mean reversion" if kind == "mr" else "grid time")]
    g = st.get("grid", {}).get(s)
    if kind != "grid" or not g or blocked or g["levels"] >= p["max_levels"]:
        return ev
    level = g["first"] - sgn * g["levels"] * g["spacing"]; price = I["c"][i]
    if (price - level) * sgn > 0:
        return ev
    lots = held[0]["volume"]   # same lot: never martingale
    entries = [x["openPrice"] for x in held] + [price]
    tp = round(sum(entries) / len(entries) + sgn * g["tp_d"], 5)
    api.order(s, side, lots, g["sl"], tp, "%s:grid" % TAG)
    for x in held:
        api.modify(x["id"], g["sl"], tp)
    g["levels"] += 1; st["day_trades"] = st.get("day_trades", 0) + 1
    return ["LIVE: grid level %d on %s" % (g["levels"], s)]


def close_bot_positions(api):
    n = 0
    for x in api.positions():
        if str(x.get("comment", "")).startswith(TAG):
            api.close(x["id"]); n += 1
    return n


# ---------------------------------------------------------------- PIN and secrets (stored only on this phone)
PIN_ITER = 120000


def _pbkdf2(secret, salt, n=PIN_ITER, dklen=32):
    try:
        return hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, n, dklen)
    except Exception:   # pure-Python fallback, same result
        out, block = b"", 1
        while len(out) < dklen:
            u = hmac.new(secret.encode(), salt + block.to_bytes(4, "big"), hashlib.sha256).digest()
            acc = bytearray(u)
            for _ in range(n - 1):
                u = hmac.new(secret.encode(), u, hashlib.sha256).digest()
                acc = bytearray(a ^ b for a, b in zip(acc, u))
            out += bytes(acc); block += 1
        return out[:dklen]


def pin_rule(pin):
    """None if the PIN/password is acceptable, else a plain reason."""
    pin = pin or ""
    if pin.isdigit():
        if len(pin) < 4:
            return "A PIN needs at least 4 digits."
        if len(set(pin)) == 1 or pin in "0123456789" or pin in "9876543210":
            return "That PIN is too easy to guess. Avoid 1111 or 1234."
    elif len(pin) < 6:
        return "A password needs at least 6 characters (or use a PIN of 4+ digits)."
    if len(pin) > 64:
        return "That is too long (64 characters at most)."
    return None


class Vault:
    """secure.json in the app's private folder: PIN hash + secrets encrypted with a key from the PIN."""

    def __init__(self, folder):
        self.path = os.path.join(folder, "secure.json")
        self.key = None
        try:
            self.d = json.load(open(self.path))
        except Exception:
            self.d = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.d, f)
        os.replace(tmp, self.path)

    def has_pin(self):
        return bool(self.d.get("pin_hash"))

    def set_pin(self, pin, keep_secrets=True):
        bad = pin_rule(pin)
        if bad:
            raise ValueError(bad)
        old = {}
        if keep_secrets and self.key:
            old = {k: self.get(k) for k in list(self.d.get("secrets", {}))}
        salt, esalt = os.urandom(16), os.urandom(16)
        self.d = {"pin_hash": base64.b64encode(_pbkdf2(pin, salt)).decode(), "salt": base64.b64encode(salt).decode(),
                  "esalt": base64.b64encode(esalt).decode(), "iter": PIN_ITER, "fails": 0, "until": 0,
                  "kind": "pin" if pin.isdigit() else "password", "secrets": {}}
        self.key = _pbkdf2(pin, esalt, PIN_ITER, 64)
        for k, v in old.items():
            if v:
                self.put(k, v)
        self._save()

    def wait_seconds(self):
        return max(0, int(self.d.get("until", 0) - time.time()))

    def unlock(self, pin):
        """-> (ok, message)"""
        w = self.wait_seconds()
        if w:
            return False, "Too many wrong tries. Wait %d seconds." % w
        salt = base64.b64decode(self.d["salt"])
        good = hmac.compare_digest(base64.b64encode(_pbkdf2(pin or "", salt, self.d.get("iter", PIN_ITER))).decode(),
                                   self.d["pin_hash"])
        if good:
            self.d["fails"] = 0; self.d["until"] = 0
            self.key = _pbkdf2(pin, base64.b64decode(self.d["esalt"]), self.d.get("iter", PIN_ITER), 64)
            self._save()
            return True, "Unlocked"
        self.d["fails"] = self.d.get("fails", 0) + 1
        if self.d["fails"] >= 5:
            self.d["until"] = time.time() + min(3600, 30 * 2 ** (self.d["fails"] - 5))
        self._save()
        left = max(0, 5 - self.d["fails"])
        return False, ("Wrong %s. %d tries left before a wait." % (self.d.get("kind", "PIN"), left) if left else
                       "Wrong %s. Wait %d seconds." % (self.d.get("kind", "PIN"), self.wait_seconds()))

    def lock(self):
        self.key = None

    def _stream(self, nonce, n):
        out, c = b"", 0
        while len(out) < n:
            out += hmac.new(self.key[:32], nonce + c.to_bytes(4, "big"), hashlib.sha256).digest(); c += 1
        return out[:n]

    def put(self, name, value):
        if not self.key:
            raise ValueError("locked")
        raw = (value or "").encode()
        nonce = os.urandom(16)
        ct = bytes(a ^ b for a, b in zip(raw, self._stream(nonce, len(raw))))
        tag = hmac.new(self.key[32:], nonce + ct, hashlib.sha256).digest()
        self.d.setdefault("secrets", {})[name] = base64.b64encode(nonce + tag + ct).decode()
        self._save()

    def get(self, name):
        blob = self.d.get("secrets", {}).get(name)
        if not blob or not self.key:
            return ""
        b = base64.b64decode(blob)
        nonce, tag, ct = b[:16], b[16:48], b[48:]
        if not hmac.compare_digest(tag, hmac.new(self.key[32:], nonce + ct, hashlib.sha256).digest()):
            return ""
        return bytes(a ^ b for a, b in zip(ct, self._stream(nonce, len(ct)))).decode(errors="ignore")

    def forget(self):
        """Forgot the PIN: wipe the PIN and every saved secret."""
        self.d = {}; self.key = None
        try:
            os.remove(self.path)
        except OSError:
            pass


def mask(s, keep=4):
    s = s or ""
    if not s:
        return "(not set)"
    if len(s) <= keep * 2:
        return "•" * len(s)
    return s[:keep] + "•" * 8 + s[-keep:]


# ---------------------------------------------------------------- world live activities: news + sessions
FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
NEWS_CURRENCIES = ("USD", "GBP", "EUR", "JPY")
NEWS_WINDOW_MIN = 60
NEWS_NOTE = ("The news filter is a SAFETY filter, not an edge: it was not backtested (no free history of the "
             "calendar), it only avoids opening trades in the wild minutes around big news.")

import re as _re

_ISO = _re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?([+-]\d{2}):?(\d{2})")
_LOC = _re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s*([AP]M).*?UTC([+-]\d{2}):?(\d{2})", _re.I)


def parse_ff_date(s):
    """Feed dates are ISO with an offset ("2026-11-27T08:30:00-05:00"); some copies come localised
    ("Fri 2026-11-27 4:30 PM EAT (UTC+03:00)"). -> aware UTC datetime, or None."""
    s = str(s or "")
    m = _ISO.search(s)
    if m:
        d, hh, mm, _, oh, om = m.groups()
        h, mi = int(hh), int(mm)
    else:
        m = _LOC.search(s)
        if not m:
            return None
        d, hh, mm, ap, oh, om = m.groups()
        h, mi = int(hh) % 12 + (12 if ap.upper() == "PM" else 0), int(mm)
    off = int(oh[1:]) * 60 + int(om)
    off = -off if oh.startswith("-") else off
    y, mo, da = map(int, d.split("-"))
    return datetime(y, mo, da, h, mi, tzinfo=timezone.utc) - timedelta(minutes=off)


def parse_news(raw):
    out = []
    for e in raw or []:
        t = parse_ff_date(e.get("date"))
        if not t:
            continue
        out.append({"t": t.timestamp(), "cur": str(e.get("country", "")).upper(), "title": e.get("title", ""),
                    "impact": e.get("impact", ""), "forecast": e.get("forecast", ""), "previous": e.get("previous", "")})
    out.sort(key=lambda x: x["t"])
    return out


_NEWS = {"at": 0, "events": None, "error": ""}


def fetch_news(cache_file=None, max_age=3600):
    """Weekly calendar, fetched at most once an hour (the feed asks for light use). Falls back to the last
    good copy on disk for up to 8 days. -> (events or None, note)"""
    if _NEWS["events"] is not None and time.time() - _NEWS["at"] < max_age:
        return _NEWS["events"], ""
    try:
        ev = parse_news(http_json(FF_URL, timeout=20))
        if not ev:
            raise RuntimeError("empty calendar")
        _NEWS.update(at=time.time(), events=ev, error="")
        if cache_file:
            try:
                json.dump({"at": time.time(), "events": ev}, open(cache_file, "w"))
            except Exception:
                pass
        return ev, ""
    except Exception as e:
        _NEWS["error"] = str(e)
        if _NEWS["events"] is not None and time.time() - _NEWS["at"] < 8 * 86400:
            return _NEWS["events"], "news feed busy, using the copy from %d min ago" % ((time.time() - _NEWS["at"]) // 60)
        if cache_file and os.path.exists(cache_file):
            try:
                c = json.load(open(cache_file))
                if time.time() - c["at"] < 8 * 86400:
                    _NEWS.update(at=c["at"], events=c["events"])
                    return c["events"], "news feed busy, using a saved copy"
            except Exception:
                pass
        return None, "news feed unavailable (%s)" % e


def news_block(sym, events, now=None, window=NEWS_WINDOW_MIN):
    """Reason string if a HIGH-impact event for this pair's currencies is within +-window minutes, else None."""
    if events is None:
        return "news calendar unavailable, so no new trades (safety)"
    now = (now or datetime.now(timezone.utc)).timestamp()
    curs = (sym[:3].upper(), sym[3:6].upper())
    for e in events:
        if e["impact"] == "High" and e["cur"] in curs and abs(e["t"] - now) <= window * 60:
            mins = int((e["t"] - now) // 60)
            when = "in %d min" % mins if mins >= 0 else "%d min ago" % -mins
            return "high-impact news %s %s (%s): no new %s trades 60 min before/after" % (e["cur"], e["title"], when, sym)
    return None


def upcoming_high(events, now=None, currencies=NEWS_CURRENCIES, limit=20):
    if not events:
        return []
    now = (now or datetime.now(timezone.utc)).timestamp()
    return [e for e in events if e["impact"] == "High" and e["cur"] in currencies and e["t"] >= now - 3600][:limit]


def _nth_sunday(y, m, n):
    """n-th Sunday of a month (n=-1: last)."""
    if n > 0:
        d = datetime(y, m, 1, tzinfo=timezone.utc)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    d = nxt - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def utc_offset_hours(city, now):
    y = now.year
    if city == "London":
        return 1 if _nth_sunday(y, 3, -1) + timedelta(hours=1) <= now < _nth_sunday(y, 10, -1) + timedelta(hours=1) else 0
    if city == "New York":
        return -4 if _nth_sunday(y, 3, 2) + timedelta(hours=7) <= now < _nth_sunday(y, 11, 1) + timedelta(hours=6) else -5
    if city == "Sydney":   # daylight time from the 1st Sunday of October to the 1st Sunday of April
        return 10 if _nth_sunday(y, 4, 1) - timedelta(hours=16) <= now < _nth_sunday(y, 10, 1) - timedelta(hours=16) else 11
    if city == "Tokyo":
        return 9
    return 0


SESSIONS = (("Sydney", 7, 16), ("Tokyo", 9, 18), ("London", 8, 17), ("New York", 8, 17))


def market_open(now=None):
    """Forex trades from Sunday 17:00 to Friday 17:00 New York time."""
    now = now or datetime.now(timezone.utc)
    ny = now + timedelta(hours=utc_offset_hours("New York", now))
    wd, h = ny.weekday(), ny.hour
    if wd == 5 or (wd == 4 and h >= 17) or (wd == 6 and h < 17):
        return False
    return True


def sessions(now=None):
    """-> [(city, is_open, local 'HH:MM', text)]"""
    now = now or datetime.now(timezone.utc)
    fx = market_open(now)
    out = []
    for city, o, c in SESSIONS:
        loc = now + timedelta(hours=utc_offset_hours(city, now))
        is_open = fx and loc.weekday() < 5 and o <= loc.hour < c
        if not fx:
            txt = "closed (weekend)"
        elif is_open:
            txt = "open, closes %02d:00 local" % c
        else:
            txt = "closed, opens %02d:00 local" % o
        out.append((city, is_open, loc.strftime("%H:%M"), txt))
    return out


# ---------------------------------------------------------------- direction view (practice only)
def weekly_bars(bars):
    out, key = [], None
    for b in bars:
        k = datetime.fromtimestamp(b["t"], timezone.utc).isocalendar()[:2]
        if k != key:
            out.append(dict(b)); key = k
        else:
            w = out[-1]; w["h"] = max(w["h"], b["h"]); w["l"] = min(w["l"], b["l"]); w["c"] = b["c"]
    return out


def trend_word(closes, n):
    if len(closes) < n + 5:
        return "not enough data"
    e = ema(closes, n)
    if closes[-1] > e[-1] and e[-1] > e[-5]:
        return "UP"
    if closes[-1] < e[-1] and e[-1] < e[-5]:
        return "DOWN"
    return "SIDEWAYS"


def direction(mode, sym, bars, price=None, tf="1d"):
    """BUY / SELL / WAIT with daily + weekly trend, entry, stop, target. Practice only."""
    out = {"sym": sym, "action": "WAIT", "daily": "?", "weekly": "?", "entry": None, "stop": None, "target": None,
           "tested": wf_passed(mode, sym, tf), "live_ok": wf_passed(mode, sym, tf) and exact_pip_value(sym),
           "risk_001": None, "why": "", "exit_rule": ""}
    if not bars or len(bars) < 60:
        out["why"] = "Not enough price history yet."
        return out
    c = [b["c"] for b in bars]
    out["daily"] = trend_word(c, 200 if len(c) > 220 else 50)
    out["weekly"] = trend_word([w["c"] for w in weekly_bars(bars)], 40 if len(bars) > 400 else 20)
    e = explain(mode, sym, tf, bars)
    out["why"] = e["text"]
    p = params_for(mode, sym, tf)
    I = indicators(bars, p)
    sig = entry_signal(mode, I, len(bars) - 1, p)
    px = price or c[-1]
    if sig:
        sgn = 1 if sig["side"] == "buy" else -1
        nd = 2 if sym.startswith("XAU") else 3 if "JPY" in sym else 5
        out.update(action=sig["side"].upper(), entry=round(px, nd), stop=round(px - sgn * sig["sl_d"], nd),
                   target=round(px + sgn * sig["tp_d"], nd))
        stop_pips = (grid_risk_pips(sig, pip_size(sym)) if sig["kind"] == "grid" else sig["sl_d"] / pip_size(sym))
        out["risk_001"] = round(stop_pips * pip_value_per_lot(sym, px) * 0.01, 2)
        out["exit_rule"] = {"mr": "Exit early when a day closes back past the 5-day average, or after %d bars." % p.get("max_bars", 24),
                            "grid": "At most %d entries, all the same lot. One stop for all." % p.get("max_levels", 3),
                            "trend": "Let the stop or target close it."}[sig["kind"]]
    return out


def risk_note(d, balance):
    """Plain check of the 3% guard for a manual 0.01-lot trade."""
    if d.get("risk_001") is None:
        return ""
    if not balance:
        return "0.01 lot risks about $%.2f if the stop is hit. Add your balance in Settings to check the 3%% rule." % d["risk_001"]
    pct = d["risk_001"] / balance * 100
    if pct > RISK["max_risk_per_trade_pct"]:
        return ("0.01 lot risks about $%.2f = %.0f%% of your $%.2f. That is over the 3%% limit: the bot would SKIP this trade."
                % (d["risk_001"], pct, balance))
    return "0.01 lot risks about $%.2f = %.1f%% of your $%.2f (limit 3%%)." % (d["risk_001"], pct, balance)


def mt5_ticket(d, lots=0.01):
    if d["action"] not in ("BUY", "SELL"):
        return ""
    return "%s %s  lot %.2f  SL %s  TP %s" % (d["sym"], d["action"], lots, d["stop"], d["target"])


def practice_manual_open(ps, d, market, now=None, stopped=False, news=False, mode="meanrev", tf="1d"):
    """The user tapped 'Practice this trade'. Same guards and lot sizing as the bot. -> message"""
    now = now or datetime.now(timezone.utc)
    s = d["sym"]
    if d["action"] not in ("BUY", "SELL"):
        return "No signal on %s right now." % s
    if s in ps["positions"]:
        return "You already have a practice trade on %s." % s
    m = market.get(s) or {}
    px = m.get("price")
    if not px:
        return "No price for %s yet. Try again in a moment." % s
    prices = {k: v.get("price") for k, v in market.items()}
    eq = practice_equity(ps, prices)
    update_day(ps, eq, now)
    why = guard_reasons(ps, eq, stopped)
    nb = news_block(s, news, now) if news else None
    if nb:
        why.append(nb)
    if why:
        return "Not allowed: %s." % why[0]
    side = d["action"].lower(); sgn = 1 if side == "buy" else -1
    p = params_for(mode, s, tf)
    I = indicators(m["bars"], p)
    sig = entry_signal(mode, I, len(m["bars"]) - 1, p) or {"kind": "mr", "sl_d": abs(d["entry"] - d["stop"]),
                                                          "tp_d": abs(d["target"] - d["entry"])}
    cost = (RISK["spread_pips"].get(s, 1.5) + RISK["slippage_pips"]) * pip_size(s)
    entry = px + sgn * cost
    pv = pip_value_per_lot(s, px)
    risk_pips = grid_risk_pips(sig, pip_size(s)) if sig["kind"] == "grid" else sig["sl_d"] / pip_size(s)
    lots, risk = lot_size(ps["balance"], RISK["risk_per_trade_pct"], RISK["max_risk_per_trade_pct"], risk_pips, pv)
    if not lots:
        return "Skipped: %s." % risk
    ps["positions"][s] = {"sym": s, "side": side, "kind": sig["kind"], "mode": mode, "tf": tf, "fills": [[entry, lots]],
                          "pv": pv, "sl": entry - sgn * sig["sl_d"], "tp": entry + sgn * sig["tp_d"], "tp_d": sig["tp_d"],
                          "spacing": sig.get("spacing"), "opened_t": m["bars"][-1]["t"], "seen_t": m["bars"][-1]["t"],
                          "opened_at": now.isoformat(), "risk": risk, "manual": True}
    ps["day_trades"] = ps.get("day_trades", 0) + 1
    return "Practice %s %s %.2f lot opened at %s (risk $%.2f)." % (side.upper(), s, lots, _f(s, entry), risk)


def practice_close_now(ps, sym, price, now=None):
    if sym not in ps["positions"] or not price:
        return "Nothing to close."
    return _close_paper(ps, sym, price, "closed by you", now or datetime.now(timezone.utc))


# ---------------------------------------------------------------- crypto scanner (read-only public prices, practice only)
CRYPTO = ("BTCUSDT", "ETHUSDT")
BINANCE = "https://data-api.binance.vision/api/v3/klines?symbol=%s&interval=1h&limit=200"


def crypto_scan(sym, rows=None):
    """Volume and momentum from public hourly klines (no keys, no accounts). Untested: information only."""
    k = rows if rows is not None else http_json(BINANCE % sym, timeout=20)
    c = [float(r[4]) for r in k]
    v = [float(r[5]) for r in k]
    tb = [float(r[9]) for r in k]
    if len(c) < 50:
        raise RuntimeError("not enough data")
    r14 = rsi(c, 14)[-1]
    mom24 = (c[-1] / c[-25] - 1) * 100
    vol_ratio = sum(v[-24:]) / (sum(v[-168:-24]) / 6) if sum(v[-168:-24]) else 1
    buy_share = sum(tb[-24:]) / sum(v[-24:]) * 100 if sum(v[-24:]) else 50
    lean = ("buyers leaning in" if buy_share > 52 and mom24 > 0 else
            "sellers leaning in" if buy_share < 48 and mom24 < 0 else "mixed")
    return {"sym": sym.replace("USDT", "USD"), "price": c[-1], "rsi14": round(r14, 1), "mom24": round(mom24, 2),
            "vol_ratio": round(vol_ratio, 2), "buy_share": round(buy_share, 1), "lean": lean,
            "trend": trend_word(c, 50)}


# ---------------------------------------------------------------- outbound host allowlist
PUBLIC_HOSTS = ("query1.finance.yahoo.com", "nfs.faireconomy.media", "data-api.binance.vision")


def host_allowed(url, with_token):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or "@" in u.netloc:
        return False
    if with_token:
        return metaapi_host_ok(url)
    return (u.hostname or "").lower() in PUBLIC_HOSTS or metaapi_host_ok(url)
