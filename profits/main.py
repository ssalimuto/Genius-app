"""Ssalimuto Profits - phone app for the Safe MT5 Bot strategies.
Made by Ssali Muto. No bot can promise no losses.
"""
import json
import os
import threading
import time
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase, DEFAULT_FONT
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

import core

VERSION = "1.0"
BUILD_NUMBER = "dev"
BUILD_COMMIT = "dev"
APP_NAME = "Ssalimuto Profits"
CREDIT = "Made by Ssali Muto"
DOWNLOAD_LINK = "https://github.com/ssalimuto/Genius-app/releases/download/profits-android/SsalimutoProfits.apk"
MT5_PACKAGE = "net.metaquotes.metatrader5"
HERE = os.path.dirname(os.path.abspath(__file__))

BG = (0.043, 0.043, 0.05, 1)
CARD = (0.105, 0.098, 0.09, 1)
CARD2 = (0.15, 0.135, 0.11, 1)
GOLD = (0.91, 0.75, 0.36, 1)
GOLD_DARK = (0.55, 0.43, 0.17, 1)
TEXT = (0.94, 0.92, 0.87, 1)
MUTED = (0.66, 0.63, 0.56, 1)
GREEN = (0.30, 0.78, 0.45, 1)
RED = (0.86, 0.22, 0.2, 1)
INK = (0.08, 0.07, 0.05, 1)

DEFAULT_SETTINGS = {
    "strategy": "meanrev", "tf": "1d", "trade_mode": "manual", "practice_pairs": ["GBPUSD"],
    "interval_min": 10, "balance_hint": 0.0, "region": "new-york", "suffix": "",
    "live_enabled": False, "live_accepted": False, "live_pairs": ["GBPUSD"], "stopped": False,
}

try:
    LabelBase.register(DEFAULT_FONT, os.path.join(HERE, "fonts", "Inter-Regular.ttf"),
                       fn_bold=os.path.join(HERE, "fonts", "Inter-Bold.ttf"))
except Exception:
    pass


# ---------------------------------------------------------------- small UI helpers
def _bg(widget, color, radius=12):
    with widget.canvas.before:
        c = Color(*color)
        r = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(radius)])
    widget.bind(pos=lambda w, v: setattr(r, "pos", v), size=lambda w, v: setattr(r, "size", v))
    widget._bgc = c
    return c


class Lbl(Label):
    def __init__(self, text="", size=15, color=TEXT, bold=False, halign="left", **kw):
        super().__init__(text=text, font_size=sp(size), color=color, bold=bold, halign=halign, valign="middle",
                         size_hint_y=None, markup=True, **kw)
        self.bind(width=lambda w, v: setattr(w, "text_size", (v, None)),
                  texture_size=lambda w, v: setattr(w, "height", max(v[1], dp(18))))


class Btn(Button):
    def __init__(self, text, cb=None, bg=GOLD, fg=INK, h=46, size=15, wrap=True, **kw):
        super().__init__(text=text, font_size=sp(size), color=fg, bold=True, size_hint_y=None, height=dp(h),
                         background_normal="", background_down="", background_color=(0, 0, 0, 0), **kw)
        self._c = _bg(self, bg, 10)
        self._base = bg
        self.halign = "center"
        if wrap:
            self.bind(width=lambda w, v: setattr(w, "text_size", (v - dp(8), None)))
        if cb:
            self.bind(on_release=lambda *_: cb())
        self.bind(state=lambda w, s: setattr(w._c, "rgba", tuple(x * (0.8 if s == "down" else 1) for x in w._base[:3]) + (1,)))


class Card(BoxLayout):
    def __init__(self, color=CARD, pad=12, spacing=6, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, padding=dp(pad), spacing=dp(spacing), **kw)
        self.bind(minimum_height=self.setter("height"))
        _bg(self, color, 14)


def row(*widgets, h=None, spacing=8):
    r = BoxLayout(orientation="horizontal", size_hint_y=None, spacing=dp(spacing))
    for w in widgets:
        r.add_widget(w)
    if h:
        r.height = dp(h)
    else:
        def fit(*_):
            r.height = max([w.height for w in r.children] + [dp(20)])
        for w in widgets:
            w.bind(height=fit)
        fit()
    return r


def field(hint, password=False, text="", numeric=False):
    t = TextInput(hint_text=hint, password=password, text=text, multiline=False, size_hint_y=None, height=dp(46),
                  font_size=sp(16), background_color=(0.16, 0.15, 0.13, 1), foreground_color=TEXT,
                  hint_text_color=MUTED, cursor_color=GOLD, padding=[dp(10), dp(12)], write_tab=False)
    if numeric:
        t.input_filter = "float"
    return t


def gap(h=8):
    return Widget(size_hint_y=None, height=dp(h))


def money(x, cur="$"):
    return "-" if x is None else ("%s%.2f" % (cur, x) if x >= 0 else "-%s%.2f" % (cur, -x))


def signed(x):
    return "-" if x is None else "%+.2f" % x


def color_hex(c):
    return "%02x%02x%02x" % tuple(int(v * 255) for v in c[:3])


def fmt_price(sym, x):
    if x is None:
        return "-"
    return ("%.2f" if sym.startswith(("XAU", "BTC", "ETH")) else "%.3f" if "JPY" in sym else "%.5f") % x


# ---------------------------------------------------------------- Android bits (safe on a computer)
def open_mt5():
    """Launch the official MetaTrader 5 app, or its store page. -> plain result text"""
    try:
        from jnius import autoclass
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        it = act.getPackageManager().getLaunchIntentForPackage(MT5_PACKAGE)
        if it is not None:
            act.startActivity(it)
            return "Opening MetaTrader 5..."
        try:
            act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + MT5_PACKAGE)))
        except Exception:
            act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=" + MT5_PACKAGE)))
        return "MetaTrader 5 is not installed. Opening its store page."
    except ImportError:
        return "Open MetaTrader 5 on your phone (this only works on Android)."
    except Exception:
        return "Could not open MetaTrader 5. Open it yourself from your apps."


def copy_text(t):
    try:
        from kivy.core.clipboard import Clipboard
        Clipboard.copy(t)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- the app
class ProfitsApp(App):
    title = APP_NAME

    def build(self):
        Window.clearcolor = BG
        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass
        self.folder = self.user_data_dir
        self.vault = core.Vault(self.folder)
        self.settings = self._load("settings.json", dict(DEFAULT_SETTINGS))
        for k, v in DEFAULT_SETTINGS.items():
            self.settings.setdefault(k, v)
        self.practice = self._load("practice.json", core.new_practice())
        self.live_state = self._load("live_state.json", {})
        self.activity = self._load("activity.json", [])
        self.market = {}          # sym -> {"price", "bars"} daily
        self.market_tf = {}       # practice timeframe data when 1h
        self.directions = {}
        self.news, self.news_note = None, ""
        self.crypto = []
        self.account = None       # real account status (paid bridge only)
        self.connected = False
        self.conn_msg = ""
        self.locks = []
        self.quotes = {}
        self.busy = threading.Lock()
        self.last_check = None
        self.tab = "home"
        self.show_adv = False
        self.show_cloud = False
        self.locked = True
        self.paused_at = None
        self._tick_ev = None
        self.root_box = BoxLayout(orientation="vertical")
        _bg(self.root_box, BG, 0)
        self.show_lock()
        return self.root_box

    # ---------- files
    def _path(self, name):
        return os.path.join(self.folder, name)

    def _load(self, name, default):
        try:
            with open(self._path(name)) as f:
                return json.load(f)
        except Exception:
            return default

    def _save(self, name, data):
        try:
            tmp = self._path(name) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, self._path(name))
        except Exception:
            pass

    def save_all(self):
        self._save("settings.json", self.settings)
        self._save("practice.json", self.practice)
        self._save("live_state.json", self.live_state)
        self._save("activity.json", self.activity[:200])

    def note(self, msg):
        stamp = datetime.now().strftime("%d %b %H:%M")
        self.activity.insert(0, "%s  %s" % (stamp, msg))
        del self.activity[200:]

    # ---------- lock screen
    def show_lock(self, msg=""):
        self.locked = True
        self.vault.lock()
        rb = self.root_box
        rb.clear_widgets()
        sv = ScrollView()
        box = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(24), spacing=dp(12))
        box.bind(minimum_height=box.setter("height"))
        box.add_widget(gap(20))
        img = Image(source=os.path.join(HERE, "icon.png"), size_hint_y=None, height=dp(120))
        box.add_widget(img)
        box.add_widget(Lbl(APP_NAME, 26, GOLD, True, "center"))
        box.add_widget(Lbl(CREDIT, 13, MUTED, False, "center"))
        box.add_widget(gap(10))
        creating = not self.vault.has_pin()
        p1 = field("PIN (4+ digits) or password (6+ characters)", password=True)
        p2 = field("Type it again", password=True) if creating else None
        status = Lbl(msg, 14, RED if msg else MUTED, False, "center")
        if creating:
            box.add_widget(Lbl("Create your app PIN or password. It is stored only on this phone, as a salted hash. "
                               "It also locks your saved MetaApi details.", 14, TEXT))
            box.add_widget(p1)
            box.add_widget(p2)

            def make():
                if p1.text != p2.text:
                    status.text = "The two entries are different."; status.color = RED; return
                try:
                    self.vault.set_pin(p1.text, keep_secrets=False)
                except ValueError as e:
                    status.text = str(e); status.color = RED; return
                self.unlocked()
            box.add_widget(Btn("Create PIN", make))
        else:
            box.add_widget(Lbl("Enter your PIN or password.", 15, TEXT, False, "center"))
            box.add_widget(p1)

            def go():
                ok, m = self.vault.unlock(p1.text)
                p1.text = ""
                if ok:
                    self.unlocked()
                else:
                    status.text = m; status.color = RED
            p1.bind(on_text_validate=lambda *_: go())
            box.add_widget(Btn("Unlock", go))

            def forgot():
                self.confirm("Forgot your PIN?",
                             "This removes the PIN and the saved MetaApi token and account id from this phone, and "
                             "turns live trading off. Practice history stays. You then create a new PIN.",
                             "Remove and start again", self._forget_pin)
            box.add_widget(Btn("Forgot PIN?", forgot, bg=CARD2, fg=MUTED, h=40, size=13))
        box.add_widget(status)
        box.add_widget(Lbl("No bot can promise no losses.", 12, MUTED, False, "center"))
        sv.add_widget(box)
        rb.add_widget(sv)

    def _forget_pin(self):
        self.vault.forget()
        self.settings["live_enabled"] = False
        self.settings["live_accepted"] = False
        self.connected = False
        self.account = None
        self.save_all()
        self.show_lock("PIN removed. Create a new one.")

    def unlocked(self):
        self.locked = False
        self.build_main()
        self.schedule_ticks()
        Clock.schedule_once(lambda dt: self.tick(), 0.3)

    # ---------- main layout
    def build_main(self):
        rb = self.root_box
        rb.clear_widgets()
        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56), padding=[dp(12), dp(6)], spacing=dp(8))
        _bg(head, (0.07, 0.065, 0.055, 1), 0)
        head.add_widget(Image(source=os.path.join(HERE, "icon.png"), size_hint=(None, 1), width=dp(40)))
        tbox = BoxLayout(orientation="vertical")
        tbox.add_widget(Label(text=APP_NAME, bold=True, color=GOLD, font_size=sp(18), halign="left", valign="middle",
                              text_size=(Window.width * 0.6, None)))
        self.status_lbl = Label(text="", color=MUTED, font_size=sp(11), halign="left", valign="middle",
                                text_size=(Window.width * 0.6, None))
        tbox.add_widget(self.status_lbl)
        head.add_widget(tbox)
        head.add_widget(Btn("Lock", lambda: self.show_lock(), bg=CARD2, fg=GOLD, h=40, size=13, size_hint_x=None, width=dp(70)))
        rb.add_widget(head)
        self.page_sv = ScrollView(do_scroll_x=False, bar_width=dp(3))
        self.page = BoxLayout(orientation="vertical", size_hint_y=None, padding=dp(10), spacing=dp(10))
        self.page.bind(minimum_height=self.page.setter("height"))
        self.page_sv.add_widget(self.page)
        rb.add_widget(self.page_sv)
        nav = GridLayout(cols=6, size_hint_y=None, height=dp(58), padding=[dp(4), dp(4)], spacing=dp(4))
        _bg(nav, (0.07, 0.065, 0.055, 1), 0)
        self.nav_btns = {}
        for key, name in (("home", "Trade"), ("markets", "Markets"), ("practice", "Practice"),
                          ("live", "Live"), ("info", "Info"), ("settings", "Settings")):
            b = Btn(name, (lambda k=key: self.go(k)), bg=CARD, fg=MUTED, h=50, size=11, wrap=False)
            self.nav_btns[key] = b
            nav.add_widget(b)
        rb.add_widget(nav)
        self.render()

    def go(self, tab):
        self.tab = tab
        self.render()
        self.page_sv.scroll_y = 1

    def render(self):
        if self.locked or not hasattr(self, "page"):
            return
        for k, b in self.nav_btns.items():
            on = k == self.tab
            b._base = GOLD if on else CARD
            b._c.rgba = b._base
            b.color = INK if on else MUTED
        self.page.clear_widgets()
        try:
            getattr(self, "page_" + self.tab)()
        except Exception as e:   # never show a raw traceback
            self.page.add_widget(Lbl("Something went wrong showing this page (%s). Pull to refresh or switch tabs."
                                     % type(e).__name__, 14, RED))
        self.update_status()

    def update_status(self):
        if not hasattr(self, "status_lbl"):
            return
        parts = []
        parts.append("STOPPED" if self.settings["stopped"] else
                     ("Auto practice" if self.settings["trade_mode"] == "auto" else "Manual"))
        if self.settings["live_enabled"]:
            parts.append("LIVE ON")
        if self.last_check:
            parts.append("checked %s" % self.last_check.strftime("%H:%M"))
        if self.busy.locked():
            parts.append("checking...")
        self.status_lbl.text = " · ".join(parts)

    def add(self, w):
        self.page.add_widget(w)
        return w

    def stop_button(self):
        if self.settings["stopped"]:
            self.add(Btn("RESUME (trading is stopped)", self.resume, bg=CARD2, fg=GOLD, h=52))
        else:
            self.add(Btn("STOP", self.stop_all, bg=RED, fg=(1, 1, 1, 1), h=64, size=22))

    # ---------- Trade (home)
    def page_home(self):
        st = self.settings
        self.stop_button()
        c = self.add(Card(CARD2))
        c.add_widget(Lbl("[b]How to trade for free[/b]: when a pair shows BUY or SELL, tap [b]Open in MT5[/b]. The trade "
                         "(pair, side, lot 0.01, stop, target) is copied for you; place it yourself in MetaTrader 5. "
                         "This app never asks for your MT5 password.", 13, TEXT))
        c.add_widget(Lbl("Signals are practice only, not advice. %s" % core.NO_PROMISE, 12, GOLD))
        modes = GridLayout(cols=4, size_hint_y=None, height=dp(42), spacing=dp(4))
        for m in core.MODES:
            on = st["strategy"] == m
            modes.add_widget(Btn(core.MODE_NAMES[m], (lambda m=m: self.set_strategy(m)), bg=GOLD if on else CARD,
                                 fg=INK if on else MUTED, h=42, size=12))
        self.add(modes)
        self.add(Lbl(self.world_line(), 12, MUTED))
        if not self.directions:
            self.add(Lbl("Loading prices and signals..." if self.busy.locked() else
                         "No prices yet. Tap Refresh (needs internet).", 14, MUTED))
        dirs = [self.directions[s] for s in core.PAIRS if s in self.directions]
        dirs.sort(key=lambda d: (d["action"] == "WAIT", not d["tested"], core.PAIRS.index(d["sym"])))
        for d in dirs:
            self.signal_card(d)
        self.add(Btn("Refresh now", self.tick, bg=CARD2, fg=GOLD, h=44))
        if self.activity:
            c = self.add(Card())
            c.add_widget(Lbl("[b]Recent activity[/b]", 14, GOLD))
            for a in self.activity[:6]:
                c.add_widget(Lbl(a, 12, MUTED))

    def signal_card(self, d):
        s = d["sym"]
        act = d["action"]
        col = GREEN if act == "BUY" else RED if act == "SELL" else GOLD
        c = self.add(Card())
        price = (self.market.get(s) or {}).get("price")
        top = row(Lbl("[b]%s[/b]  %s" % (s, fmt_price(s, price)), 17, TEXT),
                  Lbl("[b][color=%s]%s[/color][/b]" % (color_hex(col), act), 22, col, halign="right"))
        c.add_widget(top)
        mode = self.settings["strategy"]
        tested = ("[color=%s]Tested: PASS[/color] (%s, daily walk-forward)" % (color_hex(GREEN), core.MODE_NAMES[mode])
                  if d["tested"] else "[color=%s]Tested: FAIL[/color] (%s) · practice only"
                  % (color_hex(RED), core.MODE_NAMES[mode]))
        if s == "XAUUSD":
            tested += " · gold prices from the gold future"
        c.add_widget(Lbl("Trend: daily [b]%s[/b] · weekly [b]%s[/b]" % (d["daily"], d["weekly"]), 13, TEXT))
        c.add_widget(Lbl(tested, 12, MUTED))
        if act in ("BUY", "SELL"):
            c.add_widget(Lbl("Entry about [b]%s[/b] · Stop [b]%s[/b] · Target [b]%s[/b] · Lot [b]0.01[/b]"
                             % (d["entry"], d["stop"], d["target"]), 14, TEXT))
            if d.get("exit_rule"):
                c.add_widget(Lbl(d["exit_rule"], 12, MUTED))
            note = core.risk_note(d, self.settings.get("balance_hint") or 0)
            if note:
                c.add_widget(Lbl(note, 12, RED if "SKIP" in note else MUTED))
            c.add_widget(row(Btn("Open in MT5", (lambda d=d: self.mt5_ticket(d)), bg=GOLD, h=46),
                             Btn("Practice this trade", (lambda d=d: self.manual_practice(d)), bg=CARD2, fg=GOLD, h=46)))
        else:
            c.add_widget(Lbl(d["why"], 12, MUTED))
        c.add_widget(Lbl("Practice only · not advice", 11, GOLD_DARK))

    def world_line(self):
        ss = core.sessions()
        opened = [c for c, o, _, _ in ss if o]
        txt = "Sessions open: %s" % (", ".join(opened) if opened else ("none (weekend)" if not core.market_open() else "none"))
        up = core.upcoming_high(self.news) if self.news else []
        if up:
            e = up[0]
            txt += " · Next big news: %s %s %s" % (e["cur"], e["title"], self.when(e["t"]))
        elif self.news is None:
            txt += " · News feed not loaded yet"
        return txt

    def when(self, t):
        mins = int((t - time.time()) // 60)
        local = datetime.fromtimestamp(t).strftime("%a %H:%M")
        if mins < 0:
            return "(%s, %d min ago)" % (local, -mins)
        if mins < 120:
            return "(%s, in %d min)" % (local, mins)
        return "(%s, in %dh)" % (local, mins // 60)

    def set_strategy(self, m):
        self.settings["strategy"] = m
        self.save_all()
        self.recompute_directions()
        self.render()

    def mt5_ticket(self, d):
        t = core.mt5_ticket(d)
        copied = copy_text(t)
        res = open_mt5()
        self.note("Open in MT5: %s" % t)
        self.info("Your trade for MT5",
                  "[b]%s[/b]\n\n%s\n\nIn MetaTrader 5: tap the pair, then [b]Trade[/b] (New order), pick [b]Market "
                  "execution[/b], set volume [b]0.01[/b], Stop Loss [b]%s[/b] and Take Profit [b]%s[/b], then tap "
                  "[b]%s by Market[/b].\n\n%s\n\nPractice only, not advice. %s"
                  % (t, ("Copied to your clipboard. " if copied else "") + res, d["stop"], d["target"],
                     d["action"].title(), core.risk_note(d, self.settings.get("balance_hint") or 0), core.NO_PROMISE))

    def manual_practice(self, d):
        m = core.practice_manual_open(self.practice, d, self.market, stopped=self.settings["stopped"],
                                      news=self.news if self.news is not None else False,
                                      mode=self.settings["strategy"], tf="1d")
        self.note(m)
        self.save_all()
        self.info("Practice", m)
        self.render()

    # ---------- Markets
    def page_markets(self):
        c = self.add(Card())
        c.add_widget(Lbl("[b]Live prices[/b]", 16, GOLD))
        grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(4))
        grid.bind(minimum_height=grid.setter("height"))
        for s in core.PAIRS:
            px = (self.market.get(s) or {}).get("price")
            q = self.quotes.get(s)
            extra = "  spread %.1f" % q[1] if q else ""
            grid.add_widget(Lbl("[b]%s[/b]" % s, 14, TEXT))
            grid.add_widget(Lbl("%s%s" % (fmt_price(s, px), extra), 14, TEXT, halign="right"))
        c.add_widget(grid)
        c.add_widget(Lbl("Public prices (may be a few minutes behind)." +
                         (" Spread from your broker via MetaApi." if self.quotes else
                          " Broker spread shows when the paid bridge is connected."), 11, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Market sessions[/b] (forex trades Sunday 17:00 to Friday 17:00 New York time)", 15, GOLD))
        for city, op, local, txt in core.sessions():
            c.add_widget(Lbl("[color=%s]•[/color] [b]%s[/b] %s · local time %s" % (
                color_hex(GREEN if op else MUTED), city, txt, local), 13, TEXT))
        c = self.add(Card())
        c.add_widget(Lbl("[b]High-impact news[/b] (USD, GBP, EUR, JPY)", 15, GOLD))
        if self.news is None:
            c.add_widget(Lbl(self.news_note or "Loading the calendar...", 13, MUTED))
        else:
            up = core.upcoming_high(self.news)
            if not up:
                c.add_widget(Lbl("No more high-impact events this week.", 13, MUTED))
            for e in up:
                c.add_widget(Lbl("[b]%s[/b] %s %s" % (e["cur"], e["title"], self.when(e["t"])), 13, TEXT))
            if self.news_note:
                c.add_widget(Lbl(self.news_note, 11, MUTED))
        c.add_widget(Lbl("New trades are blocked from 60 min before to 60 min after high-impact news on a pair's "
                         "currencies (bot, practice and cloud runner). " + core.NEWS_NOTE, 11, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Crypto scanner[/b] (information only)", 15, GOLD))
        if not self.crypto:
            c.add_widget(Lbl("Loading...", 13, MUTED))
        for x in self.crypto:
            c.add_widget(Lbl("[b]%s[/b] %s · trend %s · 24h %+.2f%% · RSI(14) %.0f" % (
                x["sym"], fmt_price(x["sym"], x["price"]), x["trend"], x["mom24"], x["rsi14"]), 13, TEXT))
            c.add_widget(Lbl("Volume vs last week: %.2fx · buyer share %.0f%% · %s" % (
                x["vol_ratio"], x["buy_share"], x["lean"]), 12, MUTED))
        c.add_widget(Lbl("Read-only public hourly data. Untested: no crypto trading, no exchange accounts, no wallets.",
                         11, MUTED))

    # ---------- Practice
    def page_practice(self):
        st = self.settings
        prices = {s: (self.market_for_practice().get(s) or {}).get("price") for s in core.PAIRS}
        prices = {k: v for k, v in prices.items() if v}
        sm = core.practice_summary(self.practice, prices)
        c = self.add(Card(CARD2))
        c.add_widget(Lbl("[b]Practice account[/b] (virtual money, starts at $1,000)", 16, GOLD))
        c.add_widget(Lbl("Balance [b]%s[/b] · Equity [b]%s[/b]" % (money(sm["balance"]), money(sm["equity"])), 15, TEXT))
        c.add_widget(Lbl("P/L today [b]%s[/b] · total [b]%s[/b]" % (signed(sm["pl_today"]), signed(sm["pl_total"])), 15,
                         GREEN if sm["pl_total"] >= 0 else RED))
        c.add_widget(Lbl("Closed trades %d · won %d%% · open %d" % (sm["trades"], sm["win_rate"], sm["open"]), 13, MUTED))
        why = core.guard_reasons(self.practice, sm["equity"], st["stopped"])
        c.add_widget(Lbl("Practice trading allowed: [b]%s[/b]" % ("YES" if not why else "NO"), 14,
                         GREEN if not why else RED))
        for w in why:
            c.add_widget(Lbl("- " + w, 12, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Mode[/b]", 15, GOLD))
        c.add_widget(row(
            Btn("Manual (you tap)", lambda: self.set_mode("manual"), bg=GOLD if st["trade_mode"] == "manual" else CARD2,
                fg=INK if st["trade_mode"] == "manual" else MUTED, h=44, size=13),
            Btn("Auto (follow signals)", lambda: self.set_mode("auto"), bg=GOLD if st["trade_mode"] == "auto" else CARD2,
                fg=INK if st["trade_mode"] == "auto" else MUTED, h=44, size=13)))
        c.add_widget(Lbl("Auto follows %s signals on %s (%s), checked every %d min while the app is open. Exits and stops "
                         "are always managed. Live trading stays behind its locks in both modes."
                         % (core.MODE_NAMES[st["strategy"]], ", ".join(st["practice_pairs"]) or "no pairs",
                            "daily" if st["tf"] == "1d" else "hourly", st["interval_min"]), 12, MUTED))
        c.add_widget(Lbl("Pairs for Auto:", 13, TEXT))
        g = GridLayout(cols=4, size_hint_y=None, spacing=dp(4))
        g.bind(minimum_height=g.setter("height"))
        for s in core.PAIRS:
            on = s in st["practice_pairs"]
            g.add_widget(Btn(s, (lambda s=s: self.toggle_pair(s)), bg=GOLD if on else CARD2, fg=INK if on else MUTED,
                             h=38, size=12))
        c.add_widget(g)
        tf = GridLayout(cols=2, size_hint_y=None, height=dp(40), spacing=dp(4))
        for k, n in (("1d", "Daily (tested)"), ("1h", "Hourly (all failed tests)")):
            tf.add_widget(Btn(n, (lambda k=k: self.set_tf(k)), bg=GOLD if st["tf"] == k else CARD2,
                              fg=INK if st["tf"] == k else MUTED, h=40, size=12))
        c.add_widget(tf)
        c = self.add(Card())
        c.add_widget(Lbl("[b]Open practice trades[/b]", 15, GOLD))
        if not self.practice["positions"]:
            c.add_widget(Lbl("None.", 13, MUTED))
        for s, p in list(self.practice["positions"].items()):
            px = prices.get(s)
            pl = core._pnl(p, px) if px else None
            c.add_widget(Lbl("[b]%s %s[/b] %.2f lot%s at %s · stop %s · target %s · P/L %s" % (
                s, p["side"].upper(), sum(l for _, l in p["fills"]),
                " x%d" % len(p["fills"]) if len(p["fills"]) > 1 else "", fmt_price(s, p["fills"][0][0]),
                fmt_price(s, p["sl"]), fmt_price(s, p["tp"]), signed(pl)), 13, TEXT))
            c.add_widget(Btn("Close %s now" % s, (lambda s=s, px=px: self.close_practice(s, px)), bg=CARD2, fg=GOLD, h=38,
                             size=13))
        c = self.add(Card())
        c.add_widget(Lbl("[b]History[/b]", 15, GOLD))
        if not self.practice["history"]:
            c.add_widget(Lbl("No closed practice trades yet. Daily signals are rare (about one a month per pair).",
                             13, MUTED))
        for h in self.practice["history"][:40]:
            c.add_widget(Lbl("%s [b]%s %s[/b] %s → %s · [color=%s]%+.2f[/color] · %s" % (
                h["closed"][:10], h["sym"], h["side"].upper(), fmt_price(h["sym"], h["entry"]),
                fmt_price(h["sym"], h["exit"]), color_hex(GREEN if h["pnl"] >= 0 else RED), h["pnl"], h["why"]), 12, TEXT))
        self.add(Btn("Reset practice account", lambda: self.confirm(
            "Reset practice?", "This clears practice trades and history and starts again at $1,000.", "Reset",
            self.reset_practice), bg=CARD2, fg=MUTED, h=42, size=13))

    def market_for_practice(self):
        return self.market_tf if self.settings["tf"] == "1h" and self.market_tf else self.market

    def set_mode(self, m):
        self.settings["trade_mode"] = m
        self.note("Mode: %s" % ("Auto (follow signals)" if m == "auto" else "Manual"))
        self.save_all(); self.render()
        if m == "auto":
            self.tick()

    def toggle_pair(self, s):
        p = self.settings["practice_pairs"]
        if s in p:
            p.remove(s)
        else:
            p.append(s)
        self.save_all(); self.render()

    def set_tf(self, k):
        self.settings["tf"] = k
        self.save_all(); self.render(); self.tick()

    def close_practice(self, s, px):
        self.note(core.practice_close_now(self.practice, s, px))
        self.save_all(); self.render()

    def reset_practice(self):
        self.practice = core.new_practice()
        self.note("Practice account reset to $1,000")
        self.save_all(); self.render()

    # ---------- Live (paid bridge)
    def page_live(self):
        st = self.settings
        c = self.add(Card(CARD2))
        c.add_widget(Lbl("[b]%s[/b]" % core.NO_PROMISE, 16, GOLD))
        c.add_widget(Lbl("The free way is Manual: Trade tab → Open in MT5. Automatic live trading needs the optional paid "
                         "MetaApi bridge (Settings → Advanced) and stays locked until every check below passes.", 13, TEXT))
        self.stop_button()
        c = self.add(Card())
        c.add_widget(Lbl("[b]Real account[/b]", 15, GOLD))
        if not self.vault.get("token"):
            c.add_widget(Lbl("Not connected (optional). Add MetaApi in Settings → Advanced (paid bridge).", 13, MUTED))
        elif not self.account:
            c.add_widget(Lbl(self.conn_msg or "Connecting...", 13, MUTED))
        else:
            a = self.account
            cur = a.get("currency", "")
            c.add_widget(Lbl("Balance [b]%.2f %s[/b] · Equity [b]%.2f[/b]" % (a["balance"], cur, a["equity"]), 15, TEXT))
            c.add_widget(Lbl("Today's P/L: [b]%s[/b] (closed %s, open %s)" % (
                signed(a["today"]), signed(a["realized"]), signed(a["floating"])), 14, TEXT))
            c.add_widget(Lbl("Open positions: %d" % len(a["positions"]), 14, TEXT))
            for p in a["positions"]:
                side = "BUY" if "BUY" in p.get("type", "") else "SELL"
                c.add_widget(Lbl("  %s %s %s @ %s · P/L %s" % (p.get("symbol"), side, p.get("volume"), p.get("openPrice"),
                                                               signed(p.get("profit", 0))), 13, MUTED))
            why = a["why"]
            c.add_widget(Lbl("Trading allowed: [b]%s[/b]" % ("YES" if not why else "NO"), 16, GREEN if not why else RED))
            for w in why:
                c.add_widget(Lbl("- " + w, 12, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Live locks[/b] (all must pass)", 15, GOLD))
        if not self.locks:
            c.add_widget(Lbl("All locks pass.", 13, GREEN))
        for w in self.locks:
            c.add_widget(Lbl("[color=%s]x[/color] %s" % (color_hex(RED), w), 13, TEXT))
        c.add_widget(Lbl("Guards always on: 1% risk per trade · skip if 0.01 lot risks over 3% · stop for the day at "
                         "-3% · kill switch at 15% drawdown · max 3 trades a day · no trades 60 min around big news.",
                         12, MUTED))
        phrase = field('Type "%s"' % core.LIVE_PHRASE)
        c.add_widget(phrase)

        def accept():
            if phrase.text.strip() == core.LIVE_PHRASE:
                st["live_accepted"] = True
                self.note("Risk accepted for live trading")
                self.save_all(); self.tick()
            else:
                self.info("Not accepted", 'Type exactly: %s' % core.LIVE_PHRASE)
        c.add_widget(Btn("Accept the risk", accept, bg=CARD2, fg=GOLD, h=42, size=13))
        if st["live_enabled"]:
            c.add_widget(Btn("Turn live trading OFF", self.live_off, bg=CARD2, fg=RED, h=46))
        else:
            c.add_widget(Btn("Turn live trading ON", self.live_on, bg=GOLD if not self.locks else CARD2,
                             fg=INK if not self.locks else MUTED, h=46))
        elig = [x for t, m, x in core.passed_list() if m == st["strategy"] and t == "1d" and core.exact_pip_value(x)]
        c.add_widget(Lbl("Live pairs for %s (only tested PASS pairs with USD can be chosen):"
                         % core.MODE_NAMES[st["strategy"]], 12, MUTED))
        if elig:
            g = GridLayout(cols=3, size_hint_y=None, height=dp(40), spacing=dp(4))
            for x in elig:
                on = x in st["live_pairs"]
                g.add_widget(Btn(x, (lambda x=x: self.toggle_live_pair(x)), bg=GOLD if on else CARD2,
                                 fg=INK if on else MUTED, h=40, size=12))
            c.add_widget(g)
        else:
            c.add_widget(Lbl("None for this strategy: pick Mean reversion or Auto on the Trade tab.", 12, RED))
        c.add_widget(Lbl("Chosen: %s. Use either the phone or the cloud runner for live, not both."
                         % (", ".join(st["live_pairs"]) or "none"), 12, MUTED))

    def toggle_live_pair(self, x):
        lp = self.settings["live_pairs"]
        if x in lp:
            lp.remove(x)
        else:
            lp.append(x)
        self.settings["live_enabled"] = False
        self.save_all(); self.tick(); self.render()

    def live_on(self):
        if self.locks:
            self.info("Live stays locked", "\n".join("- " + w for w in self.locks))
            return
        self.settings["live_enabled"] = True
        self.note("Live trading turned ON")
        self.save_all(); self.render()

    def live_off(self):
        self.settings["live_enabled"] = False
        self.note("Live trading turned OFF")
        self.save_all(); self.render()

    # ---------- STOP
    def stop_all(self):
        self.settings["stopped"] = True
        self.settings["live_enabled"] = False
        self.note("STOP pressed: all automatic trading stopped")
        self.save_all(); self.render()
        if self.vault.get("token") and self.connected:
            self.confirm("Stopped", "All automatic trading is stopped. Also close the open live trades this bot made "
                         "(practice trades stay)?", "Close bot's live trades", self.close_live_positions,
                         cancel="Keep them")
        else:
            self.info("Stopped", "All automatic trading is stopped. Press RESUME to allow it again.")

    def close_live_positions(self):
        def work():
            try:
                api = self.api()
                n = core.close_bot_positions(api)
                msg = "Closed %d live trade(s) made by the bot." % n
            except Exception as e:
                msg = "Could not close: %s" % e
            Clock.schedule_once(lambda dt: (self.note(msg), self.info("STOP", msg), self.render()))
        threading.Thread(target=work, daemon=True).start()

    def resume(self):
        self.settings["stopped"] = False
        self.note("Resumed (live stays OFF until you turn it on)")
        self.save_all(); self.render()

    # ---------- Info
    def page_info(self):
        c = self.add(Card(CARD2))
        c.add_widget(Lbl("[b]%s[/b]" % core.NO_PROMISE, 17, GOLD))
        c.add_widget(Lbl("Forex and gold trading can lose all the money in an account, quickly. Past test results do "
                         "not promise future results. Only trade money you can afford to lose.", 13, TEXT))
        texts = {
            "trend": "Follows the big trend: buys when price breaks above its recent high while above the 200-bar average "
                     "(sells the opposite). Stop 1.5-2 ATR, target 2-3 ATR.",
            "meanrev": "Buys a short dip inside an uptrend (RSI(2) very low or a close under the lower Bollinger band), "
                       "sells a short bounce in a downtrend. Exits when price closes back over the 5-bar average, after "
                       "a time limit, or at the 2.5 ATR stop.",
            "grid": "A capped, safe grid: starts on a dip in the trend, adds at most 2 more entries, every one the SAME "
                    "size (never doubling), with one hard stop for the whole basket. Whole basket risk is 1%.",
            "auto": "Switches by trend strength: ADX(14) high → trend rules, low → mean-reversion rules.",
        }
        for m in core.MODES:
            c = self.add(Card())
            c.add_widget(Lbl("[b]%s[/b]" % core.MODE_NAMES[m], 15, GOLD))
            c.add_widget(Lbl(texts[m], 13, TEXT))
            res = []
            for (tf, mm, s), (ok, _) in sorted(core.WF.items()):
                if mm == m and ok:
                    res.append("%s %s" % (s, "daily" if tf == "1d" else "hourly"))
            c.add_widget(Lbl("Walk-forward PASS: %s" % (", ".join(res) if res else "none"), 13,
                             GREEN if res else RED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]How it was tested[/b]", 15, GOLD))
        c.add_widget(Lbl("Walk-forward: settings picked on the oldest 70% of ~10 years of free daily data, then judged "
                         "once on the newest 30% it never saw. Costs included (spread + slippage). A pass needs profit "
                         "factor over 1.2, a gain, max drawdown under 15% and 20+ unseen trades. Hourly tests were run on "
                         "EURUSD, GBPUSD and USDJPY only, and all failed.", 13, TEXT))
        n_all = len([1 for k in core.WF if k[0] == "1d"])
        n_ok = len([1 for k, v in core.WF.items() if k[0] == "1d" and v[0]])
        c.add_widget(Lbl("Honest view: %d of %d daily tests passed. With that many tries, some passes can be luck, "
                         "and each pass is only 20-35 trades over about 3 years. Mean reversion on GBPUSD daily made "
                         "+3.2%% in its unseen test. Treat everything as practice first, for months." % (n_ok, n_all),
                         13, TEXT))
        rows_ = []
        for (tf, m, s), (ok, _) in sorted(core.WF.items(), key=lambda kv: (kv[0][2], kv[0][1])):
            if tf == "1d":
                rows_.append("%s %s: [color=%s]%s[/color]" % (s, core.MODE_NAMES[m], color_hex(GREEN if ok else RED),
                                                              "PASS" if ok else "fail"))
        c.add_widget(Lbl(" · ".join(rows_), 11, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Risks and limits[/b]", 15, GOLD))
        for t in ("Live trading is possible only for tested PASS pairs that contain USD, with the paid bridge connected, "
                  "enough balance for the 3% rule at 0.01 lot, and the typed risk acceptance.",
                  "Small accounts: with about $10, even 0.01 lot on GBPUSD daily risks far more than 3%, so the bot "
                  "skips every trade. It needs roughly $600 or more.",
                  "Cross pairs (EURGBP, EURJPY, GBPJPY) and gold are practice only for now.",
                  "Crypto shows information only: no crypto trades, accounts or wallets.",
                  core.NEWS_NOTE,
                  "Prices from free public feeds can be late or briefly wrong. Your broker's prices are what count.",
                  "Your PIN, MetaApi token and account id stay on this phone (token and id encrypted with a key made "
                  "from your PIN). No app is perfectly secure: keep your phone locked and your token private."):
            c.add_widget(Lbl("- " + t, 13, TEXT))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Data used[/b]", 15, GOLD))
        c.add_widget(Lbl("Prices: Yahoo Finance public charts. News: ForexFactory weekly calendar (faireconomy.media). "
                         "Crypto: Binance public market data (read-only). Real account: MetaApi, only if you connect it.",
                         12, MUTED))
        self.add(Lbl("%s · version %s (build %s)" % (CREDIT, VERSION, BUILD_NUMBER), 12, MUTED, halign="center"))

    # ---------- Settings
    def page_settings(self):
        st = self.settings
        c = self.add(Card())
        c.add_widget(Lbl("[b]Your MT5 balance[/b] (optional, for the 3% risk check on manual trades)", 14, GOLD))
        bal = field("e.g. 9.72", text=("%g" % st["balance_hint"]) if st.get("balance_hint") else "", numeric=True)
        c.add_widget(bal)

        def save_bal():
            try:
                st["balance_hint"] = max(0.0, float(bal.text or 0))
            except ValueError:
                st["balance_hint"] = 0.0
            self.save_all(); self.info("Saved", "Balance saved for the risk check.")
        c.add_widget(Btn("Save balance", save_bal, bg=CARD2, fg=GOLD, h=42, size=13))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Check every[/b] (while the app is open)", 14, GOLD))
        g = GridLayout(cols=3, size_hint_y=None, height=dp(40), spacing=dp(4))
        for m in (5, 10, 15):
            on = st["interval_min"] == m
            g.add_widget(Btn("%d min" % m, (lambda m=m: self.set_interval(m)), bg=GOLD if on else CARD2,
                             fg=INK if on else MUTED, h=40, size=13))
        c.add_widget(g)
        c.add_widget(Lbl("The app checks only while it is open. To keep running when your phone is off, use the cloud "
                         "runner below.", 12, MUTED))
        c = self.add(Card())
        c.add_widget(Lbl("[b]Security[/b]", 14, GOLD))
        c.add_widget(Lbl("The app locks itself when you leave it. 5 wrong tries cause a wait that grows each time.",
                         12, MUTED))
        c.add_widget(Btn("Change PIN or password", self.change_pin, bg=CARD2, fg=GOLD, h=42, size=13))
        self.cloud_section()
        self.advanced_section()
        c = self.add(Card())
        c.add_widget(Lbl("[b]About[/b]", 14, GOLD))
        c.add_widget(Lbl("%s %s (build %s, code %s)\n%s" % (APP_NAME, VERSION, BUILD_NUMBER, BUILD_COMMIT, CREDIT),
                         13, TEXT))
        c.add_widget(Lbl("Newest app: %s" % DOWNLOAD_LINK, 11, MUTED))

    def set_interval(self, m):
        self.settings["interval_min"] = m
        self.save_all(); self.schedule_ticks(); self.render()

    def cloud_section(self):
        c = self.add(Card())
        c.add_widget(Btn(("- " if self.show_cloud else "+ ") + "Cloud runner (optional, free)", self.toggle_cloud,
                         bg=CARD2, fg=GOLD, h=44, size=14))
        if not self.show_cloud:
            return
        steps = [
            "A phone app cannot run while the phone is off. The cloud runner is a free scheduled job on GitHub that "
            "runs the same bot every 30 minutes on weekdays, plus once a day after the daily candle closes.",
            "It needs the paid MetaApi bridge (it reads your account through MetaApi). Without its two secrets it does "
            "nothing and exits.",
            "1. On a computer or the GitHub app, open github.com/ssalimuto/Genius-app (you must be signed in as the owner).",
            "2. Tap Settings → Secrets and variables → Actions.",
            "3. Under Secrets, tap New repository secret. Name: METAAPI_TOKEN. Value: your MetaApi token. Save.",
            "4. New repository secret again. Name: METAAPI_ACCOUNT_ID. Value: your MetaApi account id. Save.",
            "5. It runs as a DRY RUN (no real orders). Real orders only if you also add a repository variable "
            "(Variables tab) LIVE = true AND the bot's own locks pass (tested PASS pair, enough balance for the 3% rule).",
            "6. To stop it: set the variable STOP = true, or delete LIVE, or open Actions → Profits cloud runner → "
            "Disable workflow.",
            "The repository is public, so its logs only say ran / signal / skipped. They never show balances, the "
            "token or the account id. Saved state is encrypted with your token. GitHub pauses scheduled jobs after "
            "60 days without changes in the repository.",
        ]
        for s in steps:
            c.add_widget(Lbl(s, 12, TEXT))

    def toggle_cloud(self):
        self.show_cloud = not self.show_cloud
        self.render()

    def toggle_adv(self):
        self.show_adv = not self.show_adv
        self.render()

    def advanced_section(self):
        st = self.settings
        c = self.add(Card())
        c.add_widget(Btn(("- " if self.show_adv else "+ ") + "Advanced (paid bridge): MetaApi", self.toggle_adv,
                         bg=CARD2, fg=GOLD, h=44, size=14))
        if not self.show_adv:
            return
        c.add_widget(Lbl("[b]How to connect[/b] (optional; the free way is Open in MT5)", 14, GOLD))
        for t in ("Any MT4 or MT5 broker works through MetaApi: you add the account there with its server name. "
                  "For Pocket Option the server is [b]PoTrade-MT5[/b].",
                  "1. Make an account at metaapi.cloud. Adding an MT5 account costs about $2, then about $9 a month "
                  "while it is deployed (check MetaApi's current prices).",
                  "2. On metaapi.cloud add your MT4/MT5 account: login number, server, and password. You type the "
                  "password on MetaApi's website only. This app never asks for it.",
                  "3. Copy your MetaApi API token and the account id, and paste them below.",
                  "4. Press Test connection. It shows your balance or a plain error."):
            c.add_widget(Lbl(t, 12, TEXT))
        tok = self.vault.get("token")
        acc = self.vault.get("account")
        c.add_widget(Lbl("Saved token: %s\nSaved account id: %s" % (core.mask(tok), core.mask(acc)), 12, MUTED))
        t_in = field("Paste MetaApi token", password=True)
        a_in = field("MetaApi account id", password=True)
        c.add_widget(t_in)
        c.add_widget(a_in)
        g = GridLayout(cols=4, size_hint_y=None, height=dp(38), spacing=dp(4))
        for r in core.REGIONS:
            on = st["region"] == r
            g.add_widget(Btn(r, (lambda r=r: self.set_region(r)), bg=GOLD if on else CARD2, fg=INK if on else MUTED,
                             h=38, size=11))
        c.add_widget(Lbl("Region (Test connection finds it for you):", 12, MUTED))
        c.add_widget(g)
        sfx = field("Symbol ending at your broker, if any (e.g. .r)", text=st.get("suffix", ""))
        c.add_widget(sfx)

        def save():
            if t_in.text.strip():
                self.vault.put("token", t_in.text.strip())
            if a_in.text.strip():
                self.vault.put("account", a_in.text.strip())
            st["suffix"] = sfx.text.strip()[:8]
            self.save_all()
            t_in.text = a_in.text = ""
            self.info("Saved", "Saved on this phone, encrypted with a key from your PIN.")
            self.render()
        c.add_widget(row(Btn("Save", save, h=44, size=14),
                         Btn("Test connection", self.test_conn, bg=CARD2, fg=GOLD, h=44, size=14)))
        c.add_widget(Btn("Remove MetaApi details", lambda: self.confirm(
            "Remove?", "Removes the token and account id from this phone and turns live off.", "Remove",
            self.remove_creds), bg=CARD2, fg=MUTED, h=40, size=13))
        c.add_widget(Lbl("The token is only ever sent to MetaApi's own servers (*.agiliumtrade.ai), over HTTPS.",
                         11, MUTED))

    def set_region(self, r):
        self.settings["region"] = r
        self.save_all(); self.render()

    def remove_creds(self):
        self.vault.d.get("secrets", {}).clear()
        self.vault._save()
        self.settings["live_enabled"] = False
        self.connected = False
        self.account = None
        self.save_all(); self.render()

    def api(self):
        return core.MetaApi(self.vault.get("token"), self.vault.get("account"), self.settings["region"],
                            self.settings.get("suffix", ""))

    def test_conn(self):
        tok, acc = self.vault.get("token"), self.vault.get("account")
        self.info("Testing...", "Checking your MetaApi account.")

        def work():
            ok, msg, region, info = core.test_connection(tok, acc, self.settings["region"], self.settings.get("suffix", ""))

            def done(dt):
                if region:
                    self.settings["region"] = region
                self.connected = ok
                self.conn_msg = msg
                self.save_all()
                self.close_popups()
                self.info("Connected" if ok else "Not connected", msg)
                self.render()
                if ok:
                    self.tick()
            Clock.schedule_once(done)
        threading.Thread(target=work, daemon=True).start()

    def change_pin(self):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(10))
        old = field("Current PIN or password", password=True)
        n1 = field("New PIN (4+ digits) or password (6+)", password=True)
        n2 = field("New again", password=True)
        msg = Lbl("", 13, RED)
        for w in (old, n1, n2, msg):
            box.add_widget(w)
        pop = Popup(title="Change PIN", content=box, size_hint=(0.92, None), height=dp(380),
                    separator_color=GOLD, background_color=CARD)

        def go():
            ok, m = self.vault.unlock(old.text)
            if not ok:
                msg.text = m; return
            if n1.text != n2.text:
                msg.text = "The new entries are different."; return
            try:
                self.vault.set_pin(n1.text, keep_secrets=True)
            except ValueError as e:
                msg.text = str(e); return
            pop.dismiss()
            self.info("Done", "PIN changed.")
        box.add_widget(Btn("Change", go, h=44))
        pop.open()

    # ---------- popups
    def info(self, title, text):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        sv = ScrollView(size_hint_y=None, height=dp(260))
        lb = Lbl(text, 14, TEXT)
        sv.add_widget(lb)
        box.add_widget(sv)
        pop = Popup(title=title, content=box, size_hint=(0.92, None), height=dp(400), separator_color=GOLD,
                    title_color=GOLD, background_color=CARD)
        box.add_widget(Btn("OK", pop.dismiss, h=44))
        self._pops = getattr(self, "_pops", []) + [pop]
        pop.open()

    def close_popups(self):
        for p in getattr(self, "_pops", []):
            try:
                p.dismiss()
            except Exception:
                pass
        self._pops = []

    def confirm(self, title, text, yes, cb, cancel="Cancel"):
        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))
        box.add_widget(Lbl(text, 14, TEXT))
        pop = Popup(title=title, content=box, size_hint=(0.92, None), height=dp(330), separator_color=GOLD,
                    title_color=GOLD, background_color=CARD)
        box.add_widget(Widget())

        def y():
            pop.dismiss(); cb()
        box.add_widget(row(Btn(cancel, pop.dismiss, bg=CARD2, fg=MUTED, h=44, size=13), Btn(yes, y, bg=RED,
                                                                                            fg=(1, 1, 1, 1), h=44, size=13)))
        pop.open()

    # ---------- the periodic check
    def schedule_ticks(self):
        if self._tick_ev:
            self._tick_ev.cancel()
        self._tick_ev = Clock.schedule_interval(lambda dt: self.tick(), max(5, self.settings["interval_min"]) * 60)

    def tick(self):
        if self.locked or self.busy.locked():
            return
        threading.Thread(target=self._tick_work, daemon=True).start()
        Clock.schedule_once(lambda dt: self.update_status(), 0.1)

    def recompute_directions(self):
        mode = self.settings["strategy"]
        out = {}
        for s, m in self.market.items():
            try:
                out[s] = core.direction(mode, s, m["bars"], m["price"], "1d")
            except Exception:
                pass
        self.directions = out

    def _tick_work(self):
        if not self.busy.acquire(blocking=False):
            return
        events = []
        try:
            st = self.settings
            market = {}
            for s in core.PAIRS:
                try:
                    market[s] = core.yahoo_chart(s, "1d")
                except Exception:
                    if s in self.market:
                        market[s] = self.market[s]
            for k in ("USDJPY", "GBPUSD", "EURUSD"):
                if (market.get(k) or {}).get("price"):
                    core.RATES[k] = market[k]["price"]
            self.market = market
            self.recompute_directions()
            mtf = {}
            if st["tf"] == "1h":
                for s in set(st["practice_pairs"]) | set(self.practice["positions"]):
                    try:
                        mtf[s] = core.yahoo_chart(s, "1h")
                    except Exception:
                        pass
            self.market_tf = mtf
            news, note = core.fetch_news(self._path("news_cache.json"))
            self.news, self.news_note = news, note
            cr = []
            for c in core.CRYPTO:
                try:
                    cr.append(core.crypto_scan(c))
                except Exception:
                    pass
            self.crypto = cr
            # practice: always manage exits; follow signals only in Auto
            pm = self.market_for_practice()
            events += core.practice_step(self.practice, st["strategy"], st["tf"],
                                         st["practice_pairs"] if st["trade_mode"] == "auto" else [],
                                         pm, follow=st["trade_mode"] == "auto", stopped=st["stopped"],
                                         news=news if news is not None else False)
            # real account (paid bridge only)
            if self.vault.get("token") and self.vault.get("account"):
                try:
                    api = self.api()
                    acc = core.account_status(api, self.live_state, st["strategy"], "1d", st["live_pairs"],
                                              st["stopped"], st["live_accepted"], news=news)
                    self.account, self.connected, self.conn_msg = acc, True, ""
                    q = {}
                    for s in core.MAIN_PAIRS:
                        try:
                            q[s] = api.quote(s)
                        except Exception:
                            pass
                    self.quotes = q
                    self.locks = core.live_locks(True, acc["balance"], st["strategy"], "1d", st["live_pairs"],
                                                 core.LIVE_PHRASE if st["live_accepted"] else "", acc["bars"])
                    if st["live_enabled"] and not self.locks and not st["stopped"]:
                        events += core.live_step(api, self.live_state, st["strategy"], "1d", st["live_pairs"],
                                                 st["stopped"], st["live_accepted"], news=news)
                        if self.live_state.get("killed"):
                            st["live_enabled"] = False
                    elif st["live_enabled"] and self.locks:
                        st["live_enabled"] = False
                        events.append("Live turned OFF: %s" % self.locks[0])
                except Exception as e:
                    self.connected = False
                    self.account = None
                    self.conn_msg = str(e) if isinstance(e, core.MetaApiError) else "Could not reach MetaApi."
                    self.locks = core.live_locks(False, None, st["strategy"], "1d", st["live_pairs"],
                                                 core.LIVE_PHRASE if st["live_accepted"] else "", {})
            else:
                self.connected, self.account, self.quotes = False, None, {}
                self.locks = core.live_locks(False, None, st["strategy"], "1d", st["live_pairs"],
                                             core.LIVE_PHRASE if st["live_accepted"] else "", {})
            self.last_check = datetime.now()
        except Exception as e:
            events.append("Check failed: %s" % (e if isinstance(e, (RuntimeError, core.MetaApiError)) else type(e).__name__))
        finally:
            self.busy.release()

        def done(dt):
            for e in events:
                self.note(e)
            self.save_all()
            self.render()
        Clock.schedule_once(done)

    # ---------- lifecycle: lock when the app goes to the background
    def on_pause(self):
        self.paused_at = time.time()
        self.save_all()
        self.vault.lock()
        self.locked = True
        return True

    def on_resume(self):
        self.show_lock()

    def on_stop(self):
        self.save_all()


if __name__ == "__main__":
    ProfitsApp().run()
