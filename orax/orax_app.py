"""Orax: find and plan work. Made by Ssali Muto.
Screen code. Kept light for low-RAM phones: only Kivy and the standard library are imported at start; everything
else (job lists, rates, app lists, Android helpers) loads after the first frame."""
import os
import re
import threading
import time
import traceback

from kivy.app import App
from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget

import core

APP_NAME = "Orax"
VERSION = "1.0.0"
BUILD_NUMBER = "dev"
BUILD_COMMIT = "dev"
CREDIT = "Made by Ssali Muto"
ABOUT_TEXT = ("Orax helps you find and plan work. Earnings depend on your effort; no app can promise income. "
              "Made by Ssali Muto")
ABOUT_LIMITS = ("What Orax can't do: it can't sign in to accounts, pay for anything, or click through websites "
                "for you. It opens apps, links and the Play Store, and you finish there.\n\n"
                "Reminders work while the app is open. If you close Orax, it can't remind you.")
OOPS = "That didn't work. Orax kept going; please try again."
JOBS_CREDIT = "Jobs from Remote OK (remoteok.com) and Remotive. Tap a job to open the full post."

NAVY = (0.043, 0.082, 0.188, 1)
NAVY2 = (0.075, 0.125, 0.255, 1)
NAVY3 = (0.11, 0.17, 0.32, 1)
GOLD = (0.83, 0.65, 0.22, 1)
GOLD_DIM = (0.55, 0.44, 0.18, 1)
WHITE = (0.95, 0.95, 0.97, 1)
MUTED = (0.70, 0.74, 0.82, 1)
RED = (0.86, 0.33, 0.30, 1)
ORANGE = (0.93, 0.62, 0.25, 1)
GREEN = (0.36, 0.74, 0.47, 1)

IS_ANDROID = "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ


# ------------------------------------------------------------------ errors never show raw
class _Guard(ExceptionHandler):
    def handle_exception(self, inst):
        if isinstance(inst, (KeyboardInterrupt, SystemExit)):
            return ExceptionManager.RAISE
        app = App.get_running_app()
        core.log("UI error: " + "".join(traceback.format_exception(type(inst), inst, inst.__traceback__))[-1500:])
        if app is not None and not getattr(app, "first_frame", False):
            return ExceptionManager.RAISE          # before the first frame: let main.py show the crash screen
        try:
            if app is not None:
                app.toast(OOPS)
        except Exception:
            pass
        return ExceptionManager.PASS


def bg(fn, done=None):
    """Runs fn in a thread; done(result) runs on the main thread. Errors are logged, done(None) is called."""
    def run():
        try:
            r = fn()
        except Exception as e:
            core.log("bg %s: %s" % (getattr(fn, "__name__", "fn"), type(e).__name__))
            r = None
        if done:
            Clock.schedule_once(lambda dt: done(r), 0)
    threading.Thread(target=run, daemon=True).start()


# ------------------------------------------------------------------ Android helpers (all fail softly)
class Droid:
    calls = []          # desktop/test record

    @staticmethod
    def _act():
        from jnius import autoclass
        return autoclass("org.kivy.android.PythonActivity").mActivity

    @staticmethod
    def _intent():
        from jnius import autoclass
        return autoclass("android.content.Intent")

    @classmethod
    def _start(cls, intent, new_task=True):
        I = cls._intent()
        if new_task:
            intent.addFlags(I.FLAG_ACTIVITY_NEW_TASK)
        cls._act().startActivity(intent)

    @classmethod
    def view(cls, uri):
        if not IS_ANDROID:
            cls.calls.append(("view", uri))
            return True
        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            I = cls._intent()
            cls._start(I(I.ACTION_VIEW, Uri.parse(uri)))
            return True
        except Exception as e:
            core.log("view: %s" % type(e).__name__)
            return False

    @classmethod
    def open_store(cls, pkg=None, query=None):
        for u in core.store_links(pkg, query):
            if cls.view(u):
                return True
        return False

    @classmethod
    def installed_apps(cls):
        if not IS_ANDROID:
            return [("WhatsApp", "com.whatsapp"), ("Calculator", "com.android.calculator2"), ("Chrome", "com.android.chrome")]
        out = []
        try:
            I = cls._intent()
            act = cls._act()
            pm = act.getPackageManager()
            i = I(I.ACTION_MAIN)
            i.addCategory(I.CATEGORY_LAUNCHER)
            lst = pm.queryIntentActivities(i, 0)
            for k in range(lst.size()):
                ri = lst.get(k)
                pkg = ri.activityInfo.packageName
                try:
                    label = str(ri.loadLabel(pm))
                except Exception:
                    label = pkg
                if pkg != act.getPackageName():
                    out.append((label, pkg))
        except Exception as e:
            core.log("apps: %s" % type(e).__name__)
        return out

    @classmethod
    def launch(cls, pkg):
        if not IS_ANDROID:
            cls.calls.append(("launch", pkg))
            return True
        try:
            it = cls._act().getPackageManager().getLaunchIntentForPackage(pkg)
            if it is None:
                return False
            cls._start(it)
            return True
        except Exception as e:
            core.log("launch: %s" % type(e).__name__)
            return False

    @classmethod
    def share(cls, text, subject="", package=None):
        if not IS_ANDROID:
            cls.calls.append(("share", package, subject, text[:40]))
            return True
        try:
            I = cls._intent()
            i = I(I.ACTION_SEND)
            i.setType("text/plain")
            i.putExtra(I.EXTRA_TEXT, text)
            if subject:
                i.putExtra(I.EXTRA_SUBJECT, subject)
            if package:
                i.setPackage(package)
                try:
                    cls._start(i)
                    return True
                except Exception:
                    return False
            ch = I.createChooser(i, "Send with")
            cls._start(ch)
            return True
        except Exception as e:
            core.log("share: %s" % type(e).__name__)
            return False

    @classmethod
    def mailto(cls, subject, body):
        import urllib.parse
        uri = "mailto:?subject=%s&body=%s" % (urllib.parse.quote(subject or ""), urllib.parse.quote(body or ""))
        if not IS_ANDROID:
            cls.calls.append(("mailto", uri[:60]))
            return True
        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            I = cls._intent()
            cls._start(I(I.ACTION_SENDTO, Uri.parse(uri)))
            return True
        except Exception as e:
            core.log("mailto: %s" % type(e).__name__)
            return cls.share(body, subject)

    @classmethod
    def dial(cls, number):
        if not IS_ANDROID:
            cls.calls.append(("dial", number))
            return True
        try:
            from jnius import autoclass
            Uri = autoclass("android.net.Uri")
            I = cls._intent()
            cls._start(I(I.ACTION_DIAL, Uri.parse("tel:" + number)))
            return True
        except Exception as e:
            core.log("dial: %s" % type(e).__name__)
            return False

    @staticmethod
    def download_dir():
        for base in ("/storage/emulated/0/Download", "/sdcard/Download"):
            d = os.path.join(base, "Orax")
            try:
                os.makedirs(d, exist_ok=True)
                t = os.path.join(d, ".w")
                open(t, "w").close()
                os.remove(t)
                return d, "Download/Orax"
            except Exception:
                continue
        d = os.path.join(App.get_running_app().user_data_dir, "downloads")
        return d, "Orax's own storage"


# ------------------------------------------------------------------ small widgets
def paint(w, color, radius=10):
    with w.canvas.before:
        c = Color(*color)
        r = RoundedRectangle(pos=w.pos, size=w.size, radius=[dp(radius)])
    w.bind(pos=lambda *_: setattr(r, "pos", w.pos), size=lambda *_: setattr(r, "size", w.size))
    w._bgc = c
    return c


class WLabel(Label):
    """Label that wraps to its width and grows in height."""
    def __init__(self, **kw):
        kw.setdefault("color", WHITE)
        kw.setdefault("font_size", sp(15))
        kw.setdefault("halign", "left")
        kw.setdefault("valign", "top")
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self.bind(width=self._w, texture_size=self._h)

    def _w(self, *_):
        self.text_size = (self.width, None)

    def _h(self, *_):
        self.height = max(self.texture_size[1], dp(18))


class Btn(Button):
    def __init__(self, text="", primary=False, small=False, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(36) if small else dp(44))
        kw.setdefault("font_size", sp(13) if small else sp(15))
        super().__init__(text=text, background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=NAVY if primary else GOLD, **kw)
        self._c = paint(self, GOLD if primary else NAVY3, 9)
        self.bind(state=self._st)

    def _st(self, *_):
        self._c.a = 0.7 if self.state == "down" else 1


class Field(TextInput):
    """Text box with the phone keyboard's own suggestions off (they doubled letters on some keyboards)."""
    def __init__(self, hint="", multiline=False, number=False, password=False, **kw):
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(44) if not multiline else dp(110))
        super().__init__(hint_text=hint, multiline=multiline, password=password,
                         input_type="number" if number else "text", keyboard_suggestions=False,
                         write_tab=False, font_size=sp(15), background_normal="", background_active="",
                         background_color=NAVY3, foreground_color=WHITE, hint_text_color=MUTED,
                         cursor_color=GOLD, padding=(dp(10), dp(11), dp(10), dp(8)), **kw)


def card(spacing=6, pad=12, color=NAVY2):
    b = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(spacing), padding=dp(pad))
    b.bind(minimum_height=b.setter("height"))
    paint(b, color, 12)
    return b


def row(height=44, spacing=6):
    return BoxLayout(size_hint_y=None, height=dp(height), spacing=dp(spacing))


def title_label(text, size=18, color=GOLD):
    return WLabel(text=text, font_size=sp(size), bold=True, color=color)


class Page(BoxLayout):
    """A scrolling page; add content to .box."""
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.sv = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=GOLD_DIM)
        self.box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(10),
                             padding=(dp(12), dp(10), dp(12), dp(20)))
        self.box.bind(minimum_height=self.box.setter("height"))
        self.sv.add_widget(self.box)
        self.add_widget(self.sv)

    def clear(self):
        self.box.clear_widgets()
        self.sv.scroll_y = 1


# ------------------------------------------------------------------ the app
class OraxApp(App):
    title = "Orax"
    TABS = [("finder", "Finder"), ("chat", "Chat"), ("tasks", "Tasks"), ("money", "Money"), ("scam", "Scam"),
            ("more", "More")]
    SPEECH_CODE = 7101
    FILE_CODE = 7102

    # ---------------- start (light: no network, no file scans) ----------------
    def build(self):
        if os.environ.get("ORAX_TEST_CRASH") == "build":
            raise RuntimeError("test crash in build")
        self.first_frame = False
        ExceptionManager.add_handler(_Guard())
        Window.clearcolor = NAVY
        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass
        d = self.user_data_dir
        core.LOG_FILE = os.path.join(d, "orax_log.txt")
        self.settings = core.Settings(os.path.join(d, "settings.json"))
        self.memory = core.Memory(os.path.join(d, "memory.json"))
        self.tasks = core.Tasks(os.path.join(d, "tasks.json"))
        self.earnings = core.Earnings(os.path.join(d, "earnings.json"))
        self.skills = core.Skills(os.path.join(d, "skills.json"))
        self.cache = core.AnswerCache(os.path.join(d, "answers.json"))
        self.jobcache = core.JobCache(os.path.join(d, "jobs.json"))
        self.rates = core.Rates(os.path.join(d, "rates.json"))
        self.history = []
        self.jobs = []
        self.jobs_note = ""
        self.apps_cache = (0, [])
        self.pending = None
        self.pages = {}
        self.current = None
        self.page_stack = []

        root = BoxLayout(orientation="vertical")
        head = row(52, 8)
        head.padding = (dp(14), dp(6), dp(14), dp(6))
        paint(head, NAVY, 0)
        head.add_widget(Label(text="[b]O[/b]rax", markup=True, color=GOLD, font_size=sp(22), size_hint_x=None,
                              width=dp(70), halign="left"))
        self.head_note = Label(text="find and plan work", color=MUTED, font_size=sp(12), halign="right")
        self.head_note.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.head_note.valign = "middle"
        head.add_widget(self.head_note)
        root.add_widget(head)
        self.body = BoxLayout()
        root.add_widget(self.body)
        bar = row(56, 2)
        bar.padding = (dp(4), dp(4))
        paint(bar, NAVY2, 0)
        self.tab_btns = {}
        for key, label in self.TABS:
            b = ToggleButton(text=label, group="tabs", allow_no_selection=False, font_size=sp(12.5),
                             background_normal="", background_down="", background_color=(0, 0, 0, 0), color=MUTED)
            b.bind(on_release=lambda w, k=key: self.go(k))
            bar.add_widget(b)
            self.tab_btns[key] = b
        root.add_widget(bar)
        self.root_box = root
        self.go("finder")
        Window.bind(on_keyboard=self._on_key)
        Clock.schedule_once(self._after_first_frame, 0.3)
        return root

    def _after_first_frame(self, dt):
        self.first_frame = True
        Clock.schedule_once(lambda dt: self._safe(self.load_jobs_start), 1.2)
        Clock.schedule_interval(lambda dt: self._safe(self.tick), 20)

    def _safe(self, fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            core.log("safe %s: %s" % (getattr(fn, "__name__", "fn"), traceback.format_exc()[-800:]))
            self.toast(OOPS)
            del e

    def on_pause(self):
        return True

    def on_resume(self):
        Clock.schedule_once(lambda dt: self._safe(self.tick), 0.5)

    def _on_key(self, window, key, *a):
        if key == 27:                       # Android back
            if self.page_stack:
                self.page_stack.pop()()
                return True
            if self.current != "chat" and self.current != "finder":
                self.go("finder")
                return True
        return False

    # ---------------- navigation ----------------
    def go(self, key):
        self.page_stack = []
        if key not in self.pages:
            self.pages[key] = Page()
        self.body.clear_widgets()
        self.body.add_widget(self.pages[key])
        self.current = key
        for k, b in self.tab_btns.items():
            b.state = "down" if k == key else "normal"
            b.color = GOLD if k == key else MUTED
        getattr(self, "show_" + key)(self.pages[key])

    def toast(self, text, secs=2.6):
        lab = Label(text=text, color=NAVY, font_size=sp(14), size_hint=(None, None), halign="center")
        lab.text_size = (Window.width * 0.8, None)
        lab.texture_update()
        lab.size = (Window.width * 0.84, lab.texture_size[1] + dp(20))
        lab.pos = (Window.width * 0.08, dp(80))
        paint(lab, GOLD, 10)
        Window.add_widget(lab)
        Clock.schedule_once(lambda dt: Window.remove_widget(lab), secs)

    def popup(self, title, text, buttons=None):
        box = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(10))
        sv = ScrollView(do_scroll_x=False)
        lab = WLabel(text=text)
        sv.add_widget(lab)
        box.add_widget(sv)
        p = Popup(title=title, content=box, size_hint=(0.9, 0.6), title_color=GOLD, separator_color=GOLD,
                  background="", background_color=NAVY2)
        r = row(44)
        for label, fn in (buttons or []) + [("Close", None)]:
            b = Btn(label, primary=(fn is not None))
            b.bind(on_release=lambda w, f=fn: (p.dismiss(), f() if f else None))
            r.add_widget(b)
        box.add_widget(r)
        p.open()
        return p

    def online_ok(self):
        return not core.OFFLINE["force"]

    # =====================================================================  FINDER
    def show_finder(self, pg):
        pg.clear()
        b = pg.box
        self.brief_box = BoxLayout(orientation="vertical", size_hint_y=None)
        self.brief_box.bind(minimum_height=self.brief_box.setter("height"))
        b.add_widget(self.brief_box)
        self.fill_brief()
        skills = self.memory.skills_text()
        c = card()
        c.add_widget(title_label("Ways to earn that fit you"))
        c.add_widget(WLabel(text="Your skills: " + skills, color=MUTED, font_size=sp(13)))
        r = row(36)
        e = Btn("Change my skills", small=True)
        e.bind(on_release=lambda *_: self.edit_skills())
        r.add_widget(e)
        c.add_widget(r)
        b.add_widget(c)
        opps = core.match_opportunities(skills)
        show_all = getattr(self, "_all_opps", False)
        for o in (opps if show_all else opps[:5]):
            b.add_widget(self.opp_card(o))
        if not show_all:
            m = Btn("Show all %d ideas" % len(opps), small=True)
            m.bind(on_release=lambda *_: (setattr(self, "_all_opps", True), self.go("finder")))
            b.add_widget(m)
        # live jobs
        jc = card()
        jc.add_widget(title_label("Live remote jobs"))
        jc.add_widget(WLabel(text=JOBS_CREDIT, color=MUTED, font_size=sp(12)))
        sr = row(44)
        self.job_q = Field("Search jobs, e.g. python")
        sr.add_widget(self.job_q)
        go = Btn("Find", primary=True, size_hint_x=None, width=dp(80))
        go.bind(on_release=lambda *_: self.load_jobs(force=True, search=self.job_q.text.strip()))
        sr.add_widget(go)
        jc.add_widget(sr)
        r2 = row(36)
        rf = Btn("Refresh", small=True)
        rf.bind(on_release=lambda *_: self.load_jobs(force=True))
        r2.add_widget(rf)
        src = Btn("remoteok.com", small=True)
        src.bind(on_release=lambda *_: Droid.view("https://remoteok.com"))
        r2.add_widget(src)
        jc.add_widget(r2)
        b.add_widget(jc)
        self.jobs_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.jobs_box.bind(minimum_height=self.jobs_box.setter("height"))
        b.add_widget(self.jobs_box)
        self.fill_jobs()

    def fill_brief(self):
        box = getattr(self, "brief_box", None)
        if box is None:
            return
        box.clear_widgets()
        today = time.strftime("%Y-%m-%d")
        if self.settings.get("brief_day") == today and not getattr(self, "_brief_lines", None):
            return
        if not getattr(self, "_brief_lines", None):
            br = core.morning_brief(self.jobs, self.settings.get("seen_jobs"), self.tasks, self.earnings)
            self._brief_lines = br["lines"]
            self._brief_new = br["new_ids"]
        c = card(color=NAVY3)
        hour = time.localtime().tm_hour
        c.add_widget(title_label("Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening", 17))
        for ln in self._brief_lines:
            c.add_widget(WLabel(text="\u2022 " + ln, font_size=sp(14)))
        r = row(36)
        ok = Btn("Got it", small=True)

        def done(*_):
            self.settings.set("brief_day", today)
            seen = list(self.settings.get("seen_jobs") or []) + list(getattr(self, "_brief_new", []))
            self.settings.set("seen_jobs", seen[-400:])
            self._brief_lines = None
            box.clear_widgets()
        ok.bind(on_release=done)
        r.add_widget(ok)
        c.add_widget(r)
        box.add_widget(c)

    def opp_card(self, o):
        c = card()
        c.add_widget(title_label(o["title"], 16, WHITE))
        c.add_widget(WLabel(text=o["summary"], color=MUTED, font_size=sp(13.5)))
        if o.get("pay"):
            c.add_widget(WLabel(text="Pay: " + o["pay"], color=GOLD, font_size=sp(13)))
        r = row(36)
        p = Btn("Plan it", primary=True, small=True)
        p.bind(on_release=lambda *_: self.plan_it(o["title"], o.get("summary", ""), o))
        r.add_widget(p)
        if o.get("link"):
            lk = Btn("Open link", small=True)
            lk.bind(on_release=lambda *_: Droid.view(o["link"]))
            r.add_widget(lk)
        c.add_widget(r)
        return c

    def job_card(self, j):
        c = card(spacing=4, pad=10)
        c.add_widget(title_label(j.get("title", ""), 15, WHITE))
        meta = " \u00b7 ".join(x for x in (j.get("company"), j.get("where") or "Remote", j.get("date")) if x)
        c.add_widget(WLabel(text=meta, color=MUTED, font_size=sp(12.5)))
        if j.get("salary"):
            c.add_widget(WLabel(text=j["salary"], color=GOLD, font_size=sp(12.5)))
        if not j.get("open_to_you", True):
            c.add_widget(WLabel(text="May be limited to some countries. Check the post.", color=ORANGE, font_size=sp(12)))
        c.add_widget(WLabel(text="via " + j.get("source", ""), color=MUTED, font_size=sp(11.5)))
        r = row(36)
        o = Btn("Open", primary=True, small=True)
        o.bind(on_release=lambda *_: Droid.view(j.get("url", "")))
        r.add_widget(o)
        p = Btn("Plan it", small=True)
        p.bind(on_release=lambda *_: self.plan_it("Apply: %s at %s" % (j.get("title", ""), j.get("company", "")),
                                                  "Remote job post: " + j.get("url", ""), None))
        r.add_widget(p)
        c.add_widget(r)
        return c

    def fill_jobs(self):
        box = getattr(self, "jobs_box", None)
        if box is None:
            return
        box.clear_widgets()
        if self.jobs_note:
            box.add_widget(WLabel(text=self.jobs_note, color=MUTED, font_size=sp(13)))
        for j in self.jobs[:25]:
            box.add_widget(self.job_card(j))

    def load_jobs_start(self):
        """Called after the first frame: shows cached jobs, fetches fresh ones only when not in low-data mode."""
        self.jobs = list(self.jobcache.data.get("jobs") or [])
        if self.settings.get("low_data"):
            self.jobs_note = "Low-data mode: tap Refresh to load jobs." if not self.jobs else "Saved jobs (low-data mode)."
            self.refresh_finder()
            return
        self.load_jobs(force=False)

    def load_jobs(self, force=False, search=""):
        self.jobs_note = "Loading jobs..."
        self.fill_jobs()

        def work():
            return core.get_jobs(self.jobcache, force=force, search=search)

        def done(r):
            jobs, cached = r if r else ([], True)
            if search:
                self.jobs = jobs
                self.jobs_note = ("%d jobs for '%s'." % (len(jobs), search)) if jobs else \
                    "No matching jobs right now, or no internet. Try other words."
            else:
                self.jobs = jobs
                self.jobs_note = ("" if not cached else "Saved jobs (no internet right now).") if jobs else \
                    "Can't load jobs right now. Check your internet and tap Refresh."
            self.refresh_finder()
        bg(work, done)

    def refresh_finder(self):
        if self.current == "finder":
            self.fill_jobs()
            if not self.settings.get("brief_day") == time.strftime("%Y-%m-%d"):
                self._brief_lines = None
                self.fill_brief()

    def edit_skills(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        box.add_widget(WLabel(text="What can you do? For example: build Android apps, Python, repair phones, writing.",
                              color=MUTED, font_size=sp(13)))
        f = Field("Your skills", multiline=True)
        box.add_widget(f)
        p = Popup(title="My skills", content=box, size_hint=(0.92, 0.55), title_color=GOLD, separator_color=GOLD,
                  background="", background_color=NAVY2)
        r = row(44)
        s = Btn("Save", primary=True)

        def save(*_):
            t = f.text.strip()
            if t:
                for old in [x for x in self.memory.facts if x["kind"] == "skill"]:
                    self.memory.delete(old["id"])
                for part in re.split(r"[,;\n]+", t):
                    if part.strip():
                        self.memory.add(part.strip(), "skill")
            p.dismiss()
            self.go("finder")
        s.bind(on_release=save)
        c = Btn("Cancel")
        c.bind(on_release=lambda *_: p.dismiss())
        r.add_widget(s)
        r.add_widget(c)
        box.add_widget(r)
        p.open()

    def plan_it(self, title, detail="", opp=None):
        self.toast("Making a plan...")

        def work():
            steps = []
            if not self.settings.get("low_data"):
                steps = core.parse_steps(core.ask_ai(core.plan_prompt(title, detail), self.settings, self.memory,
                                                     max_tokens=500))
            return steps or core.offline_plan(opp)

        origin = self.current

        def done(steps):
            steps = steps or core.offline_plan(opp)
            self.tasks.add_plan(title, steps, source=(opp or {}).get("id", ""))
            self.toast("Plan saved in Tasks.")
            if self.current in (origin, "tasks") and not self.page_stack:
                self.go("tasks")
        bg(work, done)

    # =====================================================================  CHAT
    def show_chat(self, pg):
        if getattr(pg, "built", False):
            return
        pg.clear_widgets()
        self.chat_sv = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=GOLD_DIM)
        self.chat_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8),
                                  padding=(dp(10), dp(10), dp(10), dp(10)))
        self.chat_box.bind(minimum_height=self.chat_box.setter("height"))
        self.chat_sv.add_widget(self.chat_box)
        pg.add_widget(self.chat_sv)
        chips = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5), padding=(dp(8), dp(2)))
        for label, fill in (("Jobs", "find jobs "), ("Plan", "plan "), ("Remind", "remind me to "),
                            ("Draft", "draft a whatsapp message "), ("File", None)):
            b = Btn(label, small=True)
            if fill is None:
                b.bind(on_release=lambda *_: self.handle("read a file"))
            else:
                b.bind(on_release=lambda w, f=fill: self._fill(f))
            chips.add_widget(b)
        pg.add_widget(chips)
        bar = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6), padding=(dp(8), dp(6)))
        mic = Btn("Mic", size_hint_x=None, width=dp(56))
        mic.bind(on_release=lambda *_: self.voice())
        bar.add_widget(mic)
        self.chat_in = Field("Ask Orax anything")
        self.chat_in.bind(on_text_validate=lambda *_: self.send())
        bar.add_widget(self.chat_in)
        s = Btn("Send", primary=True, size_hint_x=None, width=dp(70))
        s.bind(on_release=lambda *_: self.send())
        bar.add_widget(s)
        pg.add_widget(bar)
        pg.built = True
        self.say("Hi, I'm Orax. I help you find real ways to earn and plan them. Try: 'find jobs python', "
                 "'plan selling phone covers', 'is this a scam: ...', 'open whatsapp', '100 usd to ugx', or just ask. "
                 "Type 'help' for everything I can do.")

    def _fill(self, text):
        self.chat_in.text = text
        self.chat_in.focus = True

    def send(self):
        t = self.chat_in.text.strip()
        if not t:
            return
        self.chat_in.text = ""
        self.handle(t)

    def bubble(self, text, who="orax", actions=None):
        if not hasattr(self, "chat_box"):
            return None
        outer = BoxLayout(size_hint_y=None)
        c = card(spacing=4, pad=10, color=NAVY3 if who == "orax" else GOLD_DIM)
        c.size_hint_x = 0.88
        c.add_widget(WLabel(text=text, font_size=sp(15), color=WHITE))
        if actions:
            r = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
            for label, fn in actions[:4]:
                b = Btn(label, small=True)
                b.bind(on_release=lambda w, f=fn: self._safe(f))
                r.add_widget(b)
            c.add_widget(r)
        c.bind(height=lambda w, h: setattr(outer, "height", h))
        if who == "orax":
            outer.add_widget(c)
            outer.add_widget(Widget())
        else:
            outer.add_widget(Widget(size_hint_x=0.12))
            outer.add_widget(c)
        self.chat_box.add_widget(outer)
        while len(self.chat_box.children) > 60:          # low RAM: keep the last 60 bubbles
            self.chat_box.remove_widget(self.chat_box.children[-1])
        Clock.schedule_once(lambda dt: setattr(self.chat_sv, "scroll_y", 0), 0.05)
        return c

    def say(self, text, actions=None):
        self.history.append({"who": "orax", "text": text})
        self.history = self.history[-20:]
        return self.bubble(text, "orax", actions)

    def ask_in_chat(self, text):
        """Used by other tabs: show the chat and handle text there."""
        self.go("chat")
        self.handle(text)

    def handle(self, text):
        if self.current != "chat":
            self.go("chat")
        self.bubble(text, "user")
        self.history.append({"who": "user", "text": text})
        if self.pending:
            kind, data = self.pending
            self.pending = None
            if kind == "correction":
                fixed = re.sub(r"^\s*(?:the\s+)?(?:right|correct|real)\s+answer\s+is\s*[:,-]?\s*", "", text, flags=re.I)
                fixed = fixed.strip(" .") or text
                self.memory.add(fixed, "correction")
                self.say("Thanks. I'll remember the right answer: " + fixed)
                return
        sk = self.skills.match(text)
        if sk:
            self.run_skill(sk, text)
            return
        tool, arg = core.detect_intent(text)
        learned = []
        if tool not in ("remember", "correction", "teach"):
            for kind, fact in core.extract_facts(text):
                if self.memory.add(fact, kind):
                    learned.append(fact)
        fn = getattr(self, "do_" + tool, None) or self.do_chat
        fn(arg if tool != "chat" else text)
        if learned and tool not in ("remember", "correction"):
            self.toast("Noted: " + "; ".join(learned)[:80])

    # ---------------- chat tools ----------------
    def do_help(self, _):
        self.say("Here's what I can do:\n"
                 "\u2022 Ask anything; tap Check to compare my answer with web sources\n"
                 "\u2022 find jobs python  \u2022 plan <idea>  \u2022 is this a scam: <message>\n"
                 "\u2022 remind me to <thing> in 20 minutes / at 5pm\n"
                 "\u2022 open <app>  \u2022 install <app>  \u2022 download <link>  \u2022 call <number>\n"
                 "\u2022 draft a whatsapp/email/sms <about>  \u2022 search <words>  \u2022 summarize <link>\n"
                 "\u2022 100 usd to ugx  \u2022 15% of 200000  \u2022 5 km to miles\n"
                 "\u2022 remember <fact>  \u2022 'that's wrong, it's ...' to correct me\n"
                 "\u2022 teach orax: <what you want done> to make your own skill\n"
                 "\u2022 read a file (text files)")

    def do_remember(self, fact):
        f = self.memory.add(fact, "fact")
        self.say(("Got it. I'll remember: " + fact) if f else "I already know that.")

    def do_correction(self, value):
        if value:
            self.memory.add(value, "correction")
            self.say("Thanks for correcting me. I'll remember: " + value)
        else:
            self.pending = ("correction", None)
            self.say("Sorry about that. What's the right answer? I'll remember it.")

    def do_apps(self, _):
        apps = self.get_apps()
        if not apps:
            self.say("I can't see your apps right now.")
            return
        names = sorted({a for a, _ in apps}, key=str.lower)
        self.say("Apps I can open (%d):\n%s\n\nSay 'open <name>'." % (len(names), ", ".join(names[:80])))

    def get_apps(self):
        ts, apps = self.apps_cache
        if apps and time.time() - ts < 600:
            return apps
        apps = Droid.installed_apps()
        self.apps_cache = (time.time(), apps)
        return apps

    def do_open_app(self, name):
        if not name:
            self.say("Which app should I open?")
            return
        hit = core.match_app(name, self.get_apps())
        if hit and Droid.launch(hit[1]):
            self.say("Opening %s." % hit[0])
            return
        pkg = core.known_package(name)
        if pkg:
            Droid.open_store(pkg)
            self.say("%s isn't on your phone. I opened its Play Store page. Tap Install." % name.title(),
                     [("Open again", lambda: Droid.open_store(pkg))])
        else:
            Droid.open_store(query=name)
            self.say("I couldn't find '%s' on your phone, so I searched the Play Store for it. Pick the right app "
                     "and tap Install." % name)

    def do_store(self, name):
        pkg = core.known_package(name)
        Droid.open_store(pkg, None if pkg else name)
        self.say(("Opening the Play Store page for %s. Tap Install." % name.title()) if pkg else
                 ("Searching the Play Store for '%s'. Pick the right app and tap Install." % name))

    def do_open_url(self, url):
        Droid.view(url)
        self.say("Opening " + url)

    def do_dial(self, number):
        Droid.dial(number)
        self.say("Opening the dialer with %s. Press call when you're ready." % number)

    def do_maps(self, place):
        import urllib.parse
        q = urllib.parse.quote(place)
        if not Droid.view("geo:0,0?q=" + q):
            Droid.view("https://www.google.com/maps/search/?api=1&query=" + q)
        self.say("Opening the map for " + place + ".")

    def do_download(self, url):
        folder, label = Droid.download_dir()
        c = self.say("Downloading...")
        lab = c.children[-1] if c else None
        state = {"last": 0}

        def progress(done, total):
            if time.time() - state["last"] < 0.5:
                return
            state["last"] = time.time()
            txt = ("Downloading... %d%%" % (done * 100 // total)) if total else ("Downloading... %.1f MB" % (done / 1e6))
            if lab is not None:
                Clock.schedule_once(lambda dt: setattr(lab, "text", txt), 0)

        def done(r):
            path, why = r if r else (None, "The download didn't finish. Check your internet and try again.")
            if lab is not None:
                lab.text = ("Saved to %s as %s" % (label, os.path.basename(path))) if path else why
        bg(lambda: core.download_file(url, folder, progress), done)

    def do_remind(self, text):
        r = core.parse_reminder(text)
        if not r:
            self.say("When should I remind you? For example: 'remind me to call Sam in 20 minutes' or "
                     "'remind me to study at 5pm'.")
            return
        what, at = r
        self.tasks.add_reminder(what, at)
        self.say("OK. I'll remind you to %s at %s. (Reminders work while Orax is open.)"
                 % (what, time.strftime("%H:%M, %a %d %b", time.localtime(at))))

    def do_calc(self, text):
        a = core.calculate(text)
        if a is None:
            self.do_chat(text)
        else:
            self.say("= " + a)

    def do_convert(self, text):
        def done(a):
            if a:
                self.say(a)
            else:
                self.do_chat(text)
        bg(lambda: core.convert(text, self.rates), done)

    def do_scam(self, text):
        if not text:
            self.go("scam")
            return
        r = core.scam_check(text)
        lines = [r["summary"]] + ["\u2022 " + d for _, d in r["flags"]]
        self.say("\n".join(lines), [("Second opinion", lambda: self.scam_ai(text, r, in_chat=True))])

    def do_jobs(self, words):
        self.go("finder")
        if words:
            self.job_q.text = words
        self.load_jobs(force=True, search=words)

    def do_plan(self, goal):
        self.plan_it(goal.strip()[:120], "", None)

    def do_teach(self, request):
        self.teach(request, in_chat=True)

    def do_read_file(self, _):
        if not IS_ANDROID:
            path = os.environ.get("ORAX_TEST_FILE")
            if path:
                self.got_text_file(path)
            else:
                self.say("Pick a file on your phone to read.")
            return
        try:
            from jnius import autoclass
            from android import activity
            I = Droid._intent()
            if not getattr(self, "_file_bound", False):
                activity.bind(on_activity_result=self._on_file_result)
                self._file_bound = True
            it = I(I.ACTION_GET_CONTENT)
            it.setType("text/*")
            it.addCategory(I.CATEGORY_OPENABLE)
            autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(
                I.createChooser(it, "Choose a text file"), self.FILE_CODE)
            self.say("Choose a text file (.txt, .csv, .md). PDF reading is coming in a later version.")
        except Exception as e:
            core.log("pick: %s" % type(e).__name__)
            self.say("I can't open the file picker on this phone.")

    def _on_file_result(self, request, result, intent):
        if request != self.FILE_CODE:
            return
        path = None
        try:
            if result == -1 and intent is not None:
                from jnius import autoclass
                uri = intent.getData()
                act = autoclass("org.kivy.android.PythonActivity").mActivity
                cr = act.getContentResolver()
                path = os.path.join(self.user_data_dir, "picked.txt")
                if os.path.exists(path):
                    os.remove(path)
                Files = autoclass("java.nio.file.Files")
                JFile = autoclass("java.io.File")
                Files.copy(cr.openInputStream(uri), JFile(path).toPath())
        except Exception as e:
            core.log("pick result: %s" % type(e).__name__)
            path = None
        Clock.schedule_once(lambda dt: self.got_text_file(path) if path else self.say("I couldn't open that file."), 0)

    def got_text_file(self, path):
        text, why = core.read_text_file(path)
        if not text:
            self.say(why)
            return
        self.say("Read %d characters. Summarising..." % len(text))
        self.ai_reply("Summarise this file in short points, then say what the user could do with it:\n\n" + text[:8000],
                      cache_key=None)

    def do_summarize_url(self, url):
        self.say("Reading " + url + " ...")

        def work():
            t = core.fetch_page_text(url, 9000)
            if not t:
                return None
            return core.ask_ai("Summarise this web page in 5 short points:\n\n" + t, self.settings, self.memory)

        def done(a):
            self.say(a or "I couldn't read that page. Open it in the browser instead.",
                     [("Open link", lambda: Droid.view(url))])
        bg(work, done)

    def do_search(self, q):
        self.say("Searching the web...")

        def work():
            res = core.web_search(q)
            if not res:
                return None, []
            return core.ask_ai(core.sources_prompt(q, res), self.settings, self.memory), res

        def done(r):
            a, res = r if r else (None, [])
            if not res:
                self.say("I couldn't search right now. Check your internet.")
                return
            text = (a or "Here are the sources I found:") + "\n\n" + "\n".join(
                "[%d] %s" % (i, x["title"]) for i, x in enumerate(res, 1))
            self.say(text, [("Open [%d]" % i, (lambda u=x["url"]: Droid.view(u))) for i, x in enumerate(res[:3], 1)])
        bg(work, done)

    def do_wiki(self, q):
        def work():
            hits = core.wiki_search(q, 1)
            return core.wiki_summary(hits[0]["title"]) if hits else None

        def done(s):
            if not s:
                self.say("I couldn't find that on Wikipedia.")
                return
            self.say("%s\n\n%s\n(Source: Wikipedia)" % (s["title"], s["text"]),
                     [("Open", lambda: Droid.view(s["url"]))])
        bg(work, done)

    def do_draft(self, text):
        self.say("Writing your draft...")

        def done(a):
            if not a:
                self.say(core.NO_ANSWER)
                return
            subj, body = core.split_subject(a)
            acts = [("Share", lambda: Droid.share(body, subj)),
                    ("WhatsApp", lambda: Droid.share(body, "", "com.whatsapp") or Droid.share(body, subj)),
                    ("Email", lambda: Droid.mailto(subj, body))]
            self.say((("Subject: " + subj + "\n\n") if subj else "") + body + "\n\n(You choose who to send it to.)",
                     acts)
        bg(lambda: core.ask_ai(core.draft_prompt(text), self.settings, self.memory, max_tokens=500), done)

    def do_chat(self, text):
        self.ai_reply(text, cache_key=text, check=True)

    def ai_reply(self, prompt, cache_key=None, check=False):
        low = self.settings.get("low_data")
        if cache_key and low:
            hit = self.cache.find(cache_key)
            if hit:
                self.say(hit["a"] + "\n\n(Saved answer, low-data mode)")
                return
        thinking = self.say("...")
        lab = thinking.children[-1] if thinking else None
        hist = list(self.history[:-1])

        def done(a):
            if lab is not None and lab.parent is not None:
                outer = lab.parent.parent
                if outer is not None and outer.parent is not None:
                    outer.parent.remove_widget(outer)
            self.history = [h for h in self.history if h.get("text") != "..."]
            if not a and cache_key:
                hit = self.cache.find(cache_key)
                if hit:
                    self.say(hit["a"] + "\n\n(Saved answer from before; I'm offline right now.)")
                    return
            if not a:
                self.say(core.NO_ANSWER)
                return
            if cache_key:
                self.cache.put(cache_key, a)
            acts = [("Check", lambda: self.check_answer(cache_key, a))] if check and cache_key else None
            self.say(a, acts)
        bg(lambda: core.ask_ai(prompt, self.settings, self.memory, hist, max_tokens=400 if low else 700), done)

    def check_answer(self, q, a):
        self.say("Checking against web sources...")

        def work():
            res = core.web_search(q, 4)
            v = core.ask_ai(core.check_prompt(q, a, res), self.settings, None, max_tokens=120) if res else ""
            return core.check_verdict(v, res), res

        def done(r):
            if not r:
                self.say("I couldn't check that right now.")
                return
            (kind, msg), res = r
            self.say(msg + ("\n\n" + "\n".join("[%d] %s" % (i, x["title"]) for i, x in enumerate(res, 1)) if res else ""),
                     [("Open [%d]" % i, (lambda u=x["url"]: Droid.view(u))) for i, x in enumerate(res[:3], 1)])
        bg(work, done)

    # ---------------- voice ----------------
    def voice(self):
        if not IS_ANDROID:
            self.toast("Voice input works on the phone.")
            return
        try:
            from jnius import autoclass
            from android import activity
            I = Droid._intent()
            RI = autoclass("android.speech.RecognizerIntent")
            if not getattr(self, "_voice_bound", False):
                activity.bind(on_activity_result=self._on_voice)
                self._voice_bound = True
            i = I(RI.ACTION_RECOGNIZE_SPEECH)
            i.putExtra(RI.EXTRA_LANGUAGE_MODEL, RI.LANGUAGE_MODEL_FREE_FORM)
            i.putExtra(RI.EXTRA_PROMPT, "Talk to Orax")
            autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(i, self.SPEECH_CODE)
        except Exception as e:
            core.log("voice: %s" % type(e).__name__)
            self.toast("Voice input isn't available. Install or update the Google app, then try again.")

    def _on_voice(self, request, result, intent):
        if request != self.SPEECH_CODE:
            return
        words = ""
        try:
            if result == -1 and intent is not None:
                from jnius import autoclass
                RI = autoclass("android.speech.RecognizerIntent")
                lst = intent.getStringArrayListExtra(RI.EXTRA_RESULTS)
                if lst is not None and lst.size() > 0:
                    words = str(lst.get(0))
        except Exception:
            words = ""
        if words:
            Clock.schedule_once(lambda dt: self._safe(self.handle, words), 0)

    # ---------------- Teach Orax ----------------
    def teach(self, request, in_chat=False):
        def work():
            if request.strip().startswith("{"):
                d = core.parse_skill_json(request)
            else:
                d = core.parse_skill_json(core.ask_ai(core.skill_prompt(request), self.settings, None, max_tokens=500))
            return core.validate_skill(d)

        def done(r):
            sk, why = r if r else (None, "I couldn't make that skill right now. Check your internet and try again.")
            if not sk:
                msg = "I couldn't make that skill: " + why
                self.say(msg) if in_chat else self.toast(msg, 4)
                return
            desc = self.skill_text(sk)
            if in_chat:
                self.say("Here's the skill. It only uses Orax's built-in tools. Save it?\n\n" + desc,
                         [("Save skill", lambda: self.save_skill(sk))])
            else:
                self.popup("New skill", "It only uses Orax's built-in tools. Save it?\n\n" + desc,
                           [("Save", lambda: self.save_skill(sk))])
        if in_chat:
            self.say("Making the skill...")
        else:
            self.toast("Making the skill...")
        bg(work, done)

    def skill_text(self, sk):
        lines = [sk["name"] + (" - " + sk["about"] if sk.get("about") else "")]
        if sk.get("triggers"):
            lines.append("Say: " + ", ".join(sk["triggers"]))
        if sk.get("time"):
            lines.append("Runs every day at %s (while Orax is open)" % sk["time"])
        for i, s in enumerate(sk["steps"], 1):
            lines.append("%d. %s: %s" % (i, s["tool"].replace("_", " "), s["arg"] or "-"))
        return "\n".join(lines)

    def save_skill(self, sk):
        self.skills.put(sk)
        self.toast("Skill saved: " + sk["name"])
        if self.current == "more":
            self.show_skills()

    def run_skill(self, sk, said=""):
        self.skills.mark_ran(sk["id"])
        if self.current != "chat":
            self.go("chat")
        self.say("Running your skill: " + sk["name"])
        steps = list(sk["steps"])
        state = {"last": ""}

        def next_step(*_):
            if not steps:
                return
            s = steps.pop(0)
            tool = s["tool"]
            arg = s["arg"].replace("{input}", said).replace("{last}", state["last"][:3000])
            if tool == "ask_ai":
                def done(a):
                    state["last"] = a or ""
                    self.say(a or core.NO_ANSWER)
                    next_step()
                bg(lambda: core.ask_ai(arg, self.settings, self.memory, max_tokens=500), done)
                return
            if tool == "jobs":
                def done2(r):
                    jobs = (r or ([], True))[0][:5]
                    state["last"] = "\n".join("%s - %s (%s)" % (j["title"], j.get("company", ""), j["url"]) for j in jobs)
                    self.say(("Jobs:\n" + state["last"]) if jobs else "No jobs found right now.")
                    next_step()
                bg(lambda: core.get_jobs(self.jobcache, search=arg), done2)
                return
            if tool == "web_search":
                def done3(res):
                    res = res or []
                    state["last"] = "\n".join("%s: %s" % (x["title"], x.get("snippet", "")) for x in res)
                    self.say(("Found:\n" + "\n".join(x["title"] for x in res)) if res else "Nothing found right now.")
                    next_step()
                bg(lambda: core.web_search(arg), done3)
                return
            simple = {"summarize_url": self.do_summarize_url, "open_app": self.do_open_app, "play_store": self.do_store,
                      "draft": lambda a: self.do_draft("draft a message " + a), "add_task": self.do_plan,
                      "remind": lambda a: self.do_remind("remind me to " + a), "calculate": self.do_calc,
                      "convert": self.do_convert}
            f = simple.get(tool)
            if f:
                f(arg)
            Clock.schedule_once(next_step, 0.5)
        next_step()

    # ---------------- reminders and timed skills (while open) ----------------
    def tick(self):
        for r in self.tasks.due():
            self.popup("Reminder", r["text"])
            try:
                if IS_ANDROID:
                    from jnius import autoclass
                    act = autoclass("org.kivy.android.PythonActivity").mActivity
                    v = act.getSystemService("vibrator")
                    if v:
                        v.vibrate(400)
            except Exception:
                pass
        for sk in self.skills.due_now():
            self.run_skill(sk)
            break

    # =====================================================================  TASKS
    def show_tasks(self, pg):
        pg.clear()
        b = pg.box
        c = card()
        c.add_widget(title_label("Reminders"))
        c.add_widget(WLabel(text="Reminders work while Orax is open.", color=MUTED, font_size=sp(12.5)))
        f = Field("e.g. call the shop owner in 30 minutes")
        c.add_widget(f)
        r = row(40)
        a = Btn("Add reminder", primary=True, small=True)

        def add(*_):
            t = f.text.strip()
            if not t:
                return
            rr = core.parse_reminder(t if t.lower().startswith("remind me") else "remind me to " + t)
            if not rr:
                self.toast("Add a time, like 'in 30 minutes' or 'at 5pm'.", 3.5)
                return
            self.tasks.add_reminder(*rr)
            self.toast("Reminder set for " + time.strftime("%H:%M %a", time.localtime(rr[1])))
            self.go("tasks")
        a.bind(on_release=add)
        r.add_widget(a)
        c.add_widget(r)
        upcoming = sorted([x for x in self.tasks.reminders if not x["fired"]], key=lambda x: x["at"])
        for rem in upcoming[:20]:
            rr = row(36)
            rr.add_widget(WLabel(text="%s  %s" % (time.strftime("%H:%M %a %d", time.localtime(rem["at"])), rem["text"]),
                                 font_size=sp(13.5), height=dp(36)))
            x = Btn("Delete", small=True, size_hint_x=None, width=dp(72))
            x.bind(on_release=lambda w, i=rem["id"]: (self.tasks.delete_reminder(i), self.go("tasks")))
            rr.add_widget(x)
            c.add_widget(rr)
        b.add_widget(c)
        c2 = card()
        c2.add_widget(title_label("Plans"))
        f2 = Field("A goal, e.g. sell phone covers at school")
        c2.add_widget(f2)
        r2 = row(40)
        mk = Btn("Make a plan", primary=True, small=True)
        mk.bind(on_release=lambda *_: f2.text.strip() and self.plan_it(f2.text.strip()[:120], "", None))
        r2.add_widget(mk)
        c2.add_widget(r2)
        if not self.tasks.plans:
            c2.add_widget(WLabel(text="No plans yet. Tap Plan it on any idea in Finder.", color=MUTED, font_size=sp(13)))
        b.add_widget(c2)
        for p in self.tasks.plans[:15]:
            b.add_widget(self.plan_card(p))

    def plan_card(self, p):
        c = card()
        done = sum(1 for s in p["steps"] if s["done"])
        c.add_widget(title_label("%s  (%d/%d)" % (p["title"], done, len(p["steps"])), 15, WHITE))
        for i, s in enumerate(p["steps"]):
            b = Button(text=("[x]  " if s["done"] else "[  ]  ") + s["text"], size_hint_y=None, halign="left",
                       valign="middle", background_normal="", background_color=(0, 0, 0, 0),
                       color=MUTED if s["done"] else WHITE, font_size=sp(14))
            b.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                   texture_size=lambda w, ts: setattr(w, "height", max(dp(34), ts[1] + dp(8))))
            b.bind(on_release=lambda w, pid=p["id"], k=i: (self.tasks.toggle(pid, k), self.go("tasks")))
            c.add_widget(b)
        r = row(36)
        rm = Btn("Remind me", small=True)
        rm.bind(on_release=lambda *_: self._remind_plan(p))
        r.add_widget(rm)
        d = Btn("Delete plan", small=True)
        d.bind(on_release=lambda *_: self.popup("Delete plan?", p["title"],
                                                [("Delete", lambda: (self.tasks.delete_plan(p["id"]), self.go("tasks")))]))
        r.add_widget(d)
        c.add_widget(r)
        return c

    def _remind_plan(self, p):
        nxt = next((s["text"] for s in p["steps"] if not s["done"]), None)
        if not nxt:
            self.toast("All steps are done. Well done!")
            return
        self.tasks.add_reminder(nxt, time.time() + 3600, p["id"])
        self.toast("I'll remind you in 1 hour: " + nxt[:60])
        self.go("tasks")

    # =====================================================================  MONEY
    def show_money(self, pg):
        pg.clear()
        b = pg.box
        wk = core.week_totals(self.earnings.items)
        c = card(color=NAVY3)
        c.add_widget(title_label("This week"))
        c.add_widget(WLabel(text="Earned  %s\nSpent    %s\nNet       %s" % (core.ugx(wk["earned"]), core.ugx(wk["spent"]),
                                                                         core.ugx(wk["net"])), font_size=sp(16)))
        b.add_widget(c)
        f = card()
        f.add_widget(title_label("Add money in or out", 16))
        amt = Field("Amount in UGX", number=True)
        opp = Field("From / for, e.g. Fiverr, data bundles")
        note = Field("Note (optional)")
        for w in (amt, opp, note):
            f.add_widget(w)
        r = row(44)

        def add(kind):
            e = self.earnings.add(amt.text, kind, opp.text, note.text)
            if not e:
                self.toast("Type an amount, like 20000.")
                return
            self.toast(("Added %s earned" if kind == "earn" else "Added %s spent") % core.ugx(e["amount"]))
            self.go("money")
        e1 = Btn("I earned", primary=True)
        e1.bind(on_release=lambda *_: add("earn"))
        e2 = Btn("I spent")
        e2.bind(on_release=lambda *_: add("spend"))
        r.add_widget(e1)
        r.add_widget(e2)
        f.add_widget(r)
        b.add_widget(f)
        bo = core.by_opportunity(self.earnings.items)
        if bo:
            c3 = card()
            c3.add_widget(title_label("By source (all time)", 16))
            for k, v in sorted(bo.items(), key=lambda kv: -(kv[1]["earned"] - kv[1]["spent"]))[:12]:
                c3.add_widget(WLabel(text="%s: earned %s, spent %s" % (k, core.ugx(v["earned"]), core.ugx(v["spent"])),
                                     font_size=sp(13.5)))
            b.add_widget(c3)
        if self.earnings.items:
            c4 = card()
            c4.add_widget(title_label("Recent", 16))
            for e in self.earnings.items[:30]:
                rr = row(36)
                sign = "+" if e["kind"] == "earn" else "-"
                rr.add_widget(WLabel(text="%s %s%s  %s" % (time.strftime("%d %b", time.localtime(e["ts"])), sign,
                                                           core.ugx(e["amount"]), e["opp"]),
                                     color=GREEN if sign == "+" else ORANGE, font_size=sp(13.5), height=dp(36)))
                x = Btn("Delete", small=True, size_hint_x=None, width=dp(72))
                x.bind(on_release=lambda w, i=e["id"]: (self.earnings.delete(i), self.go("money")))
                rr.add_widget(x)
                c4.add_widget(rr)
            b.add_widget(c4)

    # =====================================================================  SCAM
    def show_scam(self, pg):
        pg.clear()
        b = pg.box
        c = card()
        c.add_widget(title_label("Is it a scam?"))
        c.add_widget(WLabel(text="Paste a job offer, message or post. Orax checks it for common scam signs.",
                            color=MUTED, font_size=sp(13)))
        self.scam_in = Field("Paste the message here", multiline=True)
        c.add_widget(self.scam_in)
        r = row(44)
        k = Btn("Check", primary=True)
        k.bind(on_release=lambda *_: self.scam_run())
        r.add_widget(k)
        cl = Btn("Clear")
        cl.bind(on_release=lambda *_: (setattr(self.scam_in, "text", ""), self.scam_out.clear_widgets()))
        r.add_widget(cl)
        c.add_widget(r)
        b.add_widget(c)
        self.scam_out = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8))
        self.scam_out.bind(minimum_height=self.scam_out.setter("height"))
        b.add_widget(self.scam_out)
        t = card(color=NAVY3)
        t.add_widget(title_label("Stay safe", 16))
        for tip in ("Real employers never ask you to pay to get a job.",
                    "Never share your Mobile Money PIN, OTP or passwords.",
                    "Check the company on its own website, not only WhatsApp or Telegram.",
                    "Very high pay for easy work is a warning sign.",
                    "Be careful with 'double your money', crypto and forex offers."):
            t.add_widget(WLabel(text="\u2022 " + tip, font_size=sp(13.5)))
        b.add_widget(t)

    def scam_run(self):
        text = self.scam_in.text.strip()
        self.scam_out.clear_widgets()
        if not text:
            self.toast("Paste a message first.")
            return
        r = core.scam_check(text)
        col = {"high": RED, "medium": ORANGE, "low": GREEN}[r["level"]]
        c = card(color=NAVY2)
        c.add_widget(title_label({"high": "High risk", "medium": "Be careful", "low": "No common signs found"}[r["level"]],
                                 17, col))
        c.add_widget(WLabel(text=r["summary"], font_size=sp(14)))
        for _, d in r["flags"]:
            c.add_widget(WLabel(text="\u2022 " + d, color=col, font_size=sp(13.5)))
        rr = row(40)
        s = Btn("Second opinion", small=True)
        s.bind(on_release=lambda *_: self.scam_ai(text, r))
        rr.add_widget(s)
        c.add_widget(rr)
        self.scam_out.add_widget(c)

    def scam_ai(self, text, r, in_chat=False):
        if in_chat:
            self.say("Asking for a second opinion...")
        else:
            self.toast("Getting a second opinion...")

        def done(a):
            msg = a or core.NO_ANSWER
            if in_chat or self.current != "scam":
                self.say(msg)
            else:
                c = card(color=NAVY3)
                c.add_widget(WLabel(text=msg, font_size=sp(14)))
                self.scam_out.add_widget(c)
        bg(lambda: core.ask_ai(core.scam_prompt(text, r), self.settings, None, max_tokens=300), done)

    # =====================================================================  MORE
    def show_more(self, pg):
        pg.clear()
        b = pg.box
        b.add_widget(title_label("More"))
        for label, fn in (("What Orax knows", self.show_knows), ("My skills", self.show_skills),
                          ("Settings", self.show_settings), ("About", self.show_about)):
            x = Btn(label)
            x.bind(on_release=lambda w, f=fn: self._sub(f))
            b.add_widget(x)
        b.add_widget(WLabel(text=CREDIT, color=MUTED, font_size=sp(12), halign="center"))

    def _sub(self, fn):
        self.page_stack.append(lambda: self.go("more"))
        fn()

    def _sub_page(self, title):
        pg = self.pages["more"]
        pg.clear()
        r = row(40)
        back = Btn("< Back", small=True, size_hint_x=None, width=dp(90))
        back.bind(on_release=lambda *_: self.go("more"))
        r.add_widget(back)
        r.add_widget(Label(text=title, color=GOLD, font_size=sp(17), bold=True))
        pg.box.add_widget(r)
        return pg.box

    def show_knows(self):
        b = self._sub_page("What Orax knows")
        b.add_widget(WLabel(text="Orax uses these to help you. Corrections always win. Delete anything that's wrong.",
                            color=MUTED, font_size=sp(13)))
        f = Field("Add something, e.g. I live in Mityana")
        b.add_widget(f)
        r = row(40)
        a = Btn("Remember", primary=True, small=True)
        a.bind(on_release=lambda *_: f.text.strip() and (self.memory.add(f.text.strip()), self.show_knows()))
        r.add_widget(a)
        clr = Btn("Forget all", small=True)
        clr.bind(on_release=lambda *_: self.popup("Forget everything?", "Orax will forget all saved facts.",
                                                  [("Forget all", lambda: (self.memory.clear(), self.show_knows()))]))
        r.add_widget(clr)
        b.add_widget(r)
        names = {"correction": "Correction", "skill": "Skill", "location": "Place", "goal": "Goal", "fact": "Fact"}
        if not self.memory.facts:
            b.add_widget(WLabel(text="Nothing saved yet. Tell Orax things like 'I can build Android apps'.",
                                color=MUTED, font_size=sp(13)))
        for fct in reversed(self.memory.facts[-80:]):
            rr = row(40)
            rr.add_widget(WLabel(text="%s: %s" % (names.get(fct["kind"], "Fact"), fct["text"]), font_size=sp(13.5),
                                 height=dp(40)))
            x = Btn("Delete", small=True, size_hint_x=None, width=dp(72))
            x.bind(on_release=lambda w, i=fct["id"]: (self.memory.delete(i), self.show_knows()))
            rr.add_widget(x)
            b.add_widget(rr)

    def show_skills(self):
        b = self._sub_page("My skills")
        b.add_widget(WLabel(text="Teach Orax a skill: say what you want done. Orax turns it into steps that use only its "
                                 "built-in tools (search, jobs, open apps, drafts, plans, reminders, maths). You see it "
                                 "before it's saved.", color=MUTED, font_size=sp(13)))
        f = Field("e.g. every morning at 7 show python jobs and summarise them", multiline=True)
        b.add_widget(f)
        r = row(40)
        m = Btn("Make skill", primary=True, small=True)
        m.bind(on_release=lambda *_: f.text.strip() and self.teach(f.text.strip()))
        r.add_widget(m)
        b.add_widget(r)
        if not self.skills.items:
            b.add_widget(WLabel(text="No skills yet.", color=MUTED, font_size=sp(13)))
        for sk in self.skills.items:
            c = card()
            c.add_widget(WLabel(text=self.skill_text(sk), font_size=sp(13.5)))
            rr = row(36)
            run = Btn("Run", primary=True, small=True)
            run.bind(on_release=lambda w, s=sk: self.run_skill(s))
            rr.add_widget(run)
            d = Btn("Delete", small=True)
            d.bind(on_release=lambda w, i=sk["id"]: (self.skills.delete(i), self.show_skills()))
            rr.add_widget(d)
            c.add_widget(rr)
            b.add_widget(c)

    def show_settings(self):
        b = self._sub_page("Settings")
        c = card()
        c.add_widget(title_label("Your own AI keys (optional)", 15))
        c.add_widget(WLabel(text="Orax works without keys. A free key can make answers faster. Keys stay on this phone.",
                            color=MUTED, font_size=sp(12.5)))
        c.add_widget(WLabel(text="Groq key", font_size=sp(13)))
        k1 = Field("Paste key", password=True)
        k1.text = self.settings.get("key_fast") or ""
        c.add_widget(k1)
        c.add_widget(WLabel(text="Gemini key", font_size=sp(13)))
        k2 = Field("Paste key", password=True)
        k2.text = self.settings.get("key_g") or ""
        c.add_widget(k2)
        r = row(40)
        s = Btn("Save keys", primary=True, small=True)

        def save(*_):
            self.settings.set("key_fast", k1.text.strip())
            self.settings.set("key_g", k2.text.strip())
            self.toast("Keys saved.")
        s.bind(on_release=save)
        r.add_widget(s)
        c.add_widget(r)
        b.add_widget(c)
        c2 = card()
        lg = self.settings.get("lang") == "lg"
        t1 = Btn("Luganda replies: " + ("ON" if lg else "OFF"), small=True)
        t1.bind(on_release=lambda *_: (self.settings.set("lang", "en" if lg else "lg"), self.show_settings()))
        c2.add_widget(t1)
        c2.add_widget(WLabel(text="Orax answers in simple Luganda; app names, links and numbers stay in English.",
                             color=MUTED, font_size=sp(12.5)))
        ld = bool(self.settings.get("low_data"))
        t2 = Btn("Low-data mode: " + ("ON" if ld else "OFF"), small=True)
        t2.bind(on_release=lambda *_: (self.settings.set("low_data", not ld), self.show_settings()))
        c2.add_widget(t2)
        c2.add_widget(WLabel(text="Low-data mode: jobs load only when you tap Refresh, answers are shorter, and saved "
                                  "answers are reused.", color=MUTED, font_size=sp(12.5)))
        b.add_widget(c2)

    def show_about(self):
        b = self._sub_page("About")
        c = card()
        c.add_widget(title_label("Orax", 22))
        c.add_widget(WLabel(text=ABOUT_TEXT, font_size=sp(15)))
        c.add_widget(WLabel(text=ABOUT_LIMITS, color=MUTED, font_size=sp(13.5)))
        c.add_widget(WLabel(text=JOBS_CREDIT, color=MUTED, font_size=sp(12.5)))
        c.add_widget(WLabel(text="Version %s | build %s | %s" % (VERSION, BUILD_NUMBER, BUILD_COMMIT), color=MUTED,
                            font_size=sp(12)))
        c.add_widget(WLabel(text=CREDIT, color=GOLD, font_size=sp(14)))
        b.add_widget(c)


__all__ = ["OraxApp", "CREDIT", "VERSION"]
