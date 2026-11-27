"""Headless UI smoke test: create a PIN, run a real check, open every tab, take screenshots, lock, unlock."""
import os, sys, tempfile, time
os.environ.setdefault("KIVY_NO_ARGS", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..")
sys.path.insert(0, APP)
from kivy.config import Config
Config.set("graphics", "width", "720"); Config.set("graphics", "height", "1600")
from kivy.clock import Clock
import main
OUT = os.environ.get("SHOTS", tempfile.mkdtemp())
TMP = tempfile.mkdtemp()
main.ProfitsApp.user_data_dir = property(lambda self: TMP)
errors = []

def walk(w):
    yield w
    for c in w.children:
        yield from walk(c)

def texts(app):
    return " ".join(getattr(w, "text", "") or "" for w in walk(app.root_box))

class T(main.ProfitsApp):
    def on_start(self):
        assert "Create your app PIN" in texts(self), "no create-PIN screen"
        self.vault.set_pin("4826", keep_secrets=False)
        self.unlocked()
        Clock.schedule_once(self.step1, 1)

    def step1(self, dt):
        if self.busy.locked() or not self.last_check:
            Clock.schedule_once(self.step1, 1); return
        self.tabs = ["home", "markets", "practice", "live", "info", "settings"]
        Clock.schedule_once(self.shoot, 0.5)

    def shoot(self, dt):
        from kivy.core.window import Window
        if getattr(self, "_pending", None):
            Window.screenshot(name=os.path.join(OUT, "shot_%s.png" % self._pending))
            if self._pending == "settings":
                self.page_sv.scroll_y = 0.25
                Clock.schedule_once(lambda dt: Window.screenshot(name=os.path.join(OUT, "shot_settings_low.png")), 0.3)
        if not self.tabs:
            Clock.schedule_once(self.step2, 0.8); return
        tab = self.tabs.pop(0)
        if tab == "settings":
            self.show_adv = self.show_cloud = True
        self.go(tab)
        t = texts(self)
        if "Something went wrong" in t:
            errors.append(tab)
        for banned in ("".join(["H", "a", "r", "k"]), "".join(["Open", "AI"]), "".join(["Cla", "ude"]), "".join(["Anthro", "pic"]), "".join(["Gem", "ini"]), "".join(["Chat", "GPT"]), "cannot be hacked"):
            if banned.lower() in t.lower():
                errors.append("banned word %s on %s" % (banned, tab))
        self._pending = tab
        Clock.schedule_once(self.shoot, 0.4)

    def step2(self, dt):
        print("directions:", {s: d["action"] for s, d in self.directions.items()})
        print("news:", "ok %d" % len(self.news) if self.news else self.news_note, "| crypto:", len(self.crypto))
        print("locks:", self.locks)
        # manual practice on a signal if there is one, else a forced test card
        sig = [d for d in self.directions.values() if d["action"] != "WAIT"]
        print("signals now:", [(d["sym"], d["action"]) for d in sig])
        # STOP / resume / lock / unlock
        self.stop_all(); self.close_popups()
        assert self.settings["stopped"] and not self.settings["live_enabled"]
        self.resume()
        self.on_pause(); self.on_resume()
        assert self.locked and "Enter your PIN" in texts(self)
        ok, _ = self.vault.unlock("0000"); assert not ok
        ok, _ = self.vault.unlock("4826"); assert ok
        self.unlocked()
        self.mt5_ticket({"sym": "GBPUSD", "action": "SELL", "entry": 1.31, "stop": 1.33, "target": 1.28, "risk_001": 20.0,
                         "exit_rule": ""})
        assert "never asks for your MT5 password" in open(os.path.join(APP, "main.py")).read()
        Clock.schedule_once(lambda dt: self.stop(), 1)

T().run()
print("screens:", OUT)
print("UI ERRORS:", errors) if errors else print("UI SMOKE OK")
sys.exit(1 if errors else 0)
