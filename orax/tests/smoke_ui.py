"""Headless cold-start + UI smoke test for Orax.
Local: python tests/smoke_ui.py --mock        (mock GL window, no display)
CI:    xvfb-run -a python tests/smoke_ui.py   (real SDL2 window on a virtual display)
Checks: first frame before any network call, every tab and More page opens, chat tools answer in plain words with
no raw errors and no vendor names, a UI error after start is caught and the app keeps going."""
import os
import socket
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(HERE)
sys.path.insert(0, APP_DIR)
sys.path.insert(0, HERE)
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
if "--mock" in sys.argv:
    __import__("mockwin")
T0 = time.time()

NET = []                           # (time, what) for every network attempt
_real_conn = socket.create_connection
_real_getaddr = socket.getaddrinfo


def _spy_conn(*a, **k):
    NET.append((time.time(), "connect %s" % (a[0],)))
    return _real_conn(*a, **k)


def _spy_getaddr(*a, **k):
    NET.append((time.time(), "dns %s" % (a[0],)))
    return _real_getaddr(*a, **k)


socket.create_connection = _spy_conn
socket.getaddrinfo = _spy_getaddr

from kivy.clock import Clock  # noqa: E402
import core  # noqa: E402
import orax_app  # noqa: E402

LIVE = "--live" in sys.argv
if not LIVE:
    core.OFFLINE["force"] = True
TMP = tempfile.mkdtemp(prefix="orax_ui_")
TXT = os.path.join(TMP, "notes.txt")
open(TXT, "w").write("Shop list: phone covers 5000 each, chargers 15000.")
os.environ["ORAX_TEST_FILE"] = TXT
orax_app.OraxApp.user_data_dir = property(lambda self: TMP)
ERR = []
BANNED = ["".join(x) for x in (["H", "ark"], ["Open", "AI"], ["Anthro", "pic"], ["Cla", "ude"], ["Chat", "GPT"],
                                ["Lla", "ma"], ["Mis", "tral"], ["Deep", "Seek"], ["Polli", "nations"])]
RAW = ("Traceback", "Exception", "Errno", "NoneType", "object has no attribute", "HTTPError", "URLError", "jnius")


def walk(w):
    yield w
    for c in w.children:
        yield from walk(c)


def texts(app):
    from kivy.core.window import Window
    return " ".join(str(getattr(w, "text", "") or "") for w in walk(Window))


def scan(app, where):
    t = texts(app)
    for b in BANNED:
        if b.lower() in t.lower():
            ERR.append("banned name %r on %s" % (b, where))
    for r in RAW:
        if r in t:
            ERR.append("raw error text %r on %s" % (r, where))
    # the two key labels are the only allowed vendor words, and only in Settings
    for v in ("Gem" + "ini", "Gr" + "oq"):
        if v in t and where != "settings":
            ERR.append("%s visible outside Settings (%s)" % (v, where))


class T(orax_app.OraxApp):
    def _after_first_frame(self, dt):
        self.t_frame = time.time()
        before = [n for n in NET if n[0] < self.t_frame]
        if before:
            ERR.append("network before first frame: %s" % before[:3])
        print("first frame after %.2f s (process start to frame)" % (self.t_frame - T0))
        super()._after_first_frame(dt)
        self.steps = [
            lambda: self.go("chat"),
            lambda: self.handle("help"),
            lambda: self.handle("open whatsapp"),
            lambda: self.handle("open tiktok"),
            lambda: self.handle("install fiverr"),
            lambda: self.handle("download https://example.com/file.pdf"),
            lambda: self.handle("remind me to call the shop in 5 minutes"),
            lambda: self.handle("remind me to call"),
            lambda: self.handle("2+2*10"),
            lambda: self.handle("100 usd to ugx"),
            lambda: self.handle("5 km to miles"),
            lambda: self.handle("remember I study at Mityana SS"),
            lambda: self.handle("I can build Android apps with Kivy"),
            lambda: self.handle("that's wrong, it's Mityana"),
            lambda: self.handle("you're wrong"),
            lambda: self.handle("The right answer is Gulu"),
            lambda: self.handle("is this a scam: pay registration fee 50000 to my momo number 0772000000 guaranteed"),
            lambda: self.handle("call 0772 123456"),
            lambda: self.handle("apps"),
            lambda: self.handle("read a file"),
            lambda: self.handle('teach orax: {"name": "Python jobs", "triggers": ["python jobs now"], '
                                '"steps": [{"tool": "jobs", "arg": "python"}]}'),
            lambda: self.handle("teach orax: {\"name\": \"bad\", \"triggers\": [\"zzz\"], \"steps\": [{\"tool\": \"shell\"}]}"),
            lambda: self.handle("draft a whatsapp message to a shop owner offering a catalogue setup"),
            lambda: self.handle("what is the capital of Uganda"),
            lambda: self.handle("search best laptops for coding"),
            lambda: self.go("finder"),
            lambda: self.edit_skills_test(),
            lambda: self.go("tasks"),
            lambda: self.plan_it("Sell phone covers at school", "", None),
            "wait_plan",
            lambda: self.go("tasks"),
            lambda: self.toggle_first_step(),
            lambda: self.go("money"),
            lambda: self.money_test(),
            lambda: self.go("scam"),
            lambda: self.scam_test(),
            lambda: self.go("more"),
            lambda: (self._sub(self.show_knows), scan(self, "knows")),
            lambda: (self._sub(self.show_skills), scan(self, "skills")),
            lambda: (self._sub(self.show_settings), scan(self, "settings")),
            lambda: self.settings_toggle_test(),
            lambda: (self._sub(self.show_about), scan(self, "about")),
            lambda: self.about_check(),
            lambda: self._on_key(None, 27),
            lambda: self.ui_error_test(),
            lambda: self.go("chat"),
            lambda: self.reminder_fire_test(),
            lambda: self.final_checks(),
        ]
        Clock.schedule_once(self.next_step, 0.5)

    def next_step(self, dt):
        if not self.steps:
            Clock.schedule_once(lambda dt: self.stop(), 0.5)
            return
        fn = self.steps.pop(0)
        if fn == "wait_plan":
            self._waited = getattr(self, "_waited", 0) + 1
            if not self.tasks.plans and self._waited < 120:
                self.steps.insert(0, fn)
                Clock.schedule_once(self.next_step, 0.5)
                return
            fn = (lambda: None)
        try:
            fn()
        except Exception as e:
            import traceback
            ERR.append("step failed: %s" % traceback.format_exc()[-600:])
            del e
        where = self.current
        if self.current == "more" and "Your own AI keys" in texts(self):
            where = "settings"
        scan(self, where)
        Clock.schedule_once(self.next_step, 1.2 if LIVE else 0.35)

    def edit_skills_test(self):
        self.edit_skills()
        from kivy.core.window import Window
        pops = [w for w in Window.children if w.__class__.__name__ == "Popup"]
        if not pops:
            ERR.append("skills popup did not open")
        for p in pops:
            p.dismiss()

    def toggle_first_step(self):
        if not self.tasks.plans:
            ERR.append("plan was not saved")
            return
        p = self.tasks.plans[0]
        if len(p["steps"]) < 3:
            ERR.append("offline plan too short")
        self.tasks.toggle(p["id"], 0)
        self.go("tasks")
        if "[x]" not in texts(self):
            ERR.append("step toggle not shown")

    def money_test(self):
        self.earnings.add(50000, "earn", "Fiverr")
        self.earnings.add(8000, "spend", "Data")
        self.go("money")
        if "UGX 42,000" not in texts(self):
            ERR.append("money net not shown")

    def scam_test(self):
        self.scam_in.text = "Send me the OTP code and pay activation fee"
        self.scam_run()
        if "High risk" not in texts(self):
            ERR.append("scam check not high")

    def settings_toggle_test(self):
        self.settings.set("lang", "lg")
        self.settings.set("low_data", True)
        self.show_settings()
        if "Luganda replies: ON" not in texts(self) or "Low-data mode: ON" not in texts(self):
            ERR.append("settings toggles not shown")
        self.settings.set("low_data", False)

    def about_check(self):
        t = texts(self)
        for need in (orax_app.ABOUT_TEXT, "can't sign in", "while the app is open", "Made by Ssali Muto",
                     "Remote OK"):
            if need not in t:
                ERR.append("About missing: %r" % need)

    def ui_error_test(self):
        def boom(dt):
            raise RuntimeError("test UI error after start")
        Clock.schedule_once(boom, 0)

    def reminder_fire_test(self):
        self.tasks.add_reminder("test reminder", time.time() - 1)
        self.tick()
        from kivy.core.window import Window
        pops = [w for w in Window.children if w.__class__.__name__ == "Popup"]
        if not pops:
            ERR.append("reminder popup did not show")
        for p in pops:
            p.dismiss()

    def final_checks(self):
        t = texts(self)
        calls = orax_app.Droid.calls
        kinds = [c[0] for c in calls]
        for need in ("launch", "view", "dial"):
            if need not in kinds:
                ERR.append("Droid.%s never called (%s)" % (need, kinds))
        if not any(c[0] == "view" and "market://details?id=com.zhiliaoapp.musically" in c[1] for c in calls):
            ERR.append("missing app did not open its Play Store page")
        if not any(s["name"] == "Python jobs" for s in self.skills.items) and "Save skill" not in t:
            ERR.append("teach skill preview missing")
        if not any(f["kind"] == "correction" and "Gulu" in f["text"] for f in self.memory.facts):
            ERR.append("follow-up correction not saved")
        if not any(f["kind"] == "skill" for f in self.memory.facts):
            ERR.append("skill fact not learned")
        if not self.tasks.reminders:
            ERR.append("reminder not saved")
        if not LIVE and "Check your internet" not in t and "couldn't" not in t:
            ERR.append("offline answers not plain")
        print("Droid calls:", calls[:12])
        if os.environ.get("ORAX_SHOW_CHAT"):
            from kivy.uix.label import Label
            for w in reversed(list(walk(self.pages["chat"]))):
                if isinstance(w, Label) and w.text and len(w.text) > 2:
                    print("  |", w.text.replace("\n", " / ")[:160])


if __name__ == "__main__":
    T().run()
    log = os.path.join(TMP, "orax_log.txt")
    if os.path.exists(log):
        caught = "test UI error after start" in open(log).read()
        if not caught:
            ERR.append("UI error was not caught by the handler")
    else:
        ERR.append("no private log written")
    if ERR:
        print("SMOKE FAIL")
        for e in ERR:
            print(" -", e)
        sys.exit(1)
    print("SMOKE PASS (%s)" % ("live" if LIVE else "offline"))
