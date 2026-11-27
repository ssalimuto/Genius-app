"""Cloud runner: one pass, quiet public logs (no balances, ids or tokens), state kept, dry run unless allowed."""
import io, json, os, sys, tempfile, contextlib, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(HERE, "..", "..", "cloud_bot", "safe_mt5_bot.py")
DATA = os.environ.get("PROFITS_DATA") or os.path.join(HERE, "data")
os.environ["BOT_QUIET"] = "1"
os.environ["BOT_STATE_PATH"] = os.path.join(tempfile.mkdtemp(), "state.json")
spec = importlib.util.spec_from_file_location("bot", BOT); bot = importlib.util.module_from_spec(spec); spec.loader.exec_module(bot)
cfg = bot.load_config()
assert cfg["mode"] == "meanrev" and cfg["timeframe"] == "1d" and cfg["symbols"] == ["GBPUSD"] and not cfg["i_accept_risk"]

def run(live=False):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        bot.once(cfg, live, cfg["mode"])
    return out.getvalue()

for k in ("METAAPI_TOKEN", "METAAPI_ACCOUNT_ID"):
    os.environ.pop(k, None)
o = run(); assert "skipped: secrets not set" in o, o
os.environ["METAAPI_TOKEN"] = "TOKEN-abc-SECRET"; os.environ["METAAPI_ACCOUNT_ID"] = "acc-12345-SECRET"
bars = bot.load_yahoo(os.path.join(DATA, "GBPUSD_1d.json"))
bars = [{"o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"], "t": b["t"]} for b in bars]
p = bot.validated(cfg, "meanrev", "GBPUSD"); assert p
I = bot.indicators(bars, p)
idx = [i for i in range(300, len(bars)) if bot.entry_signal("meanrev", I, i, p)][-1]
orders = []
class Fake:
    def __init__(self, cfg): pass
    def account(self): return {"balance": 98765.43, "equity": 98765.43, "currency": "USD"}
    def positions(self): return []
    def candles(self, *a): return [{"open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "time": b["t"]} for b in bars[:idx + 2]]
    def order(self, *a): orders.append(a)
bot.MetaApi = Fake
bot.load_news = lambda st: []          # calendar loaded, nothing near
o1 = run(live=False)
assert "signal: dry run" in o1 and not orders, o1
for secret in ("98765", "SECRET", "acc-12345", "TOKEN"):
    assert secret not in o1, (secret, o1)
st = json.load(open(os.environ["BOT_STATE_PATH"])); assert st["last_bar"]["GBPUSD"] == bars[idx]["t"]
o2 = run(live=False); assert "signal" not in o2, o2         # same bar: nothing new
# live needs i_accept_risk (repo variable LIVE=true) -> without it, still dry run
os.remove(os.environ["BOT_STATE_PATH"]); o3 = run(live=True); assert not orders and "dry run" in o3, o3
cfg["i_accept_risk"] = True
os.remove(os.environ["BOT_STATE_PATH"]); o4 = run(live=True); assert len(orders) == 1 and "live order sent" in o4, o4
# news window blocks; STOP blocks
bot.load_news = lambda st: None
os.remove(os.environ["BOT_STATE_PATH"]); orders.clear(); o5 = run(live=True); assert not orders and "news" in o5, o5
os.environ["BOT_STOP"] = "true"; o6 = run(live=True); assert "STOP" in o6 or "stopped" in o6; os.environ.pop("BOT_STOP")
print(o1.strip()); print("CLOUD BOT OK")
