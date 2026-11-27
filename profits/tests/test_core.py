"""Desktop tests for Ssalimuto Profits logic (no network needed except --live)."""
import json, os, sys, tempfile, time
from datetime import datetime, timezone, timedelta
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import core

DATA = os.environ.get("PROFITS_DATA") or os.path.join(HERE, "data")

def bars_of(sym, tf="1d"):
    p = os.path.join(DATA, "%s%s.json" % (sym, "_1d" if tf == "1d" else ""))
    d = json.load(open(p))["chart"]["result"][0]
    return core.parse_yahoo(d, now=10 ** 12)["bars"]

def test_wf():
    pl = core.passed_list(); print("  passed:", pl)
    assert ("1d", "meanrev", "GBPUSD") in pl and all(tf == "1d" for tf, _, _ in pl)
    assert len(core.PAIRS) == 11 and core.pip_size("XAUUSD") == 0.01 and core.pip_value_per_lot("XAUUSD", 2000) == 1.0
    assert not core.exact_pip_value("EURGBP") and not core.exact_pip_value("XAUUSD") and core.exact_pip_value("USDCHF")
    assert core.wf_passed("meanrev", "GBPUSD", "1d") and not core.wf_passed("meanrev", "GBPUSD", "1h")

def test_lot_and_guards():
    assert core.lot_size(9.72, 1, 3, 180, 10)[0] == 0          # tiny account: skipped
    lots, risk = core.lot_size(1000, 1, 3, 20, 10); assert lots == 0.05 and risk == 10.0
    st = {}; core.update_day(st, 1000)
    assert core.guard_reasons(st, 1000) == []
    assert any("daily loss" in w for w in core.guard_reasons(st, 969))
    assert any("kill switch" in w for w in core.guard_reasons(st, 849))
    st["day_trades"] = 3; assert any("max 3" in w for w in core.guard_reasons(st, 1000))
    assert core.guard_reasons({"peak": 1, "day_start": 1}, 1, stopped=True)
    assert core.guard_reasons({"peak": 1, "day_start": 1}, 1, live=True, accepted=False)

def test_locks():
    if not DATA: return
    b = {"GBPUSD": bars_of("GBPUSD")}
    w = core.live_locks(True, 9.72, "meanrev", "1d", ["GBPUSD"], core.LIVE_PHRASE, b)
    assert w and "balance too small" in w[0], w
    assert core.live_locks(True, 5000, "meanrev", "1d", ["GBPUSD"], core.LIVE_PHRASE, b) == []
    assert core.live_locks(True, 5000, "meanrev", "1d", ["GBPUSD"], "i accept", b)
    assert core.live_locks(False, None, "meanrev", "1d", ["GBPUSD"], core.LIVE_PHRASE, b)
    assert core.live_locks(True, 5000, "trend", "1d", ["GBPUSD"], core.LIVE_PHRASE, b)
    assert core.live_locks(True, 5000, "meanrev", "1d", ["EURUSD"], core.LIVE_PHRASE, {"EURUSD": bars_of("EURUSD")})
    assert core.live_locks(True, 5000, "meanrev", "1h", ["GBPUSD"], core.LIVE_PHRASE, b)
    assert core.live_locks(True, 5000, "meanrev", "1d", ["EURGBP"], core.LIVE_PHRASE, b)   # pass, but cross pair
    assert core.live_locks(True, 5000, "trend", "1d", ["XAUUSD"], core.LIVE_PHRASE, b)

def test_explain():
    if not DATA: return
    for s in core.MAIN_PAIRS:
        for m in core.MODES:
            for tf in ("1d", "1h"):
                e = core.explain(m, s, tf, bars_of(s, tf))
                assert e["title"] and len(e["text"]) > 30, e
    print("  e.g.", core.explain("meanrev", "GBPUSD", "1d", bars_of("GBPUSD"))["text"][:220])

def test_practice_replay():
    """Replay the daily GBPUSD history bar by bar through the practice engine (follow signals ON)."""
    if not DATA: return
    for mode, sym, tf in (("meanrev", "GBPUSD", "1d"), ("grid", "USDJPY", "1h"), ("trend", "EURUSD", "1h"), ("auto", "GBPUSD", "1d")):
        bars = bars_of(sym, tf); ps = core.new_practice(); n_ev = 0
        start = max(core.WARMUP, len(bars) - 700)
        for k in range(start, len(bars) - 1):
            now = datetime.fromtimestamp(bars[k + 1]["t"], timezone.utc)
            ev = core.practice_step(ps, mode, tf, [sym], {sym: {"price": bars[k + 1]["o"], "bars": bars[:k + 1]}}, now=now)
            n_ev += len(ev)
            assert ps["day_trades"] <= core.RISK["max_trades_per_day"]
            for pos in ps["positions"].values():   # never martingale: every level same lot
                assert len({round(l, 2) for _, l in pos["fills"]}) == 1
                assert len(pos["fills"]) <= 3
        sm = core.practice_summary(ps, {sym: bars[-1]["c"]})
        print("  practice %-7s %s %s: %d trades, win %d%%, P/L %+.2f, killed=%s" % (mode, sym, tf, sm["trades"], sm["win_rate"], sm["pl_total"], ps["killed"]))
        assert sm["trades"] > 0
        # STOP and follow-off open nothing new
        ps2 = core.new_practice()
        for k in range(start, start + 200):
            core.practice_step(ps2, mode, tf, [sym], {sym: {"price": bars[k + 1]["o"], "bars": bars[:k + 1]}},
                               now=datetime.fromtimestamp(bars[k + 1]["t"], timezone.utc), stopped=True)
        assert not ps2["history"] and not ps2["positions"]

def test_vault():
    d = tempfile.mkdtemp(); v = core.Vault(d)
    assert not v.has_pin()
    for bad in ("12", "1111", "1234", "abc"):
        assert core.pin_rule(bad), bad
    v.set_pin("4826"); v.put("token", "tok-SECRET-123"); v.put("account", "acc-1")
    raw = open(os.path.join(d, "secure.json")).read()
    assert "tok-SECRET" not in raw and "4826" not in raw
    v2 = core.Vault(d); assert v2.get("token") == ""
    ok, msg = v2.unlock("0000"); assert not ok
    ok, msg = v2.unlock("4826"); assert ok and v2.get("token") == "tok-SECRET-123"
    v2.set_pin("my secret pass"); assert v2.get("token") == "tok-SECRET-123"
    v3 = core.Vault(d)
    for _ in range(5): v3.unlock("9999")
    assert v3.wait_seconds() > 0 and not v3.unlock("my secret pass")[0]
    v3.forget(); assert not core.Vault(d).has_pin()
    assert core.mask("abcdefghijklmnopqrstuvwxyz").startswith("abcd") and "mnop" not in core.mask("abcdefghijklmnopqrstuvwxyz")

def test_host_guard():
    ok = core.metaapi_host_ok
    assert ok("https://mt-client-api-v1.new-york.agiliumtrade.ai/users/current/accounts/x")
    assert ok("https://mt-provisioning-api-v1.agiliumtrade.ai/users/current/accounts/x")
    for bad in ("http://mt-client-api-v1.new-york.agiliumtrade.ai/x", "https://agiliumtrade.ai.evil.com/x",
                "https://evilagiliumtrade.ai/x", "https://query1.finance.yahoo.com/x", "https://a.agiliumtrade.ai@evil.com/x"):
        assert not ok(bad), bad
    try:
        core.http_json("https://example.com/", token="t"); raise SystemExit("token sent to a non-MetaApi host")
    except core.MetaApiError:
        pass
    try:
        core.MetaApi("t", "../../x"); raise SystemExit("bad account id accepted")
    except core.MetaApiError:
        pass

def test_fake_live():
    """live_step / account_status against a fake MetaApi: guards, max trades, no order when blocked."""
    if not DATA: return
    bars = bars_of("GBPUSD")
    # find a bar index where meanrev fires
    p = core.params_for("meanrev", "GBPUSD", "1d"); I = core.indicators(bars, p)
    idx = [i for i in range(300, len(bars)) if core.entry_signal("meanrev", I, i, p)][-1]
    class Fake:
        orders = []
        def account(self): return {"balance": 5000, "equity": 5000, "currency": "USD"}
        def positions(self): return []
        def deals(self, a, b): return []
        def bars(self, s, tf): return bars[:idx + 1]
        def order(self, *a): self.orders.append(a); return {"ok": 1}
    f = Fake(); st = {}
    ev = core.live_step(f, st, "meanrev", "1d", ["GBPUSD"], stopped=False, accepted=True)
    assert len(f.orders) == 1 and ev, ev
    lots = f.orders[0][2]; assert 0.01 <= lots <= 5, lots
    core.live_step(f, st, "meanrev", "1d", ["GBPUSD"], stopped=False, accepted=True)
    assert len(f.orders) == 1        # same bar: no repeat
    st2 = {}; f.orders = []
    core.live_step(f, st2, "meanrev", "1d", ["GBPUSD"], stopped=True, accepted=True); assert not f.orders
    core.live_step(f, {}, "meanrev", "1d", ["GBPUSD"], stopped=False, accepted=False); assert not f.orders
    core.live_step(f, {}, "trend", "1d", ["GBPUSD"], stopped=False, accepted=True); assert not f.orders
    s = core.account_status(f, {}, "meanrev", "1d", ["GBPUSD"], False, True)
    assert s["why"] == [] and s["today"] == 0, s["why"]

def test_news_and_sessions():
    from datetime import datetime, timezone
    t = core.parse_ff_date("2026-11-27T08:30:00-05:00")
    assert t == datetime(2026, 11, 27, 13, 30, tzinfo=timezone.utc)
    assert core.parse_ff_date("Fri 2026-11-27 4:30 PM EAT (UTC+03:00)") == t
    assert core.parse_ff_date("Mon 2026-11-23 12:05 AM EAT (UTC+03:00)") == datetime(2026, 11, 22, 21, 5, tzinfo=timezone.utc)
    ev = core.parse_news([{"title": "Non-Farm Employment Change", "country": "USD", "date": "2026-11-27T08:30:00-05:00", "impact": "High"},
                          {"title": "BOE speech", "country": "GBP", "date": "2026-11-27T12:00:00-05:00", "impact": "Medium"}])
    near = datetime(2026, 11, 27, 12, 45, tzinfo=timezone.utc)
    assert core.news_block("EURUSD", ev, near) and core.news_block("USDJPY", ev, near)
    assert core.news_block("EURUSD", ev, datetime(2026, 11, 27, 14, 31, tzinfo=timezone.utc)) is None
    assert core.news_block("EURUSD", ev, datetime(2026, 11, 27, 12, 29, tzinfo=timezone.utc)) is None
    assert core.news_block("EURUSD", None, near)          # feed down -> safety block
    assert core.news_block("GBPJPY", ev, near) is None     # medium impact / other currencies
    assert [e["title"] for e in core.upcoming_high(ev, near)] == ["Non-Farm Employment Change"]
    # sessions: Wed 26 Nov 2026 13:45 UTC -> London + New York open; Saturday -> all closed
    s = dict((c, o) for c, o, _, _ in core.sessions(datetime(2026, 11, 26, 13, 45, tzinfo=timezone.utc)))
    assert s == {"Sydney": False, "Tokyo": False, "London": True, "New York": True}, s
    s = dict((c, o) for c, o, _, _ in core.sessions(datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)))
    assert s["Tokyo"] and s["Sydney"] and not s["London"], s
    assert not any(o for _, o, _, _ in core.sessions(datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)))
    assert core.utc_offset_hours("London", datetime(2026, 7, 1, tzinfo=timezone.utc)) == 1
    assert core.utc_offset_hours("New York", datetime(2026, 7, 1, tzinfo=timezone.utc)) == -4
    assert core.utc_offset_hours("Sydney", datetime(2026, 7, 1, tzinfo=timezone.utc)) == 10
    assert core.utc_offset_hours("Sydney", datetime(2026, 12, 1, tzinfo=timezone.utc)) == 11
    # the practice engine skips a signal inside the news window and takes it after
    if DATA:
        bars = bars_of("GBPUSD"); p = core.params_for("meanrev", "GBPUSD", "1d"); I = core.indicators(bars, p)
        idx = [i for i in range(300, len(bars)) if core.entry_signal("meanrev", I, i, p)][-1]
        tt = bars[idx]["t"] + 86400 + 3600
        nev = [{"t": tt + 600, "cur": "GBP", "title": "CPI y/y", "impact": "High"}]
        ps = core.new_practice(); mk = {"GBPUSD": {"price": bars[idx]["c"], "bars": bars[:idx + 1]}}
        e1 = core.practice_step(ps, "meanrev", "1d", ["GBPUSD"], mk, now=datetime.fromtimestamp(tt, timezone.utc), news=nev)
        assert not ps["positions"] and "news" in e1[0], e1
        core.practice_step(ps, "meanrev", "1d", ["GBPUSD"], mk, now=datetime.fromtimestamp(tt + 7300, timezone.utc), news=nev)
        assert ps["positions"], "trade not taken after the news window"

def test_live_prices():
    if "--live" not in sys.argv: return
    pr = core.public_prices(); print("  live prices", pr); assert all(pr.values()), pr
    for s in core.MAIN_PAIRS:
        d = core.yahoo_chart(s, "1d"); assert len(d["bars"]) > 250
        print("  ", s, core.explain("meanrev", s, "1d", d["bars"])["title"])
    ev, note = core.fetch_news(); print("  news feed:", "ok %d events" % len(ev) if ev else note)

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f(); print("ok", k)
    print("ALL OK")
