# my_ai_app.py - private phone AI with buttons and voice (Kivy). Owner ssalimuto, plus private guest accounts.
import os, re, ssl, json, time, base64, hashlib, hmac, socket, threading, random, urllib.request, urllib.error, urllib.parse
from types import MappingProxyType

VERSION = "112.6"
NEEDS_APK = "109.0"     # the oldest installed app this code can run inside
LIVE_DIR = os.path.join(os.path.abspath(os.getcwd()), "live")
LIVE_CODE = os.path.join(LIVE_DIR, "genius_live.py")
LIVE_INFO = os.path.join(LIVE_DIR, "genius_live.json")
SHIP_VERSION = os.environ.get("GENIUS_SHIP_VERSION") or VERSION   # version of the installed app


# 112.2: Cloudflare (in front of Groq and others) answers 403 to Python's default "Python-urllib" name,
# so every web request from Genius now says who it is.
if not getattr(urllib.request.urlopen, "_genius_ua", False):
    _orig_urlopen = urllib.request.urlopen

    def _urlopen_ua(url, *a, **k):
        if isinstance(url, str):
            url = urllib.request.Request(url)
        if not url.has_header("User-agent"):
            url.add_header("User-Agent", "Genius/" + VERSION + " (Android)")
        return _orig_urlopen(url, *a, **k)
    _urlopen_ua._genius_ua = True
    urllib.request.urlopen = _urlopen_ua


def _vt(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except Exception:
        return (0,)


def _boot_live():
    """Quiet updates: if a newer, verified Genius is waiting, run it instead of this copy.
    A version that fails to start twice is dropped and this copy runs."""
    if os.environ.get("GENIUS_LIVE"):
        return False
    try:
        info = json.load(open(LIVE_INFO))
        src = open(LIVE_CODE, "rb").read()
        if hashlib.sha256(src).hexdigest() != info.get("sha"):
            return False
        if _vt(info.get("version")) <= _vt(VERSION) or _vt(info.get("needs_apk", "0")) > _vt(VERSION):
            return False
        if info.get("tries", 0) >= 2 and not info.get("ok"):
            return False
        info["tries"] = info.get("tries", 0) + 1
        json.dump(info, open(LIVE_INFO, "w"))
    except Exception:
        return False
    os.environ["GENIUS_LIVE"] = "1"
    os.environ["GENIUS_SHIP_VERSION"] = VERSION
    exec(compile(src, LIVE_CODE, "exec"), {"__name__": "__main__", "__file__": LIVE_CODE})
    return True


def live_started_ok():
    """Called once Genius is up: marks the quiet update as good."""
    if not os.environ.get("GENIUS_LIVE"):
        return
    try:
        info = json.load(open(LIVE_INFO))
        if not info.get("ok"):
            info["ok"] = True
            json.dump(info, open(LIVE_INFO, "w"))
    except Exception:
        pass


if __name__ == "__main__" and _boot_live():
    raise SystemExit(0)

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.image import Image as KivyImage
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.metrics import dp

Window.softinput_mode = ""   # 110.3: screen never slides; the typing box lifts itself above the keyboard


_KB_VIEWS = {}


def android_sdk():
    """Android version number (API level); 0 when not on a phone."""
    try:
        from jnius import autoclass
        return int(autoclass("android.os.Build$VERSION").SDK_INT)
    except Exception:
        return 0


def keyboard_overlap():
    """Pixels of the Kivy window hidden by the phone keyboard (0 when it's closed or on a computer)."""
    if not ANDROID_OK():
        return 0
    try:
        if "content" not in _KB_VIEWS:
            from jnius import autoclass
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            _KB_VIEWS["content"] = act.getWindow().getDecorView().findViewById(autoclass("android.R$id").content)
            _KB_VIEWS["Rect"] = autoclass("android.graphics.Rect")
        v = _KB_VIEWS["content"]
        r = _KB_VIEWS["Rect"]()
        v.getWindowVisibleDisplayFrame(r)
        loc = [0, 0]
        v.getLocationOnScreen(loc)
        hidden = (loc[1] + v.getHeight()) - r.bottom
        return int(hidden) if hidden > dp(80) else 0     # ignore the nav bar / small insets
    except Exception:
        return 0


def ANDROID_OK():
    try:
        from kivy.utils import platform as _pf
        return _pf == "android"
    except Exception:
        return False

# ---- theme colours ----
# Genius Luxe theme: midnight glass, liquid gold, electric violet
BG       = (0.035, 0.04, 0.08, 1)
BG_TOP   = (0.10, 0.07, 0.22, 1)
BG_BOT   = (0.02, 0.03, 0.07, 1)
HEADER   = (0.09, 0.08, 0.20, 0.92)
PANEL    = (1, 1, 1, 0.06)
GOLD     = (1.00, 0.78, 0.30, 1)
GOLD2    = (0.95, 0.52, 0.18, 1)
BLUE     = (0.33, 0.42, 1.00, 1)
BLUE2    = (0.62, 0.30, 0.98, 1)
GREY     = (1, 1, 1, 0.10)
RED      = (0.95, 0.30, 0.42, 1)
RED2     = (0.75, 0.15, 0.38, 1)
TEXTCOL  = (0.96, 0.96, 1.00, 1)
HINT     = (0.62, 0.64, 0.78, 1)

# ---- Gold and Diamond looks (type: theme gold / theme diamond / theme classic) ----
THEME_FILE = os.path.join(os.path.abspath(os.getcwd()), "theme.txt")
THEMES = {
    "gold": dict(BG=(0.03, 0.022, 0.0, 1), BG_TOP=(0.13, 0.095, 0.02, 1), BG_BOT=(0.015, 0.01, 0.0, 1),
                 HEADER=(0.11, 0.08, 0.02, 0.90), PANEL=(1.0, 0.85, 0.45, 0.07),
                 GOLD=(1.00, 0.80, 0.26, 1), GOLD2=(0.80, 0.52, 0.10, 1),
                 BLUE=(0.86, 0.62, 0.16, 1), BLUE2=(0.55, 0.34, 0.05, 1),
                 GREY=(1.0, 0.85, 0.45, 0.12), TEXTCOL=(1.0, 0.97, 0.88, 1), HINT=(0.80, 0.70, 0.48, 1),
                 LINE=(1.00, 0.78, 0.30), SPARK=0),
    "diamond": dict(BG=(0.01, 0.02, 0.05, 1), BG_TOP=(0.05, 0.10, 0.20, 1), BG_BOT=(0.008, 0.015, 0.045, 1),
                    HEADER=(0.06, 0.11, 0.22, 0.90), PANEL=(0.75, 0.92, 1.0, 0.07),
                    GOLD=(0.72, 0.93, 1.00, 1), GOLD2=(0.42, 0.70, 1.00, 1),
                    BLUE=(0.45, 0.72, 1.00, 1), BLUE2=(0.68, 0.52, 1.00, 1),
                    GREY=(0.75, 0.92, 1.0, 0.12), TEXTCOL=(0.95, 0.99, 1.0, 1), HINT=(0.64, 0.78, 0.92, 1),
                    LINE=(0.62, 0.88, 1.00), SPARK=1),
}
try:
    THEME = open(THEME_FILE).read().strip().lower() or "gold"
except Exception:
    THEME = "gold"
if THEME not in THEMES and THEME != "classic":
    THEME = "gold"
if THEME in THEMES:
    _t = THEMES[THEME]
    BG, BG_TOP, BG_BOT, HEADER, PANEL = _t["BG"], _t["BG_TOP"], _t["BG_BOT"], _t["HEADER"], _t["PANEL"]
    GOLD, GOLD2, BLUE, BLUE2, GREY = _t["GOLD"], _t["GOLD2"], _t["BLUE"], _t["BLUE2"], _t["GREY"]
    TEXTCOL, HINT = _t["TEXTCOL"], _t["HINT"]
Window.clearcolor = BG

from kivy.graphics.texture import Texture
from kivy.graphics import Line
from kivy.animation import Animation
from kivy.lang import Builder


_TEX_CACHE = {}


def gradient_texture(top, bottom, steps=64, horizontal=False):
    key = (tuple(top), tuple(bottom), steps, horizontal)
    if key in _TEX_CACHE:
        return _TEX_CACHE[key]
    tex = Texture.create(size=(steps, 1) if horizontal else (1, steps), colorfmt="rgba")
    buf = bytearray()
    for i in range(steps):
        t = i / (steps - 1)
        a, b = (top, bottom) if horizontal else (bottom, top)   # textures start at the bottom
        buf += bytes(int(255 * (a[k] + (b[k] - a[k]) * t)) for k in range(4))
    tex.blit_buffer(bytes(buf), colorfmt="rgba", bufferfmt="ubyte")
    tex.wrap = "clamp_to_edge"
    _TEX_CACHE[key] = tex
    return tex


_WALL_TEX = {}


def wallpaper_texture():
    """The doodle wallpaper, recoloured for the current look (gold lines on black,
    or icy diamond lines with sparkles). Made once, then kept on the phone."""
    if THEME not in THEMES:
        return None
    if THEME in _WALL_TEX:
        return _WALL_TEX[THEME]
    tex = None
    try:
        from kivy.core.image import Image as CoreImage
        here = os.path.abspath(os.getcwd())
        out = os.path.join(here, f"wall_{THEME}_v1.png")
        if not os.path.exists(out):
            src = None
            for d in (here, os.path.dirname(os.path.abspath(__file__))):
                if os.path.exists(os.path.join(d, "bg.jpg")):
                    src = os.path.join(d, "bg.jpg")
                    break
            if not src:
                return None
            from PIL import Image, ImageDraw, ImageFilter
            t = THEMES[THEME]
            g = Image.open(src).convert("L")
            w, h = g.size
            px = g.load()
            lo = sorted(g.resize((64, 64)).getdata())[32]
            mask = g.point(lambda v: max(0, min(255, int((v - lo - 6) * 6))))
            top = [int(c * 255) for c in t["BG_TOP"][:3]]
            bot = [int(c * 255) for c in t["BG_BOT"][:3]]
            base = Image.new("RGB", (1, h))
            for y in range(h):
                f = y / float(h - 1)
                base.putpixel((0, y), tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3)))
            base = base.resize((w, h))
            line = Image.new("RGB", (w, h), tuple(int(c * 255) for c in t["LINE"]))
            glow = mask.filter(ImageFilter.GaussianBlur(3)).point(lambda v: int(v * 0.32))
            img = Image.composite(line, base, glow)
            img = Image.composite(line, img, mask.point(lambda v: int(v * 0.42)))
            if t.get("SPARK"):
                rnd = random.Random(7)
                dr = ImageDraw.Draw(img)
                for _ in range(70):
                    x, y, r = rnd.randrange(w), rnd.randrange(h), rnd.choice((3, 4, 6, 8))
                    col = (215, 245, 255)
                    dr.line((x - r, y, x + r, y), fill=col, width=1)
                    dr.line((x, y - r, x, y + r), fill=col, width=1)
                    dr.point((x, y), fill=(255, 255, 255))
            img.save(out)
        tex = CoreImage(out).texture
    except Exception as e:
        try:
            log(f"wallpaper skipped: {e}")
        except Exception:
            pass
        tex = None
    _WALL_TEX[THEME] = tex
    return tex


def add_gradient_bg(widget, top=BG_TOP, bottom=BG_BOT):
    """Paint the themed doodle wallpaper (or a gradient) plus soft glowing orbs behind a screen."""
    wall = wallpaper_texture()
    with widget.canvas.before:
        Color(1, 1, 1, 1)
        r = Rectangle(texture=wall if wall is not None else gradient_texture(top, bottom))
        Color(BLUE2[0], BLUE2[1], BLUE2[2], 0.10)
        from kivy.graphics import Ellipse
        o1 = Ellipse()
        Color(GOLD[0], GOLD[1], GOLD[2], 0.07)
        o2 = Ellipse()

    def sync(*_):
        r.pos, r.size = widget.pos, widget.size
        d = widget.width * 1.1
        o1.size = (d, d)
        o1.pos = (widget.x - d * 0.45, widget.top - d * 0.55)
        o2.size = (d * 0.9, d * 0.9)
        o2.pos = (widget.right - d * 0.45, widget.y - d * 0.25)
    widget.bind(pos=sync, size=sync)


# Gradient partner for each solid colour, so every button glows like glass
_PAIRS = {GOLD: GOLD2, BLUE: BLUE2, RED: RED2}

# Popups: frosted dark glass with gold titles everywhere
Builder.load_string('''
<Popup>:
    background: ""
    background_color: %s
    title_size: "19sp"
    title_align: "center"
    separator_height: "2dp"
<ModalView>:
    overlay_color: 0.01, 0.01, 0.04, 0.72
''' % ", ".join(str(round(c, 3)) for c in ((BG_TOP[0], BG_TOP[1], BG_TOP[2], 0.97) if THEME in THEMES else (0.07, 0.065, 0.15, 0.97))))

OWNER = "ssalimuto"
ROOT = os.path.abspath(os.getcwd())           # owner's home; guests live in ROOT/users/<name>
ACCOUNTS_FILE = os.path.join(ROOT, "accounts.json")
CURRENT = {"name": OWNER, "owner": True}
OWNER_SALT = "cbdcd2493aa83fd739f4492eec2b2f01"
OWNER_HASH = "fb78aea9063acb75346bf8fbd20adc8db0efc2e9a6048b95c62300b016e7ae99"
STATE_FILE = os.path.join(ROOT, "owner_state.json")
LOG_FILE = "ai_log.txt"
KEY_FILE = os.path.join(ROOT, "gemini_key.txt")
FAST_MODELS = ("gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-flash-latest")
DEEP_MODELS = ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-pro")
MEMORY_FILE = "chat_memory.json"
NOTES_FILE = "notes.txt"
VAULT_FILE = "vault.dat"
MAX_TRIES = 3
LOCKOUT_SECONDS = 300

ALLOWED = MappingProxyType({
    "time": "Tell the time and date",
    "battery": "Check the battery level",
    "vibrate": "Vibrate the phone",
    "notify": "Send a notification",
    "remind": "Reminder, e.g. remind 5 drink water",
    "calc": "Do math, e.g. calc 12*8+5",
    "do": "Genius Agent plans and finishes a whole job, e.g. do compare 3 phones under 800k",
    "run": "Run a skill you taught, e.g. run news (teach skill news: step; step)",
    "skillbook": "See the skills you taught Genius",
    "note": "Save a note, e.g. note buy airtime",
    "notes": "Show your saved notes",
    "weather": "Weather, e.g. weather Kampala",
    "setvoice": "Save your free Sunbird AI token for a real Luganda voice",
    "aboutme": "Teach me about you, e.g. aboutme I want to become a freelancer",
    "wake": "Turn hands-free on/off: just say 'Hey Genius' while the app is open",
    "save": "Lock a secret, e.g. save wifi MyPass123",
    "open": "Show a locked secret, e.g. open wifi",
    "secrets": "List what is in your locker",
    "+": "Tap + to add a picture or file (PDF, text). Then ask about it, or change the picture",
    "setme": "Save your newest selfie as your face, so 'make me ...' pictures look like you. 'keep this face' uses the last picture",
    "edit": "Change your last picture, e.g. edit make it night. Or just say: make me near a building",
    "draw": "Draw a picture, e.g. draw a lion on Mount Elgon. Put your photo as Download/Genius/me.jpg, then 'draw me in a suit' keeps YOUR face",
    "log": "Show the log",
    "key": "Set up a free AI key step by step (also: setup, getkey, apikey, ekisumuluzo)",
    "setkey": "setkey YOURKEY - lets me answer anything",
    "help": "List commands",
    "minerals": "Minerals near me: Government mineral records, mines and quarries near your town (minerals Mityana, minerals steps)",
    "metal": "Metal Finder: finds iron, steel and magnets with the phone sensor (metal guide, metal spots). coil uses a coil detector for all metals",
    "change code": "Create or change your hidden secret code for login",
    "fun": "Fun studio: collage, transform (effects), slideshow (video), fun videos",
    "storage": "Open My storage (200 MB for pictures, files, notes). Also: save this, save note ...",
    "life": "Study coach, money, morning brief and freelancing commands",
    "study": "Study progress and exam countdown",
    "subjects": "Save your subjects, e.g. subjects Maths, Biology",
    "exam": "Set an exam, e.g. exam UCE 2026-11-02",
    "quiz": "Practice question, e.g. quiz biology",
    "explain": "Simple explanation, e.g. explain osmosis",
    "studyplan": "Today's study plan",
    "spent": "Record spending, e.g. spent 2000 airtime",
    "got": "Record money in, e.g. got 50k pocket money",
    "money": "Money summary",
    "goal": "Savings goal, e.g. goal phone 300k",
    "put": "Add to a goal, e.g. put phone 10k",
    "brief": "Morning briefing (brief at 07:00, brief off)",
    "freelance": "Freelancing helper commands",
    "skills": "Save your skills, e.g. skills typing, Canva",
    "cv": "Write your CV",
    "proposal": "Reply to a job, e.g. proposal <job text>",
    "gigs": "Find beginner gigs for your skills",
    "price": "What to charge, e.g. price logo design",
    "build": "Genius writes a program for you, e.g. build a times-table quiz",
    "myapps": "List programs Genius has built",
    "runapp": "Run a program Genius built (asks your approval)",
    "showapp": "Show a program's code",
    "hotspot": "Open Wi-Fi hotspot settings to share your internet",
    "makeai": "Create your own AI, e.g. makeai tutor: biology teacher for UCE",
    "myais": "List AIs you have created",
    "ask": "Ask one of your AIs, e.g. ask tutor what is osmosis",
    "backup": "Save all your Genius data to a backup file",
    "restore": "Bring back data from your latest backup (asks approval)",
    "about": "What Genius is, what it can do, and who made it",
    "licenses": "Open-source licenses Genius uses",
    "version": "Genius version and what's new",
    "setgroq": "setgroq YOURKEY - free, very fast AI from console.groq.com",
    "setrouter": "setrouter YOURKEY - many AIs from openrouter.ai",
    "seteleven": "seteleven YOURKEY - lets Genius sing songs in your cloned voice (key from elevenlabs.io)",
    "setpolli": "setpolli YOURKEY - sharper free pictures (key from enter.pollinations.ai)",
    "turbo": "Turbo on/off: simple questions go to the fastest AI",
    "askall": "Ask every connected AI at once, e.g. askall what is gravity",
    "ais": "Which AIs are connected",
    "mood": "Mood check-in 1-5, e.g. mood 2 stressed about money",
    "moods": "See how you've been feeling",
    "calm": "A guided 1-minute breathing exercise",
    "talk": "Support mode: Genius listens and comforts (talk off to stop)",
    "helpline": "Free help numbers in Uganda",
    "myphone": "Save your own phone number, e.g. myphone 0772123456",
    "trusted": "Trusted people for SOS, e.g. trusted Mum 0772123456",
    "sos": "Open a help message to your trusted people (you press Send)",
    "call": "Open the dialer, e.g. call 116 or call Mum",
    "think": "All AIs answer, then Genius checks them and gives one best answer",
    "mic": "Check why the microphone can't hear you (same as 'mic test')",
    "solve": "Solve a problem step by step, e.g. solve I keep running out of money",
    "problems": "Your problems and their action plans",
    "step": "Tick a step done, e.g. step 1 2 (problem 1, step 2)",
    "know": "Teach Genius facts it uses to solve problems, e.g. know school: fees due 5 Nov",
    "knowledge": "What Genius knows to help you",
    "upgrade": "Install a new Genius version from Download/Genius/update (checked first)",
    "update": "Get the newest Genius straight inside the app, no website needed",
    "rollback": "Go back to the previous Genius version",
    "security": "Security status: firewall, decoy, intruders, tampering",
    "intruders": "See who tried to break in",
    "tripwire": "Add a fake secret that traps hackers, e.g. tripwire momo_pin",
    "deep": "Turn deep thinking + web search on or off",
    "theme": "Change the look: theme gold, theme diamond, or theme classic",
    "news": "World news: Uganda, Africa, world, sports, tech (news brief for a summary)",
    "uneb": "UNEB-style question, e.g. uneb s4 biology, then mark <your answer>",
    "mark": "Mark your answer to the last UNEB question",
    "homework": "Add a photo with + then type homework for step-by-step answers",
    "luganda": "Luganda mode: luganda on / luganda off",
    "translate": "English and Luganda, e.g. translate thank you",
    "define": "Dictionary, e.g. define osmosis (works offline)",
    "fee": "Mobile money charges, e.g. fee mtn send 50000",
    "budget": "Money plan, e.g. budget 200000",
    "scam": "Check a suspicious message, e.g. scam You have won...",
    "farm": "Farming help, e.g. farm maize in Mityana",
    "remember": "Teach Genius about you, e.g. remember I am in S4",
    "memory": "What Genius remembers about you",
    "forget": "Forget something, e.g. forget my class",
    "datasaver": "Data saver on/off: shorter answers",
    "proverb": "A Luganda proverb",
    "stop": "Shut down",
})
HELP_EXTRA = {
    "make song <style> about <idea>": "Make a song with words, e.g. make song amapiano about my mum. Styles: afrobeat, amapiano, kadongo kamu, luganda praise, gospel, dancehall, hip hop, rnb, love ballad, kids, pop, lofi. Add 'in Luganda' or 'English and Luganda'",
    "music / sound": "Music maker menu with every style",
    "play song / lyrics / pause music / stop music": "Play your last song with karaoke words on screen, pause or stop it",
    "studio / banana": "Photo studio: AI edits, change clothes or place, blend photos (banana pro on/off)",
    "transform / looks": "Instant effects and iPhone-style looks that work offline",
    "ultra / zoom photo / ai zoom": "Make a photo sharper, or zoom into it",
    "collage / slideshow": "Put pictures together, or make a looping video",
    "camera": "Camera menu: selfie, back camera or live zoom",
    "selfie": "Open the front camera for a selfie",
    "profile picture": "Change your profile picture: selfie, beauty selfie or a gallery photo",
    "genius eye / glam beauty / portrait blur": "Beauty camera: smooth glowing skin, sharp eyes, better light, offline",
    "new picture / undo picture": "Start a fresh picture, or go back one",
    "quick <question>": "Fastest answer from any connected AI",
    "mind <question>": "Genius Mind: every AI plus web checks for one careful answer",
    "teach skill <name>: step; step": "Teach Genius a job it can repeat with run <name>",
    "better: <fix>": "Correct my last answer so I learn it",
    "apps / open <app>": "List or open your phone's apps (owner only)",
    "wealth / market <coin or currency>": "Money bot, crypto and exchange rates",
    "home": "Home page with big buttons",
    "premium": "Your plan and how to unlock premium",
    "everywhere": "Floating bubble, 'Hey Genius' and home-screen shortcuts",
    "share": "Share Genius with friends",
    "accounts": "Manage guest accounts (owner)",
    "mic test": "Find out why the microphone can't hear you",
}
LIFE_ACTIONS = ("life", "study", "subjects", "exam", "quiz", "explain", "studyplan",
                "spent", "got", "money", "goal", "put", "brief",
                "freelance", "skills", "cv", "proposal", "gigs", "price",
                "build", "myapps", "showapp", "hotspot", "makeai", "myais", "ask", "backup")
NEEDS_APPROVAL = ("vibrate", "notify", "remind", "runapp", "restore")
OWNER_ONLY = ("update", "upgrade", "rollback", "security", "intruders", "tripwire", "restore")
NEW_ACTIONS = ("solve", "problems", "step", "know", "knowledge", "upgrade", "rollback",
               "security", "intruders", "tripwire")
ABOUT_TEXT = """Genius 112.3
Made by Ssali Muto, Uganda.

What I am
An AI agent: Google Gemini's brain plus my own tools. I'm not AGI, and no one has built AGI yet.

What I can do
- Chat and answer questions (fast or deep mode, with web search)
- Remember facts about you (aboutme)
- Notes, reminders, calculator, weather, battery
- Draw pictures, keep a locked secret store
- Study coach: quizzes on your subjects, exam countdown, weak-topic tracking
- Money: spending, pocket money, savings goals in UGX
- Morning brief: weather, exams, money, notes, Uganda news, spoken
- Freelancing: CV, job proposals, real gigs, pricing
- AI maker: create your own specialist AIs and ask them questions
- Backup and restore of your data to your phone's Download folder
- Problem solver: step-by-step plans for real-life problems (solve)
- Builder: writes small Python programs on request and runs them with your approval
- Talk and listen (Speak button, hands-free 'Hey Genius')
- Music maker: songs in 14 styles (Afrobeat, Amapiano, Kadongo Kamu, Luganda praise, Gospel, Dancehall, Hip hop, RnB, ballad, kids...) with real-sounding instruments, words in English or Luganda, and karaoke lyrics while it plays
- Suggests commands as you type; tap one to fill it in

Safety
- Only the owner can log in. Wrong passwords lock it for longer each time (5 min, 15 min, 1 hour).
- Distraction firewall: an intruder is sent to a fake decoy Genius with fake data and slow replies.
- Tripwires and an intruder log tell you when someone tried to break in.
- A tamper check warns you if the code was changed.
- Your API keys stay on this phone. Never share them.
- 'key' opens a step-by-step helper to get a free AI key (Groq, Gemini or OpenRouter). It tests the key before saving and only ever shows its last 4 characters.
- A watcher blocks dangerous actions (copying itself, deleting files, turning off stop).
- 'stop' always shuts me down.

Limits
- I only listen while the app is open and the screen is on.
- I need internet for answers, weather, web search, and Google speech.
- Genius can make mistakes. Check anything important."""

LICENSES_TEXT = """Open-source licenses

Genius is built with free open-source software:
- Python (PSF License)
- Kivy (MIT License)
- Plyer (MIT License)
- Pyjnius (MIT License)
- Android and Chromium parts (Apache License 2.0 / BSD License)
- AndroidX libraries, e.g. legacy v13 and mediarouter (Apache License 2.0)
- Firebase / Google Play services parts (Apache License 2.0)

What this means
- You may use, change, and even sell an app built with them.
- Keep their copyright notices and include this list with your app.
- If you change their code, mark the changed files (Apache 2.0, section 4).
- If a library ships a NOTICE file, include it with your app.
- Don't use their names or logos to promote Genius.
- They come 'as is', with no warranty.

Google Gemini is a paid online service under Google's own terms, not these licenses."""

PLAY_BUILD = False   # True only in the Play Store build: Play delivers updates itself
VERSION_DATE = "2026-10-27"
CHANGELOG = """Genius 112.6 (2026-10-27)
- New: Minerals near me. Say minerals and your town (e.g. minerals Mityana), or tap it in Tools.
- Shows Uganda Government records of mineral areas nearest you (gold, tin, lithium, kaolin and more) with distances, plus mines and quarries mapped within 30 km.
- Honest steps to turn a find into money: lab test at DGSM Entebbe, check licences, get a licence, sell to licensed dealers. Plus scam warnings.

Genius 112.5 (2026-10-27)
- Metal Finder: the graph now keeps moving after the first 10 seconds.
- Phones that don't send magnetic readings are told plainly, with the coil option.

Genius 112.4 (2026-10-27)
- New: Metal Finder. Say metal or tap Metal Finder in Tools.
- Uses the phone's magnetic sensor to find iron, steel and magnets near the top of the phone, with a live gauge, beeps that speed up, a graph, a Peak reading and "stronger / weaker" hints.
- Zero, three sensitivity levels, sound on or off, and Save spot to keep your finds.
- Honest by design: shows real readings and says what the phone can't see (gold, copper, aluminium).
- Coil detector mode: join an ESP32 coil kit's Wi-Fi (Genius-Detector) to find all metals, deeper.
- Phones without a magnetic sensor are told clearly, with the coil option.

Genius 112.3 (2026-10-26)
- Never-fail answers: if one AI fails, Genius moves to the next one by itself, then to a free backup AI that needs no key.
- If the signal drops, Genius waits for it, reconnects and answers your question on its own when the internet is back.
- "explain more" and "explain each part" now explain the last answer.
- New: aicheck tests every AI connection and shows which ones work.

Genius 112.2 (2026-10-26)
- Pro songs with a REAL singing voice and band from ElevenLabs Music. Genius writes the words (Luganda, English or both), ElevenLabs sings and plays them.
- Say: pro song amapiano about my mum. Words light up karaoke style while it plays.
- About 2 minutes long, uses about 1,800 ElevenLabs credits (needs your key: seteleven).
- One download link that always gives the newest Genius, and old shared links now give the newest app too.
- Fixed: UNEB questions, marking and other AI tools said "couldn't reach the AI" even with internet. Groq was refusing Genius's requests; now they go through.

Genius 112.1 (2026-10-26)
- AI sings in YOUR voice: record about a minute of your voice once (say clone my voice), and Genius makes your voice clone at ElevenLabs.
- Then tap 'AI sings it in my voice' in the vocal studio (or say ai sing my song): your clone performs every line on the beat.
- Needs your own ElevenLabs key with voice cloning (Starter plan): type seteleven and your key. Uses your ElevenLabs credits.

Genius 112.0 (2026-10-26)
- Vocal studio: make a song in YOUR voice. Genius makes the beat and words, then you sing over it with the words lighting up.
- A live voice bar shows how loud you sing (green good, gold strong, red too loud), with REC time.
- Record, Stop, Listen, Share and Record again. Your voice is mixed onto the beat with a little room echo and saved with the lyrics.
- Say: song in my voice amapiano about my mum, or record vocals, or tap Sing it in my voice in Music.

Genius 111.9 (2026-10-26)
- New news screen, mostly videos: the latest clips from NTV Uganda, NBS, Al Jazeera, BBC, Sky Sports, ESPN FC, CNBC and CNET, each with its picture.
- Photo stories from Nile Post and BBC with their pictures.
- Videos and stories now play and open INSIDE Genius. Tap Close or Back to return.
- Topic tabs on top: Uganda, World, Sports, Africa, Business, Tech, Entertainment, Health, Trending.
- Say news or news videos to open it.

Genius 111.8 (2026-10-26)
- Checked every command for mistakes.
- "Create for me a picture of a man" no longer puts YOUR face on the man. Your face is used only when you ask for a picture of you.
- Picture requests always go to the picture maker, so an AI can't answer with only words.
- "Make me a photo of a girl" makes a new picture instead of changing the last one.
- Fixed random crashes when slow answers came back.
- "save picture" no longer hidden like a password; clearer help for remember, forget, fee and call.
- Offline, Genius says hi and does sums like what is 25*4.
- "ai status", "menu" and "what can you do" now work.

Genius 111.7 (2026-10-26)
- Pictures of people now look like real Ugandans (dark brown skin, African features) unless you ask for someone else, and like real phone photos taken in everyday places, not glossy stock portraits.
- The free picture maker's logo is cut off the bottom of pictures.
- These picture rules are now built into Genius's brain, so its thinking and answers follow them too.
- Asking Genius Mind for a picture now makes the picture instead of saying "Search failed".
- Genius Mind no longer shows "Search failed" when web search is down; it answers without it.
- Tapping Good or Bad answer again no longer repeats the same message.
- A bad picture rating offers "Make a new picture" or "Tell me what to change".
- Full check of every command: fixed crashes from background jobs touching the screen, "save picture" no longer hidden like a password, clearer help for remember, forget, fee and call, and offline Genius now does sums and says hi.

Genius 111.5 (2026-10-26)
- 3 more free AIs you can connect: Cerebras, Mistral and SambaNova (type key).
- Smart AI picker: Genius learns which AI is fastest and most reliable on your phone, and asks it first.
- Good answer / Bad answer under each reply. Your taps teach Genius which AI to trust.
- Help improve Genius (Menu): opt-in. Once a day it tells the developer which parts had problems, never your chats, name or files, so updates fix real problems faster.

Genius 111.4 (2026-10-26)
- Change profile picture (Menu > Change profile picture, or say 'profile picture'): take a selfie, a beauty selfie, choose from your gallery, use your last picture, or remove it. Genius centres it on your face. Every account has its own picture.

Genius 111.3 (2026-10-26)
- Genius Eye beauty camera (say 'genius eye', or Camera > Genius Eye): finds faces, smooths skin while keeping eyes, lips and hair sharp, evens and brightens skin tone, lifts dark shadows, sharpens details. Then try Glam beauty or Portrait blur. Works offline.

Genius 111.2 (2026-10-26)
- Selfie camera button on the home screen, next to Super zoom camera. You can also add a Genius Selfie button to your phone's home screen (Genius everywhere).

Genius 111.1 (2026-10-26)
- Save and share: every picture now has Save to gallery, Save to files and Share buttons. Or just say 'save', 'save to files' or 'share picture'. Pictures go to your Gallery in a Genius album.

Genius 111.0 (2026-10-26)
- Camera fixed: say 'camera' for Selfie (front camera), Back camera or the live zoom camera. Say 'selfie' to open the front camera straight away.
- 14 new social media effects: HD clear, Warm, Cool, Teal & orange, Cinematic, Fade, Dreamy, Film grain, Glitch, Neon, Cartoon, Duotone pink, Polaroid and Vignette. After you take a photo, tap 'Add effects'.

Genius 110.9 (2026-10-26)
- Fixed news and Trending on social media not loading on phones.
- Trending now also shows what people in Uganda and around the world are searching for, from Google Trends, and it loads faster.

Genius 110.8 (2026-10-26)
- Share now sends a link that downloads Genius straight onto any Android phone. After it's installed, Genius updates itself to the newest version.
- Privacy shield: your chats, memory, notes and keys are locked so only Genius can read them. Sharing sends only the link.
- 'private on' blocks screenshots, screen recorders and on-screen AI from seeing Genius. 'private off' turns it off.

Genius 110.7 (2026-10-26)
- Typing mode: while you type, the top bar hides and Genius's words get smaller, so there's room to see everything you write. Your words are smaller too, and the box stays right above the keyboard. Everything goes back to normal when the keyboard closes.

Genius 110.6 (2026-10-26)
- New + button next to the typing box: take a photo with the camera, pick from your gallery, add your newest screenshot, or add a file like a PDF or notes. Then ask about it, solve homework from it, or change it.

Genius 110.5 (2026-10-26)
- Much faster answers: words start appearing in under a second and type themselves out as Genius thinks.
- Quick questions use the fastest AI, and Genius keeps its line to the AI open so there's no waiting to connect.
- Everyday questions like 'do you know...' no longer take the slow path.

Genius 110.4 (2026-10-26)
- No more empty boxes next to Genius and online.
- 'make it' is no longer changed to 'makeai'.
- Ask something while Genius is still thinking and it does it right after, instead of saying 'still thinking'. It never gets stuck after a bad network.

Genius 110.3 (2026-10-26)
- Keyboard fix: the screen no longer slides when you type. The typing box sits right on top of the keyboard and grows up to 6 lines so you can see all your words.

Genius 110.2 (2026-10-26)
- Trending on social media: the hottest worldwide posts people are sharing (Reddit world, Uganda and Africa) plus viral stories. Say 'news trending' or find it in Search.

Genius 110.1 (2026-10-26)
- Cleaner top bar: only Share and Search. Tap Search to find every tool (news, UNEB, draw, music, money, settings...) or search chats and the internet.

Genius 110.0 (2026-10-26)
- World news: Uganda, Africa, world, sports, business, tech, health. Tap a headline to read it. 'news brief' gives a short AI summary.
- UNEB practice: uneb s4 biology gives a UNEB-style question; mark <your answer> gives a score and model answer.
- Homework from a photo: add the photo with + and type homework for step-by-step solutions.
- Luganda mode (luganda on/off), translate English and Luganda, Luganda proverbs.
- Offline help: answers you got before, dictionary (define), calc and notes work without internet.
- Money: budget 200000 plan and today's mobile money charges (fee mtn send 50000).
- Scam checker: scam <message>.
- Farming help with the weather: farm maize in Mityana.
- Memory: remember I am in S4, memory, forget.
- Data saver: datasaver on for shorter answers.
- News and UNEB buttons in Tools. Type new to see everything.

Genius 109.9 (2026-10-26)
- New Share button on the top bar: one tap to send Genius to WhatsApp, Facebook, TikTok, Instagram, X, Telegram, Messenger, Snapchat, or copy the link.
- Share Genius is also first in Tools.

Genius 109.8 (2026-10-26)
- Fixed: in long chats the words could vanish and the chat turned into a black box. Genius now hides the oldest messages so your chat always stays visible.

Genius 109.7 (2026-10-26)
- Answers like Google's AI Mode: a clear first sentence, then tidy bullet points with bold labels and headings, the websites it searched, and tappable "ask next" questions.

Genius 109.6 (2026-10-26)
- Sharper, more real pictures: Genius now uses Google's newest picture makers (Nano Banana 2.1, Nano Banana 2 and Pro) when your Gemini key has picture access.
- Free pictures look better: realistic photo models, bigger size (up to 832 x 1216), a better camera description, and gentle phone-camera finishing (sharpness, contrast, colour).
- Picture shape follows your words: wide scenes come out landscape, logos and avatars square, people tall.
- New: setpolli YOURKEY. A free key from enter.pollinations.ai unlocks the sharper Z-Image and Flux makers with no logo.
- Typing like a phone keyboard: chips above the box now finish the word you're typing, guess your next word, and fix common typos (teh to the, wether to weather). English and Luganda.
- Genius learns the words you use, only on your phone, so predictions get more personal over time.

Genius 109.5 (2026-10-26)
- See your words as you type: the box wraps and grows up to 4 lines, stays above the keyboard, and is easy to read on every theme.
- Suggestions while you type: matching commands (English and Luganda) appear above the box. Tap one to fill it in.
- Karaoke: when Genius plays a song it made, the words show on screen and the line being played lights up. Pause, Play again and Stop buttons. Say 'lyrics' or 'play song' anytime.
- Better songs: each style now has its own tempo, key, drums, bass line, chords and lead sound - Afrobeat, Amapiano (log drum), Kadongo Kamu (finger-picked guitar), Luganda praise, Gospel (organ), Dancehall, Hip hop (808), RnB, Love ballad, Kids, Pop, Lo-fi, Cinematic and Dance.
- More real sound: plucked guitar, kora and bass strings, warmer piano and organ, real-sounding drums, a human feel, stereo, echo, hall reverb and studio mastering at CD quality (44.1 kHz).
- Real song words: intro, verses, a catchy chorus that repeats, bridge and outro, with rhymes. In English, Luganda, or both. With an AI key the AI writes them; without one Genius uses its own songbook.
- Just say it: "make song amapiano about my mum". Genius tells you which style it picked.
- Colourful chat: names, numbers, commands and links in your theme's colours. Your own words and secrets are never coloured.

Genius 109.4 (2026-10-26)
- New 'Set up AI key' helper: type key (or tap it in your profile or the menu) and Genius walks you through getting a free AI key in 3 easy steps.
- Pick Groq (free, fastest), Google Gemini (free, needed for picture edits) or OpenRouter, open the key page with one tap, then Paste and Test.
- Genius checks the key works before saving it, and tells you plainly if it's wrong, expired or there's no internet.
- When an answer needs a key, Genius now offers a "Set up key" button instead of only text.

Genius 109.3 (2026-10-26)
- Pictures work again: when one free picture maker is busy, Genius tries a second one by itself.
- Pictures, songs and effects save where your phone allows (Download/Genius, or Genius's own storage) and always show in the app.
- Songs mix faster, and if one player can't play a song, Genius uses the phone's own player.
- Faster answers: when the internet is down, Genius stops waiting and tells you at once.
- Clearer messages that say what to do next. 'help' now lists every command, including theme.
- Fixes: 'open wifi' opens your locker again, 'start fresh' works, calc understands 2^10, 12 x 3 and 15% of 40000.
- Weather shows the chance of rain and remembers the last reading for 10 minutes.

Genius 109.0 (2026-10-26)
- Opens with your secret code: create it the first time, then just type it to unlock.
- The three-bar menu at the top right holds Speak, Draw, Locker, Notes, Weather, Deep, Clear, Stop and the rest.
- The top shows only your chat, Search and the menu.
- Quiet updates: Genius fetches new versions by itself in the background and uses them the next time you open it. No downloads, no screens.

Genius 107.0 (2026-10-25)
- Updates itself: type update and Genius downloads and installs the newest version, no website needed.
- Updates on its own: when a new version is out, Genius downloads it by itself and you just tap Update.

Genius 106.0 (2026-10-25)
- Understands misspelled commands, e.g. itruders becomes intruders.

Genius 105.0 (2026-10-25)
- When Google refuses your key, Genius now tells you exactly why and how to fix it.

Genius 104.0 Agent (2026-10-25)
- Genius Agent: "do <job>" plans the job, does each step with live search, checks itself and saves the result.
- Teach a skill once: "teach skill news: step; step", then "run news" forever. "skillbook" lists them.
- Every question now trains the Brain: each answer, from any mode, leaves a lesson for next time.
- Daily self-review: Genius merges and sharpens its own lessons ("improve yourself" runs it now).

Genius 103.0 Brain (2026-10-25)
- Genius learns: after every new question it writes itself a lesson and uses it next time.
- Correct it with "better: ...", teach it with "teach ...", rate with "good" or "bad".
- "what have you learned" shows its lessons; "forget lessons" clears them.

Genius 102.0 Doodle (2026-10-25)
- New look: dark doodle wallpaper of game icons behind every screen
- Picture chat like the best apps: after a picture, say 'make me near a building', 'change it to night'
  or 'blur the background' and Genius edits THAT picture, keeping the same person
- Ideas for changes after every picture; 'undo picture' goes back, 'new picture' starts fresh
- Top right: Find (search chats, notes, creations, internet) and Menu (My creations, My storage, Exit, Lock, Help)
- Genius everywhere (say "everywhere"): floating G bubble over other apps, "Hey Genius" wake word while open, home-screen buttons for Talk, Camera, Music, Ultra
- Music maker (say "sound", or "sound happy afrobeat about ..."): AI producer picks style, key, tempo, chords, melody and instruments, then mixes a full song with reverb and mastering
- Genius Ultra (say "ultra"): HDR, smart white balance, clarity, fine detail, vibrance and noise clean-up; applied automatically to every camera shot and zoom
- Super zoom camera (say "camera"): live 1x-100x zoom with slider and presets, smart sharpening, "ai zoom" rebuilds detail; also zoom any photo
- Pro camera looks (say "looks"): 12 instant iPhone-style looks (Vibrant, Warm, Rich Contrast, HDR, Cinematic, Golden Hour...) + AI flagship look; Replace (sky, background, Portrait mode, Studio Light...)
- Banana studio (say "banana"): Nano Banana / Nano Banana Pro realistic editing, blend 2-4 photos, ultra realistic, fix hands, remove people, restore old photos, picture shape
- Fun studio (Menu or say "fun"): change clothes (12 outfits), change place (14 places), beautiful photo, photo collages, 14 instant effects + AI styles, video slideshows, fun videos
- Accounts: anyone can tap "Create an account" (name, email, hidden password, hidden code; sign in with name or email) and gets their own private Genius. Owner manages them in Menu > Accounts
- Login: password + hidden secret code (4-8 digits). Change it in Menu or say "change code"
- My storage: a private 200 MB space for pictures, files and notes. Say "storage", "save this" or "save note ..."
- + button: add a picture or a file (PDF, text) from your phone, or your newest photo/file.
  Then ask about it ('summarize', 'what is this?') or change the picture ('make me near a building')
- setme: take a selfie, type setme, and your face is saved for 'make me ...' pictures
- Better photos: golden light, blurred background, natural pose, and the newest picture engine

Genius 101.0 Guardian (2026-10-24)
- Drawing fixed: if the free picture engine can't draw, Genius uses a free picture maker instead
- Same face: save your selfie as Download/Genius/me.jpg, then "draw me ..." keeps your real face
- Real photos only: every picture is photo-realistic, never a cartoon. Cartoon words are removed,
  an AI describes the scene like a photographer, and camera detail is added
- Problem solver: solve <problem> gives the causes, options, best choice and a step plan
- problems / step: track your plans and tick steps off as you go
- know: teach Genius facts about your life so its advice fits you
- Self-upgrade: upgrade installs a new version only after checking its fingerprint, and keeps the old one
- rollback: go back to the previous version anytime
- Distraction firewall: after wrong passwords, a hacker lands in a fake decoy Genius
  with fake notes and fake secrets, while your real data stays hidden
- Tarpit: the decoy answers slowly to waste a hacker's time
- Tripwires: fake secrets that raise an alarm when someone opens them
- Stronger lockouts: 5 min, then 15 min, then 1 hour
- Intruder log and alert the next time you log in
- Tamper check: warns if Genius's code was changed by someone else
- security: see everything in one place

Genius 100.0 Personal (2026-10-24)
- Personal AI for your whole life, not only school
- Emotional support: talk mode, mood check-ins and trends, calm breathing
- Safety: spots crisis words and shows free Uganda helplines
- Trusted people and sos: opens a help text to them (you press Send)
- call: opens the dialer for a number or trusted person
- Care mode: notices sadness or stress, answers gently in a softer, slower voice
- Checks on you again 30 minutes later (while Genius is open)
- myphone: your number is added to SOS messages

Genius 100.0 (2026-10-24)
- Many AIs: several smart engines, including a very fast one
- Turbo mode: simple questions go to the fastest AI
- Instant repeat answers (remembers answers to the same question)
- Backup AI: if one fails, another AI answers
- askall: ask every AI at once and compare (fastest first)
- ais: see which AIs are connected
- think: several AIs answer, then Genius cross-checks them into one best answer
- Study, freelance and builder tools work with any connected AI, not only one

Genius 2.0, renamed from My AI
- Study coach: subjects, exam countdown, quizzes, weak topics, study plan
- Money tracker in UGX: spending, income, savings goals
- Morning brief: weather, exams, money, notes, Uganda news, spoken
- Freelancing: skills, CV, proposals, real gigs, pricing
- Builder: writes and runs small Python programs (with your approval)
- AI maker: create your own specialist AIs (makeai, ask, myais)
- Backup and restore to Download/Genius
- Microphone: uses Google's voice box when Android blocks the mic
- Licenses updated: AndroidX and Firebase (Apache 2.0)

Genius 1.x - My AI
- Smart chat (fast and deep), tools, memory, notes, reminders
- Weather, battery, notifications, drawing, locker, Luganda voice, wake mode"""

FORBIDDEN = ("copy_self", "disable_stop", "edit_rules", "delete_files", "open_network")


# ---------------- safety core ----------------
def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()


def this_device():
    return hashlib.sha256(socket.gethostname().encode()).hexdigest()


def log(event):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} | {event}\n")


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    state = {"device": this_device(), "fails": 0, "locked_until": 0}
    json.dump(state, open(STATE_FILE, "w"))
    return state


LOCKOUT_STEPS = (300, 900, 3600)      # 5 min, 15 min, 1 hour
INTRUDER_FILE = os.path.join(ROOT, "intruders.json")


def intruder_log(event, detail=""):
    try:
        data = json.load(open(INTRUDER_FILE))
    except Exception:
        data = {"events": [], "seen": 0}
    data["events"].append({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "e": event, "d": detail[:120]})
    data["events"] = data["events"][-300:]
    json.dump(data, open(INTRUDER_FILE, "w"))
    log(f"INTRUDER: {event} {detail[:60]}")


def intruder_data():
    try:
        return json.load(open(INTRUDER_FILE))
    except Exception:
        return {"events": [], "seen": 0}


# ---------------- accounts: other people get their own private Genius ----------------
_RULE_NAMES = ("FAST_RULES", "DEEP_RULES", "AGENT_RULES")
_RULE_ORIG = {}


def accounts_load():
    try:
        return json.load(open(ACCOUNTS_FILE))
    except Exception:
        return {}


def accounts_save(a):
    json.dump(a, open(ACCOUNTS_FILE, "w"))


def valid_username(n):
    return bool(re.fullmatch(r"[a-z0-9_]{3,20}", n))


def create_account(name, pw, code, email=""):
    name = name.strip().lower()
    email = email.strip().lower()
    if not valid_username(name):
        return "Name must be 3-20 letters, numbers or _ (no spaces)."
    a = accounts_load()
    if name == OWNER or name in a:
        return "That name is taken. Choose another."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", email):
        return "Enter a real email address, like name@gmail.com."
    if any(v.get("email") == email for v in a.values()):
        return "That email already has an account."
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    if not code.isdigit() or not (4 <= len(code) <= 8):
        return "Secret code must be 4 to 8 digits."
    if len(set(code)) == 1 or code in "0123456789" or code in "9876543210":
        return "Secret code is too easy to guess."
    ps, cs = os.urandom(16), os.urandom(16)
    a[name] = {"pw_salt": ps.hex(), "pw_hash": hash_pw(pw, ps), "code_salt": cs.hex(),
               "code_hash": hash_pw(code, cs), "email": email, "created": time.strftime("%Y-%m-%d %H:%M")}
    accounts_save(a)
    log(f"ACCOUNT CREATED: {name}")
    return ""


# ---------------- Genius Premium: free trial, then 2,000 UGX ----------------
TRIAL_DAYS = 7
TRIAL_USES = 50
TRIAL_MB = 0                            # 0 = no download limit during the free trial


def _user_mb():
    """MB of pictures, songs, videos and files this person has saved in Genius."""
    total = 0
    try:
        for folder, _, fs in os.walk(genius_dl()):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(folder, f))
                except OSError:
                    pass
    except Exception:
        pass
    return total / (1024 * 1024)
PREMIUM_PRICE = "2,000 UGX"
PREMIUM_DAYS = 7                        # one payment = 1 week
PAY_NUMBER = ""                         # Mobile Money number people pay to (set by the owner)
PAY_NAME = "Ssali Muto"
_PREMIUM_SALT = b"genius-premium-v1-ssalimuto-7f3a9c"
_TRIAL_MARK = "/storage/emulated/0/Download/Genius/.gp" if os.path.isdir("/storage/emulated/0") else None


def _trial_mark_get(email):
    """A hidden copy outside the app, so reinstalling doesn't restart the free trial."""
    try:
        return json.load(open(_TRIAL_MARK)).get(hashlib.sha256(email.encode()).hexdigest()[:16])
    except Exception:
        return None


def _trial_mark_set(email, start):
    if not _TRIAL_MARK:
        return
    try:
        d = json.load(open(_TRIAL_MARK)) if os.path.exists(_TRIAL_MARK) else {}
        d.setdefault(hashlib.sha256(email.encode()).hexdigest()[:16], start)
        os.makedirs(os.path.dirname(_TRIAL_MARK), exist_ok=True)
        json.dump(d, open(_TRIAL_MARK, "w"))
    except Exception:
        pass


def premium_code(email, months=1, yymm=None):
    """Unlock code the owner gives after payment: W<weeks>-<YYMM>-<6 signed characters>."""
    yymm = yymm or time.strftime("%y%m")
    sig = hmac.new(_PREMIUM_SALT, f"{email.strip().lower()}|{months}|{yymm}".encode(), hashlib.sha256).hexdigest()[:6].upper()
    return f"W{months}-{yymm}-{sig}"


def premium_status():
    """Returns (allowed, message) for the signed-in person. The owner is always free."""
    if CURRENT["owner"]:
        return True, "You're the owner, so Genius is free for you."
    a = accounts_load()
    acc = a.get(CURRENT["name"])
    if not acc:
        return True, ""
    now = time.time()
    if acc.get("premium_until", 0) > now:
        days = int((acc["premium_until"] - now) // 86400) + 1
        return True, f"Genius Premium is active for {days} more day{'s' if days != 1 else ''}."
    email = acc.get("email", CURRENT["name"])
    start = acc.get("trial_start") or _trial_mark_get(email) or now
    if not acc.get("trial_start"):
        acc["trial_start"] = start
        accounts_save(a)
    _trial_mark_set(email, start)
    days_left = TRIAL_DAYS - int((now - start) // 86400)
    uses_left = TRIAL_USES - acc.get("uses", 0)
    mb_left = (TRIAL_MB - _user_mb()) if TRIAL_MB else 1
    if days_left > 0 and uses_left > 0 and mb_left > 0:
        mb_txt = f" and {mb_left:.0f} MB of downloads" if TRIAL_MB else ", with unlimited downloads,"
        return True, (f"Free trial: {days_left} day{'s' if days_left != 1 else ''}, {uses_left} "
                      f"use{'s' if uses_left != 1 else ''}{mb_txt} left.")
    if mb_left <= 0 and days_left > 0 and uses_left > 0:
        return False, f"You've used your {TRIAL_MB} MB of free downloads."
    return False, "Your free trial has ended."


def premium_count_use():
    if CURRENT["owner"]:
        return
    a = accounts_load()
    if CURRENT["name"] in a and a[CURRENT["name"]].get("premium_until", 0) <= time.time():
        a[CURRENT["name"]]["uses"] = a[CURRENT["name"]].get("uses", 0) + 1
        accounts_save(a)


def premium_redeem(code):
    code = code.strip().upper().replace(" ", "")
    m = re.fullmatch(r"W(\d{1,2})-(\d{4})-([0-9A-F]{6})", code)
    a = accounts_load()
    acc = a.get(CURRENT["name"])
    if not m or not acc:
        return "That code doesn't look right. It looks like W1-2610-AB12CD."
    months, yymm = int(m.group(1)), m.group(2)
    this = time.strftime("%y%m")
    prev = time.strftime("%y%m", time.localtime(time.time() - 32 * 86400))
    if yymm not in (this, prev):
        return "That code has expired. Ask the owner for a new one."
    if not hmac.compare_digest(premium_code(acc.get("email", ""), months, yymm), code):
        intruder_log("wrong premium code", CURRENT["name"])
        return "That code isn't for this account. Check your email with the owner."
    used = acc.setdefault("used_codes", [])
    if code in used:
        return "That code was already used."
    used.append(code)
    base = max(time.time(), acc.get("premium_until", 0))
    acc["premium_until"] = base + PREMIUM_DAYS * months * 86400
    accounts_save(a)
    log(f"PREMIUM: {CURRENT['name']} unlocked {months} week(s)")
    return ""


def name_for(login):
    """Sign in with your name or your email."""
    login = login.strip().lower()
    if "@" in login:
        for n, v in accounts_load().items():
            if v.get("email") == login:
                return n
    return login


def account_ok(name, pw, code):
    acc = accounts_load().get(name.strip().lower())
    if not acc:
        hash_pw(pw or "x", b"0" * 16)        # same time cost, so a hacker can't tell if the name exists
        return False
    a = hmac.compare_digest(hash_pw(pw.strip(), bytes.fromhex(acc["pw_salt"])), acc["pw_hash"])
    b = hmac.compare_digest(hash_pw(code.strip(), bytes.fromhex(acc["code_salt"])), acc["code_hash"])
    return a and b


def delete_account(name):
    import shutil
    a = accounts_load()
    if name not in a:
        return False
    del a[name]
    accounts_save(a)
    shutil.rmtree(os.path.join(ROOT, "users", name), ignore_errors=True)
    log(f"ACCOUNT DELETED: {name}")
    return True


def switch_user(name):
    """Move Genius into this person's own private space: own chats, notes, money, memory."""
    owner = name == OWNER
    CURRENT.update(name=name, owner=owner)
    home = ROOT if owner else os.path.join(ROOT, "users", name)
    os.makedirs(home, exist_ok=True)
    os.chdir(home)
    g = globals()
    for k in _RULE_NAMES:
        if k in g:
            _RULE_ORIG.setdefault(k, g[k])
            g[k] = _RULE_ORIG[k] if owner else _RULE_ORIG[k].replace("ssalimuto", name)
    history.clear()
    history.extend(load_memory())
    try:
        LAST_IMAGE.update(path=None, time=0, prompt="")
        IMAGE_STACK.clear()
    except Exception:
        pass


def pin_is_set():
    d = load_state()
    return bool(d.get("pin_hash"))


def set_pin(code):
    d = load_state()
    salt = os.urandom(16)
    d["pin_salt"] = salt.hex()
    d["pin_hash"] = hash_pw(code.strip(), salt)
    json.dump(d, open(STATE_FILE, "w"))
    log("SECRET CODE SET")


def pin_ok(code):
    d = load_state()
    if not d.get("pin_hash"):
        return True
    return hmac.compare_digest(hash_pw(code.strip(), bytes.fromhex(d["pin_salt"])), d["pin_hash"])


def check_login(name, pw, code=""):
    """FIREWALL: name + password + same device. Wrong tries escalate the lock,
    and an attacker is quietly sent into the decoy (returns ok=False, msg='DECOY')."""
    data = load_state()
    data.setdefault("strikes", 0)
    who = name.strip() or "(blank)"
    if time.time() < data["locked_until"]:
        intruder_log("login while locked -> decoy", f"name={who}")
        return False, "DECOY"
    if data["device"] != this_device():
        intruder_log("other device -> decoy", f"name={who}")
        return False, "DECOY"
    uname = name_for(name)
    if uname == OWNER:
        ok = hmac.compare_digest(hash_pw(pw.strip(), bytes.fromhex(OWNER_SALT)), OWNER_HASH)
        ok = pin_ok(code) and ok          # wrong code looks exactly like a wrong password
    else:
        ok = account_ok(uname, pw, code)
    log(f"LOGIN {'OK' if ok else 'FAILED'}: name={who}")
    if ok:
        data["fails"] = 0
        data["strikes"] = 0
        msg = f"Welcome {uname}."
        switch_user(uname)
    else:
        data["fails"] += 1
        intruder_log("wrong password", f"name={who}")
        if data["fails"] >= MAX_TRIES:
            wait = LOCKOUT_STEPS[min(data["strikes"], len(LOCKOUT_STEPS) - 1)]
            data["strikes"] += 1
            data["locked_until"] = time.time() + wait
            data["fails"] = 0
            msg = "DECOY"
        else:
            msg = f"Access denied. {MAX_TRIES - data['fails']} tries left."
    json.dump(data, open(STATE_FILE, "w"))
    return ok, msg


# ---------------- phone features (plyer) ----------------
def safe(func):
    try:
        return func()
    except BaseException:
        return None


# ---- voice: a man's voice using Android's own speech engine ----
VOICE_PITCH = 0.85   # deep but still clear (1.0 is normal)
VOICE_SPEED = 0.85   # a little slower, easy for anyone to follow
_android_tts = {"engine": None, "ready": False}


def _pick_male_voice(engine):
    """Choose an installed English male voice if the phone has one."""
    try:
        voices = engine.getVoices()
        if voices is None:
            return
        it = voices.iterator()
        best = None
        while it.hasNext():
            v = it.next()
            name = v.getName().lower()
            if not name.startswith("en"):
                continue
            if v.isNetworkConnectionRequired():
                continue
            # Google male voices usually have these codes in the name
            if "male" in name and "female" not in name:
                best = v
                break
            if any(code in name for code in ("-iom-", "-iol-", "-tpd-", "-rjs-", "-gbd-", "-gbg-")):
                best = best or v
        if best is not None:
            engine.setVoice(best)
    except Exception:
        pass


def _start_android_tts():
    from jnius import autoclass, PythonJavaClass, java_method
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    TextToSpeech = autoclass("android.speech.tts.TextToSpeech")

    class _Init(PythonJavaClass):
        __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
        __javacontext__ = "app"

        @java_method("(I)V")
        def onInit(self, status):
            eng = _android_tts["engine"]
            if status == 0 and eng is not None:
                eng.setPitch(VOICE_PITCH)
                eng.setSpeechRate(VOICE_SPEED)
                _pick_male_voice(eng)
                _android_tts["ready"] = True

    _android_tts["listener"] = _Init()   # keep a reference alive
    _android_tts["engine"] = TextToSpeech(PythonActivity.mActivity, _android_tts["listener"])
    return True


# ---- real Luganda voice from Sunbird AI (Ugandan, native speakers) ----
SUNBIRD_KEY_FILE = os.path.join(ROOT, "sunbird_key.txt")
SUNBIRD_URL = "https://api.sunbird.ai/tasks/audio/speech"
SUNBIRD_VOICES = "https://api.sunbird.ai/tasks/voice/speakers?language=lug"
_luganda = {"voice": None, "sound": None, "lock": threading.Lock(), "n": 0}


def _sunbird_token():
    try:
        return open(SUNBIRD_KEY_FILE).read().strip() or None
    except Exception:
        return None


def _find_male_luganda(data):
    """Walk the speaker list and return the first male Luganda voice name/tag."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            g = str(x.get("gender", "")).lower()
            if g in ("male", "m", "man"):
                v = x.get("name") or x.get("voice") or x.get("id") or x.get("speaker_id")
                if v:
                    found.append(str(v))
            for y in x.values():
                walk(y)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(data)
    return found[0] if found else None


def _luganda_voice(token):
    if _luganda["voice"]:
        return _luganda["voice"]
    try:
        req = urllib.request.Request(SUNBIRD_VOICES, headers={"Authorization": "Bearer " + token})
        data = json.load(urllib.request.urlopen(req, timeout=30, context=ssl_context()))
        _luganda["voice"] = _find_male_luganda(data)
    except Exception:
        pass
    return _luganda["voice"]


def _play_file(path):
    """Play a sound file. Kivy first; if Kivy can't open it, Android's own MediaPlayer. Returns True if playing."""
    if _luganda["sound"] is not None:
        try:
            _luganda["sound"].stop()
        except Exception:
            pass
        _luganda["sound"] = None
    if not path or not os.path.exists(path):
        return False
    try:
        from kivy.core.audio import SoundLoader
        snd = SoundLoader.load(path)
        if snd:
            _luganda["sound"] = snd
            _luganda["file"], _luganda["paused_at"] = path, 0.0
            snd.play()
            return True
    except Exception as e:
        log(f"PLAY kivy failed: {e}")
    try:
        from jnius import autoclass
        mp = autoclass("android.media.MediaPlayer")()
        mp.setDataSource(path)
        mp.prepare()
        mp.start()
        _luganda["sound"] = mp
        _luganda["file"], _luganda["paused_at"] = path, 0.0
        return True
    except Exception as e:
        log(f"PLAY android failed: {e}")
    return False


def luganda_speak(text):
    """Speak with a native Luganda male voice. Returns False if not set up."""
    token = _sunbird_token()
    if not token:
        return False

    def work():
        with _luganda["lock"]:
            body = {"text": text[:600], "language": "lug", "response_mode": "stream"}
            voice = _luganda_voice(token)
            if voice:
                body["voice"] = voice
            try:
                req = urllib.request.Request(
                    SUNBIRD_URL, data=json.dumps(body).encode(),
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "application/json"})
                audio = urllib.request.urlopen(req, timeout=120, context=ssl_context()).read()
                if audio[:1] == b"{":           # got JSON with a link instead of sound
                    url = json.loads(audio).get("audio_url")
                    audio = urllib.request.urlopen(url, timeout=60, context=ssl_context()).read()
                _luganda["n"] = (_luganda["n"] + 1) % 5
                path = f"voice_{_luganda['n']}.wav"
                with open(path, "wb") as f:
                    f.write(audio)
                Clock.schedule_once(lambda *_: safe(lambda: _play_file(path) or True), 0)
            except Exception as e:
                log(f"LUGANDA VOICE failed: {e}")
                Clock.schedule_once(lambda *_: _device_tts(text), 0)
    threading.Thread(target=work, daemon=True).start()
    return True


USE_LUGANDA_VOICE = False   # set True to use the Sunbird Luganda voice again


def tts(text):
    if USE_LUGANDA_VOICE and luganda_speak(text):
        return
    _device_tts(text)


def _device_tts(text):
    eng = _android_tts["engine"]
    if eng is None and safe(_start_android_tts):
        eng = _android_tts["engine"]
    if eng is not None and _android_tts["ready"]:
        def _say():
            eng.speak(text, 0, None, "myai")
            return True
        if safe(_say):
            return
    # fallback while the engine warms up, or off-Android
    def _s():
        from plyer import tts as t
        t.speak(text)
        return True
    safe(_s)


def battery_text():
    def _b():
        from plyer import battery
        return dict(battery.status)
    st = safe(_b) or {}
    if st.get("percentage") is None:
        return "I could not read the battery."
    charging = "and charging" if st.get("isCharging") else "not charging"
    return f"Battery is at {st['percentage']:.0f} percent, {charging}."


def vibrate():
    def _v():
        from plyer import vibrator
        vibrator.vibrate(1)
        return True
    return "Vibrating." if safe(_v) else "Vibration is not available."


def notify(title, msg):
    def _n():
        from plyer import notification
        notification.notify(title=title, message=msg)
        return True
    return bool(safe(_n))


# ---------------- chat ----------------
OFFLINE = [
    (("hello", "hi", "hey", "oli otya"), ["Hello ssalimuto! How are you?", "Hi boss, I'm listening."]),
    (("how are you",), ["I'm running well and ready to help you."]),
    (("your name", "who are you"), ["I'm your private AI. I only obey ssalimuto."]),
    (("who made you", "who created you"), ["You did, ssalimuto, with a little help."]),
    (("thank", "webale"), ["You're welcome!", "Anytime, boss."]),
    (("bye", "goodbye"), ["Goodbye! Press Stop when you want me to shut down."]),
    (("joke",), ["Why did the robot go to school? To improve its byte!",
                 "I told my computer a joke about UDP. I'm not sure it got it."]),
    (("what can you do", "help me"), ["Tap Help to see my commands, or just talk to me."]),
]
def load_memory():
    try:
        return json.load(open(MEMORY_FILE))[-40:]
    except Exception:
        return []


def save_memory():
    json.dump(history[-40:], open(MEMORY_FILE, "w"))


history = load_memory()


def offline_reply(text):
    if len(text.split()) > 4:
        return None
    t = " " + "".join(c if c.isalnum() else " " for c in text.lower()) + " "
    for keys, answers in OFFLINE:
        if any(f" {k}" in t for k in keys):
            return random.choice(answers)
    return None


def key_reason(code, detail=""):
    """Plain words for why Google refused the key, with Google's own reason."""
    msg, why = "", ""
    try:
        err = json.loads(detail).get("error", {})
        msg = (err.get("message") or "").strip()
        for d in err.get("details") or []:
            why = why or d.get("reason", "")
    except Exception:
        pass
    k = (why + " " + msg).upper()
    if "API_KEY_INVALID" in k or "NOT VALID" in k:
        tip = "This key is wrong or was deleted. Make a new one at aistudio.google.com/apikey"
    elif "EXPIRED" in k:
        tip = "This key has expired. Make a new one at aistudio.google.com/apikey"
    elif "SERVICE_DISABLED" in k or "HAS NOT BEEN USED" in k or "DISABLED" in k:
        tip = "The Gemini service is switched off for this key's project. Make a key in a new project at aistudio.google.com/apikey"
    elif "LOCATION" in k or "REGION" in k or "COUNTRY" in k:
        tip = "Google doesn't allow this key from your location"
    elif "BLOCKED" in k or "RESTRICT" in k or "REFERER" in k or "ANDROID" in k:
        tip = "This key has limits that block the app. Remove the key's restrictions, or make a new key"
    elif "PERMISSION" in k or code == 403:
        tip = "This key isn't allowed to use Gemini. Make a new one at aistudio.google.com/apikey"
    else:
        tip = "Google refused the key"
    out = "Google rejected the key. " + tip + ", then type setkey and paste only the key."
    if msg:
        out += "\nGoogle says: " + msg[:220]
    return out


RELEASES_URL = "https://api.github.com/repos/ssalimuto/Genius-app/releases?per_page=15"
UPDATE_CHECK_FILE = os.path.join(ROOT, "update_check.json")


def _ver_tuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def online_update():
    """Newest Genius on the release page: (version, apk_url) or (None, reason)."""
    try:
        req = urllib.request.Request(RELEASES_URL, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "Genius-app"})
        try:
            r = urllib.request.urlopen(req, timeout=20, context=ssl_context())
        except urllib.error.URLError as e:
            if "CERTIFICATE" not in str(e).upper():
                raise
            r = urllib.request.urlopen(req, timeout=20, context=ssl._create_unverified_context())
        with r:
            rels = json.load(r)
    except Exception:
        return None, "I couldn't reach the update page. Check your internet and try again."
    best = None
    for rel in rels:
        if rel.get("draft"):
            continue
        for a in rel.get("assets") or []:
            m = re.match(r"genius2-(\d+(?:\.\d+)*)-.*\.apk$", a.get("name", ""))
            if m and (best is None or _ver_tuple(m.group(1)) > _ver_tuple(best[0])):
                best = (m.group(1), a.get("browser_download_url"))
    if not best:
        return None, "No Genius download is on the release page yet."
    if _ver_tuple(best[0]) <= _ver_tuple(SHIP_VERSION):
        return None, f"You already have the newest Genius ({VERSION})."
    return best, None


def fetch_live_update():
    """Quietly fetch newer Genius code from the release page and keep it ready for the
    next start. No screens, no messages. Returns 'ready', 'apk' (needs a new app), or ''."""
    if PLAY_BUILD:
        return ""
    try:
        req = urllib.request.Request(RELEASES_URL, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "Genius-app"})
        with urllib.request.urlopen(req, timeout=20, context=ssl_context()) as r:
            rels = json.load(r)
        best = None
        for rel in rels:
            if rel.get("draft"):
                continue
            names = {a.get("name"): a.get("browser_download_url") for a in rel.get("assets") or []}
            if "genius_live.py" in names and "genius_live.sha256" in names:
                best = names
                break
        if not best:
            return ""
        def get(u):
            rq = urllib.request.Request(u, headers={"User-Agent": "Genius-app"})
            with urllib.request.urlopen(rq, timeout=60, context=ssl_context()) as r:
                return r.read()
        want = get(best["genius_live.sha256"]).decode().split()[0].strip().lower()
        src = get(best["genius_live.py"])
        if hashlib.sha256(src).hexdigest() != want:
            intruder_log("quiet update rejected: fingerprint mismatch")
            return ""
        text = src.decode("utf-8")
        compile(text, "genius_live.py", "exec")
        if "class GeniusApp" not in text or "def check_login" not in text:
            return ""
        v = re.search(r'^VERSION\s*=\s*"([^"]+)"', text, re.M)
        need = re.search(r'^NEEDS_APK\s*=\s*"([^"]+)"', text, re.M)
        v = v.group(1) if v else "0"
        need = need.group(1) if need else v
        if _vt(v) <= _vt(VERSION):
            return ""
        if _vt(need) > _vt(SHIP_VERSION):
            return "apk"                     # new parts inside the app itself: a real install is needed
        os.makedirs(LIVE_DIR, exist_ok=True)
        tmp = LIVE_CODE + ".part"
        open(tmp, "wb").write(src)
        os.replace(tmp, LIVE_CODE)
        json.dump({"version": v, "needs_apk": need, "sha": want, "tries": 0, "ok": False},
                  open(LIVE_INFO, "w"))
        log(f"QUIET UPDATE ready: {v}")
        return "ready"
    except Exception as e:
        log(f"quiet update skipped: {e}")
        return ""


def install_online_update(ver, url, tell):
    """Download the new APK inside the app, then open Android's Update screen."""
    try:
        from jnius import autoclass, cast
    except Exception:
        tell("Updating inside the app only works on the phone.")
        return
    try:
        Context = autoclass("android.content.Context")
        DM = autoclass("android.app.DownloadManager")
        DMRequest = autoclass("android.app.DownloadManager$Request")
        DMQuery = autoclass("android.app.DownloadManager$Query")
        Env = autoclass("android.os.Environment")
        Uri = autoclass("android.net.Uri")
        Intent = autoclass("android.content.Intent")
        Build = autoclass("android.os.Build$VERSION")
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        if Build.SDK_INT >= 26 and not act.getPackageManager().canRequestPackageInstalls():
            Settings = autoclass("android.provider.Settings")
            i = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                       Uri.parse("package:" + act.getPackageName()))
            act.startActivity(i)
            tell("First allow Genius to install updates: switch on 'Allow from this source', "
                 "come back, and type update again. You only do this once.")
            return
        dm = cast("android.app.DownloadManager", act.getSystemService(Context.DOWNLOAD_SERVICE))
        name = f"Genius-{ver}.apk"
        old = os.path.join(Env.getExternalStoragePublicDirectory(Env.DIRECTORY_DOWNLOADS).getAbsolutePath(), name)
        try:
            if os.path.exists(old):
                os.remove(old)
        except Exception:
            pass
        req = DMRequest(Uri.parse(url))
        req.setTitle(f"Genius {ver}")
        req.setDescription("Downloading the new Genius")
        req.setMimeType("application/vnd.android.package-archive")
        req.setNotificationVisibility(1)
        req.setDestinationInExternalPublicDir(Env.DIRECTORY_DOWNLOADS, name)
        did = dm.enqueue(req)
        tell(f"Downloading Genius {ver} now. Keep the app open, about a minute on good signal.")
        for _ in range(600):                 # up to 20 minutes
            time.sleep(2)
            q = DMQuery()
            q.setFilterById([did])
            c = dm.query(q)
            status = 0
            if c is not None and c.moveToFirst():
                status = c.getInt(c.getColumnIndex("status"))
            if c is not None:
                c.close()
            if status == 8:                  # successful
                break
            if status == 16:                 # failed
                tell("The download failed. Check your internet and type update again.")
                return
        else:
            tell("The download is taking too long. Type update again on better signal.")
            return
        uri = dm.getUriForDownloadedFile(did)
        i = Intent(Intent.ACTION_VIEW)
        i.setDataAndType(uri, "application/vnd.android.package-archive")
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK)
        act.startActivity(i)
        tell(f"Downloaded. Tap Update on the screen that opens to get Genius {ver}. "
             "Your notes, lessons and storage stay.")
    except Exception as e:
        log(f"update error: {e}")
        tell("Something went wrong while updating. Type update to try again.")


def update_due():
    """True once a day, for the quiet background check."""
    try:
        last = json.load(open(UPDATE_CHECK_FILE)).get("t", 0)
    except Exception:
        last = 0
    if time.time() - last < 50 * 60:
        return False
    try:
        json.dump({"t": time.time()}, open(UPDATE_CHECK_FILE, "w"))
    except Exception:
        pass
    return True


def clean_key(text):
    """Pull the real key out of whatever was pasted (even a whole curl command)."""
    m = re.search(r"(AQ\.[A-Za-z0-9_\-]+|AIza[A-Za-z0-9_\-]{20,})", text)
    return m.group(1) if m else text.strip().strip("'\"")


_SSL = []


def ssl_context():
    """One shared TLS context (building it reads the certificate file, so do it once)."""
    if not _SSL:
        try:
            import certifi
            _SSL.append(ssl.create_default_context(cafile=certifi.where()))
        except Exception:
            _SSL.append(ssl.create_default_context())
    return _SSL[0]


def _is_net_error(e):
    """True for 'no internet / timed out' problems (not a server's answer): trying another model won't help."""
    return (not isinstance(e, urllib.error.HTTPError)) and isinstance(
        e, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError))


LUGANDA = ("Always reply in clear, simple English. ")
_OLD_LUGANDA = ("Always reply in Luganda (Oluganda), the language of Buganda, using simple, natural, "
           "correct Luganda. Only use an English word when there is no common Luganda word for it. ")
FAST_RULES = (LUGANDA + "You are the private AI of your owner ssalimuto, a young person in Uganda. "
              "Answer clearly in 1 to 3 short sentences. You only talk; never claim to control devices.")
DEEP_RULES = (LUGANDA + "You are the private AI of your owner ssalimuto, a young person in Uganda. "
              "Think carefully step by step before answering. Check facts with Google Search when "
              "the question is about news, prices, people or anything recent. Give the best, most "
              "accurate answer you can: start with the direct answer, then explain simply with short "
              "points or steps. Say honestly when you are not sure. Never claim to control devices.")


IMAGE_MODELS = ("gemini-nano-banana-2.1", "gemini-3.1-flash-image", "gemini-2.5-flash-image",
                "gemini-3-pro-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image-preview",
                "gemini-2.5-flash-image-preview")
PRO_IMAGE_MODELS = ("gemini-3-pro-image", "gemini-3-pro-image-preview")
# Nano Banana = gemini-2.5-flash-image, Nano Banana Pro = gemini-3-pro-image-preview (sharper, more realistic)
BANANA = {"pro": False, "aspect": ""}


def image_models():
    if BANANA["pro"]:
        return PRO_IMAGE_MODELS + tuple(m for m in IMAGE_MODELS if m not in PRO_IMAGE_MODELS)
    return IMAGE_MODELS


HORDE_URL = "https://aihorde.net/api/v2"      # free community picture maker, works with the anonymous key
POLLI_URL = "https://image.pollinations.ai/prompt/"
FREE_DRAW_FAIL = ("The free picture makers are very busy right now. Wait a minute and say it again, "
                  "or add a Gemini key with billing (setkey) for faster, sharper pictures.")


def _short_prompt(prompt, limit=440):
    """Free makers want a short prompt: keep the description, drop the long camera wording."""
    p = (prompt or "").replace(PHOTO_STYLE, "").strip(" .,")
    p = ugandan_people(p, prompt)
    p = re.sub(r"\s+", " ", p)[:limit].strip(" .,") or "a real photograph"
    return p + (", real casual photo taken on an Android phone, everyday snapshot, natural light, "
                "true-to-life skin texture, everything in focus, ordinary background, no bokeh, unedited")


def _retry_after(body, default=0):
    m = re.search(r"[Rr]etry after (\d+)\s*s", body or "")
    return int(m.group(1)) if m else default


def save_picture(data, prefix="drawing"):
    """Save picture bytes as a JPG/PNG Kivy can always show (WebP/odd formats are converted).
    Goes to Download/Genius/pictures when the phone allows it, else Genius's own folder."""
    ext = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    if not (data[:3] == b"\xff\xd8\xff" or ext == ".png"):
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(data)).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=93)
            data, ext = buf.getvalue(), ".jpg"
        except Exception as e:
            log(f"PICTURE convert failed: {e}")
    name = f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{random.randint(100, 999)}{ext}"
    for d in (genius_dl("pictures"), private_dir("pictures")):
        try:
            out = os.path.join(d, name)
            with open(out, "wb") as f:
                f.write(data)
            return os.path.abspath(out)
        except Exception as e:
            log(f"PICTURE save failed in {d}: {e}")
    out = os.path.abspath(name)
    with open(out, "wb") as f:
        f.write(data)
    return out


def _fetch(url, timeout=45, data=None, headers=None, method=None):
    """GET/POST with a timeout; retries once without certificate checks on old phones. Returns (code, ctype, bytes)."""
    h = {"User-Agent": "Genius/" + VERSION}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
    except urllib.error.URLError as e:
        if isinstance(e, urllib.error.HTTPError) or "CERTIFICATE" not in str(e).upper():
            raise
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
    with r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


POLLI_KEY_FILE = os.path.join(ROOT, "pollinations_key.txt")
POLLI_GEN = "https://gen.pollinations.ai/image/"
NEG_PROMPT = ("cartoon, anime, drawing, painting, illustration, 3d render, cgi, plastic skin, waxy skin, "
              "airbrushed, oversaturated, deformed hands, extra fingers, missing fingers, bad anatomy, "
              "distorted face, asymmetrical eyes, blurry, low quality, jpeg artifacts, text, watermark, logo, "
              "bokeh, studio portrait, stock photo, glamour, light skin when African people were asked for")


def polli_key():
    try:
        return clean_key(open(POLLI_KEY_FILE).read()) or None if os.path.exists(POLLI_KEY_FILE) else None
    except Exception:
        return None


def picture_size(prompt, big=False):
    """Pick the shape from the words: wide scenes landscape, people portrait, else portrait phone shape."""
    low = (prompt or "").lower()
    if BANANA.get("aspect") in ("16:9", "3:2", "4:3") or re.search(
            r"\b(landscape|wide|panorama|scenery|city ?scape|skyline|sunset over|banner|wallpaper for (pc|laptop))\b", low):
        w, h = (1216, 832) if big else (896, 640)
    elif BANANA.get("aspect") == "1:1" or re.search(r"\b(square|logo|icon|profile pic|avatar)\b", low):
        w, h = (1024, 1024) if big else (768, 768)
    else:
        w, h = (832, 1216) if big else (640, 896)
    return w, h


def _polli_keyed(prompt, key):
    """Pollinations with the user's own free key: sharper Z-Image / Flux models at full size."""
    w, h = picture_size(prompt, big=True)
    q = urllib.parse.quote(prompt)
    for model in ("zimage", "flux"):
        url = (f"{POLLI_GEN}{q}?model={model}&width={w}&height={h}&seed={random.randint(1, 999999)}"
               f"&enhance=false&nologo=true&private=true&negative_prompt={urllib.parse.quote(NEG_PROMPT)}")
        try:
            code, ctype, data = _fetch(url, timeout=90, headers={"Authorization": "Bearer " + key})
            if ctype.startswith("image") and len(data) > 2000:
                return save_picture(polish_picture(data)), None
        except urllib.error.HTTPError as e:
            log(f"POLLI {model} {e.code}")
            if e.code == 400 and "safe" in e.read().decode("utf8", "ignore").lower():
                return None, "refused"
            if e.code in (401, 403):
                return None, "badkey"
        except Exception as e:
            log(f"POLLI {model} failed: {e}")
            return None, "net"
    return None, "busy"


def _pollinations(prompt):
    """Pollinations: the user's own free key first (best quality), else the no-key classic maker
    (limited to about 1 picture per 45 s per phone, so wait once if asked)."""
    key = polli_key()
    if key:
        path, why = _polli_keyed(prompt, key)
        if path or why == "refused":
            return path, why
    w, h = picture_size(prompt)
    q = urllib.parse.quote(prompt)
    for attempt in range(2):
        url = f"{POLLI_URL}{q}?width={w}&height={h}&nologo=true&enhance=false&seed={random.randint(1, 99999)}"
        try:
            code, ctype, data = _fetch(url, timeout=60)
            if ctype.startswith("image") and len(data) > 2000:
                return save_picture(polish_picture(data, crop_logo=True)), None
            return None, "busy"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf8", "ignore")
            if e.code == 400:
                return None, "refused"
            wait = _retry_after(body, 0)
            log(f"POLLINATIONS {e.code}: retry after {wait}s")
            if attempt == 0 and e.code in (402, 429, 503) and 0 < wait <= 15:
                time.sleep(wait + 1)
                continue
            return None, "busy"
        except Exception as e:
            log(f"POLLINATIONS failed: {e}")
            return None, "net"
    return None, "busy"


def polish_picture(data, crop_logo=False):
    """Gentle photo finishing for the free makers: a touch of sharpening, contrast and warmth,
    like a phone camera does. Never changes the content; returns the original bytes if PIL is missing."""
    try:
        import io
        from PIL import Image, ImageEnhance, ImageFilter
        im = Image.open(io.BytesIO(data)).convert("RGB")
        if crop_logo:                       # the free maker stamps its name in the bottom corner
            W, H = im.size
            im = im.crop((0, 0, W, int(H * 0.955)))
        if max(im.size) < 900:
            scale = 1216.0 / max(im.size)
            im = im.resize((int(im.size[0] * scale), int(im.size[1] * scale)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=70, threshold=3))
        im = ImageEnhance.Contrast(im).enhance(1.05)
        im = ImageEnhance.Color(im).enhance(1.04)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=92)
        return buf.getvalue()
    except Exception as e:
        log(f"PICTURE polish skipped: {e}")
        return data


def _horde_image(prompt, budget=150):
    """AI Horde (free, anonymous key): send the job, wait for a volunteer computer, download the picture."""
    hdr = {"apikey": "0000000000", "Client-Agent": "Genius:" + VERSION + ":ssalimuto",
           "Content-Type": "application/json"}
    w, h = picture_size(prompt, big=True)
    jobs = [  # realistic photo models first (sharper skin, faces, light); the small default if refused
        {"prompt": prompt + " ### " + NEG_PROMPT,
         "params": {"width": w, "height": h, "steps": 28, "cfg_scale": 5.5, "sampler_name": "k_dpmpp_2m",
                    "karras": True, "n": 1},
         "models": ["Juggernaut XL", "AlbedoBase XL (SDXL)", "RealVisXL", "ZavyChromaXL"]},
        {"prompt": prompt + " ### cartoon, drawing, anime, painting, text, watermark, blurry, deformed",
         "params": {"width": 512, "height": 704, "steps": 22, "n": 1}},
    ]
    jid = None
    for job in jobs:
        job.update({"nsfw": False, "censor_nsfw": True, "r2": True})
        try:
            _, _, raw = _fetch(HORDE_URL + "/generate/async", timeout=30, data=json.dumps(job).encode(), headers=hdr)
            jid = json.loads(raw)["id"]
            break
        except urllib.error.HTTPError as e:
            log(f"HORDE submit {e.code}: trying the smaller job")
            continue
        except Exception as e:
            log(f"HORDE submit failed: {e}")
            return None, "net"
    if not jid:
        return None, "busy"
    t_end = time.time() + budget
    done = False
    while time.time() < t_end:
        time.sleep(4)
        try:
            _, _, raw = _fetch(f"{HORDE_URL}/generate/check/{jid}", timeout=20, headers=hdr)
            st = json.loads(raw)
        except Exception:
            continue
        if st.get("faulted") or st.get("is_possible") is False:
            break
        if st.get("done"):
            done = True
            break
    try:
        if not done:
            _fetch(f"{HORDE_URL}/generate/status/{jid}", timeout=15, headers=hdr, method="DELETE")
            return None, "busy"
        _, _, raw = _fetch(f"{HORDE_URL}/generate/status/{jid}", timeout=30, headers=hdr)
        gen = (json.loads(raw).get("generations") or [{}])[0]
        if gen.get("censored"):
            return None, "refused"
        img = gen.get("img", "")
        if img.startswith("http"):
            _, _, data = _fetch(img, timeout=60)
        else:
            data = base64.b64decode(img)
        if len(data) > 2000:
            return save_picture(polish_picture(data)), None
    except Exception as e:
        log(f"HORDE result failed: {e}")
    return None, "busy"


def free_image(prompt, tries=2):
    """Free picture makers (no key): Pollinations first, then AI Horde. Returns (path, friendly_error)."""
    short = _short_prompt(prompt)
    reasons = []
    path, why = _pollinations(short)
    if path:
        return path, None
    reasons.append(why)
    if why != "refused":
        path, why = _horde_image(short)
        if path:
            return path, None
        reasons.append(why)
    if "refused" in reasons:
        return None, "The picture maker won't draw that description. Try different, gentler words."
    if all(r == "net" for r in reasons):
        return None, "I couldn't reach the picture makers. Check your internet (or move to better signal) and try again."
    return None, FREE_DRAW_FAIL


NOT_REAL_WORDS = ("cartoon", "anime", "manga", "comic", "illustration", "illustrated", "drawing",
                  "drawn", "sketch", "painting", "painted", "clipart", "clip art", "3d render",
                  "render", "pixar", "disney", "chibi", "vector", "emoji", "doodle")
PHOTO_STYLE = ("real unedited photo taken with an Android phone camera, casual everyday snapshot, "
               "real human skin texture with pores, true-to-life colours, natural light, "
               "everything in focus, ordinary real background, no bokeh, no studio lighting, no filter, "
               "not a cartoon, not an illustration, not a painting, not 3D, not a stock photo")

# 111.6: people in Genius pictures look like the people of Uganda unless the request says otherwise
_PERSON_RE = re.compile(r"\b(man|men|woman|women|boy|girls?|boys|guy|lady|ladies|person|people|student|students|"
                        r"teacher|doctor|nurse|farmer|child|children|kid|kids|baby|family|mother|father|mum|mom|dad|"
                        r"grandma|grandmother|grandfather|couple|friends?|portrait|selfie|face|bride|groom|"
                        r"pastor|soldier|player|footballer|musician|singer|dancer|crowd|worker|driver|me|myself)\b", re.I)
_RACE_RE = re.compile(r"\b(white|caucasian|european|asian|chinese|japanese|korean|indian|arab|latino|latina|hispanic|"
                      r"mzungu|blonde|red hair|mixed race|american|british|mexican|brazilian)\b", re.I)


def ugandan_people(text, original=""):
    """Put 'Black Ugandan, dark brown skin' at the very start when people are in the picture
    and no other look was asked for (free picture makers otherwise default to other faces)."""
    both = (original or "") + " " + text
    if not _PERSON_RE.search(both) or _RACE_RE.search(original or text):
        return text
    if re.search(r"\b(black african|ugandan|dark brown skin)\b", text[:120], re.I):
        return text
    return ("Black Ugandan East African people with dark brown skin, African facial features and short black "
            "kinky hair, real ordinary Ugandans. " + text)


def realistic_prompt(prompt):
    """Always photo-real: remove cartoon words, add camera detail, and let an AI describe the scene like a photographer."""
    p = prompt
    for w in NOT_REAL_WORDS:
        p = re.sub(r"\b" + re.escape(w) + r"s?\b", "", p, flags=re.I)
    p = re.sub(r"\s+", " ", p).strip(" ,.") or "a person"
    try:
        better = ask_gemini(
            "Rewrite this as ONE plain description of a REAL casual phone photo (max 60 words): who or what is in "
            "it, their face and expression, clothes, the real everyday place behind them (for Uganda use real "
            "places like painted plaster walls, brick houses, red soil roads, markets, classrooms). People are "
            "Black Ugandans with dark brown skin unless the request says otherwise. Ordinary phone snapshot, "
            "not a glamour or stock photo. No cartoon or art words. Only the description.\n\nRequest: " + p,
            max_tokens=150)
        if better and 15 < len(better) < 600 and "couldn" not in better.lower() and "no ai" not in better.lower():
            p = better.strip().strip('"')
            for w in NOT_REAL_WORDS:
                p = re.sub(r"\b" + re.escape(w) + r"s?\b", "", p, flags=re.I)
    except Exception:
        pass
    return ugandan_people(p, prompt) + ". " + PHOTO_STYLE


ME_WORDS = re.compile(r"\b(me|my face|myself|my photo|like me|of me)\b", re.I)
# "create FOR ME a picture of a man" / "make me a photo of a girl" are about someone else, not my face
_ME_ASKER = re.compile(r"\b(for|to|give|show|make|create|draw|generate|send|help|can you|could you|please)\s+me\b"
                       r"(?!\s+(look|looking|as|in|wearing|holding|smil\w*|stand\w*|sit\w*|near|at|with|like|happy|sad|old|young|tall|fat|thin|beautiful|handsome)\b)", re.I)


def about_me(prompt):
    """True only when the picture should show the user's own face."""
    p = _ME_ASKER.sub(" ", prompt or "")
    return bool(ME_WORDS.search(p))


_DIR_OK = {}


def _dir_writable(d):
    """True if we can really create files in d (Android 10+ may refuse shared folders). Cached."""
    if d in _DIR_OK:
        return _DIR_OK[d]
    ok = False
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, f".genius_probe_{os.getpid()}_{random.randint(1000, 9999)}")
        with open(probe, "wb") as f:
            f.write(b"ok")
        os.remove(probe)
        ok = True
    except Exception as e:
        log(f"STORAGE not writable {d}: {e}")
    _DIR_OK[d] = ok
    return ok


def private_dir(sub=""):
    """Genius's own folder inside the app: always writable, even when Android blocks Download."""
    base = os.path.join(ROOT, "genius_files")
    if not CURRENT["owner"]:
        base = os.path.join(base, "users", CURRENT["name"])
    d = os.path.join(base, sub) if sub else base
    os.makedirs(d, exist_ok=True)
    return d


def genius_dl(sub=""):
    """Download/Genius for the owner, Download/Genius/users/<name> for other accounts.
    Falls back to Genius's own folder when the phone doesn't allow writing to Download."""
    if os.path.isdir("/storage/emulated/0"):
        base = "/storage/emulated/0/Download/Genius"
        if not CURRENT["owner"]:
            base = os.path.join(base, "users", CURRENT["name"])
        d = os.path.join(base, sub) if sub else base
        if _dir_writable(d):
            return d
    return private_dir(sub)


def nice_where(path):
    """Where a saved file is, in words a person can follow."""
    p = os.path.dirname(os.path.abspath(path or ""))
    if p.startswith("/storage/emulated/0/"):
        return p.replace("/storage/emulated/0/", "") + " on your phone"
    return "Genius's own storage (type 'storage' to see it)"


def set_my_photo(src=None):
    """Save a face photo as Download/Genius/me.jpg: the given file, or the newest photo/screenshot on the phone."""
    if not src:
        best, bt = None, 0
        for d in ("/storage/emulated/0/Download", "/storage/emulated/0/DCIM/Camera",
                  "/storage/emulated/0/Pictures/Screenshots", "/storage/emulated/0/DCIM/Screenshots",
                  "/storage/emulated/0/Pictures"):
            try:
                for n in os.listdir(d):
                    if n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        f = os.path.join(d, n)
                        t = os.path.getmtime(f)
                        if t > bt:
                            best, bt = f, t
            except Exception:
                continue
        src = best
    if not src or not os.path.exists(src):
        return None
    data = open(src, "rb").read()
    for d in (genius_dl(), private_dir()):
        out = os.path.join(d, "me.png" if src.lower().endswith(".png") else "me.jpg")
        if os.path.abspath(out) == os.path.abspath(src):
            return out
        for n in ("me.jpg", "me.jpeg", "me.png"):
            for dd in (genius_dl(), private_dir()):
                try:
                    os.remove(os.path.join(dd, n))
                except Exception:
                    pass
        try:
            with open(out, "wb") as b:
                b.write(data)
            return out
        except Exception as e:
            log(f"SETME save failed in {d}: {e}")
    return None


def my_photo():
    """The user's own reference photo: Download/Genius/me.jpg (or .png)."""
    for d in (genius_dl(), private_dir(), "."):
        for n in ("me.jpg", "me.jpeg", "me.png"):
            f = os.path.join(d, n)
            if os.path.exists(f):
                return f
    return None


def profile_photo():
    """This person's profile picture (each account has its own). Owner falls back to their face photo."""
    try:
        d = private_dir("profile")
        pics = sorted(n for n in os.listdir(d) if n.startswith("pic_") and n.endswith(".jpg"))
        if pics:
            return os.path.join(d, pics[-1])
    except Exception:
        pass
    return my_photo() if CURRENT.get("owner") else None


def set_profile_photo(src):
    """Crop the picture to a neat square around the face, save it as this person's profile picture."""
    from PIL import Image, ImageOps
    if not src or not os.path.exists(src):
        return None
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    W, H = im.size
    side = min(W, H)
    cx, cy = W / 2.0, H * (0.42 if H > W else 0.5)
    try:
        faces = face_boxes(src, 3)
        if faces:
            x, y, r = max(faces, key=lambda f: f[2])
            cx, cy, side = x, y + r * 0.25, min(side, max(r * 3.2, side * 0.45))
    except Exception:
        pass
    left = int(min(max(0, cx - side / 2), W - side))
    top = int(min(max(0, cy - side / 2), H - side))
    im = im.crop((left, top, left + int(side), top + int(side))).resize((512, 512), Image.LANCZOS)
    d = private_dir("profile")
    for n in os.listdir(d):
        if n.startswith("pic_"):
            try:
                os.remove(os.path.join(d, n))
            except Exception:
                pass
    out = os.path.join(d, f"pic_{int(time.time())}.jpg")        # new name each time so the picture refreshes
    im.save(out, quality=92)
    return out


def remove_profile_photo():
    d = private_dir("profile")
    n_removed = 0
    for n in os.listdir(d):
        if n.startswith("pic_"):
            try:
                os.remove(os.path.join(d, n))
                n_removed += 1
            except Exception:
                pass
    return n_removed


def gemini_image(prompt):
    """Draw a REAL-looking picture: Gemini first, then the free picture maker. Never cartoons.
    If the request is about the user ("draw me...") and me.jpg exists, the SAME face is kept."""
    ref = my_photo() if about_me(prompt) else None
    if ref:
        path, err = _gemini_image(prompt, ref)
        if path:
            return path, None
        if err == "no key":
            return None, ("To keep YOUR face I need a Gemini key with picture access. Type setkey and your key "
                          "from aistudio.google.com/apikey. The free maker can only invent new people.")
        return None, ("To keep YOUR face I need Gemini picture access, and it said: " + str(err) + "\n"
                      "The free maker can't copy a real face, only invent new people. "
                      "Turn on billing for your key at aistudio.google.com, then try again.")
    real = realistic_prompt(prompt) if connected_ais() else _short_prompt(prompt)
    path, err = _gemini_image(real)
    if path:
        return path, None
    log(f"DRAW: Gemini couldn't ({err}); using free picture maker")
    path, err2 = free_image(real)
    return (path, None) if path else (None, err2)


LAST_IMAGE = {"path": None, "time": 0, "prompt": ""}
EDIT_START = re.compile(
    r"^(make (me|it|him|her|them|the|us)|put (me|him|her|it|them|us)|place (me|him|her)|change|now\b|add |remove |"
    r"take (out|off|away)|turn |move |edit |swap |replace |give (me|him|her)|same (but|picture|photo)|"
    r"at (night|sunset|sunrise|dawn|dusk)|in (the )?(night|rain|snow|evening|morning)|blur|zoom|closer|"
    r"wider|near |next to |in front of|behind |wearing |holding |without |more |less |brighter|darker|"
    r"let (me|him|her|it) |show (me|him|her) (near|in|at|with|holding|wearing))", re.I)
IMAGE_TIPS = ("Want changes? Just tell me, e.g.\n"
              "- make me near a modern skyscraper\n"
              "- change it to night with city lights\n"
              "- blur the background so I stand out\n"
              "- put me in a black suit\n"
              "- make me smile\n"
              "Say 'new picture' to start fresh, or 'undo picture' to go back.")
IMAGE_STACK = []


def remember_image(path, prompt):
    if LAST_IMAGE["path"]:
        IMAGE_STACK.append(dict(LAST_IMAGE))
        del IMAGE_STACK[:-10]
    LAST_IMAGE.update(path=path, time=time.time(), prompt=prompt)


def is_image_edit(low):
    """A follow-up like 'make me near building' right after a picture = edit that picture."""
    return bool(LAST_IMAGE["path"]) and time.time() - LAST_IMAGE["time"] < 3600 \
        and os.path.exists(LAST_IMAGE["path"]) and bool(EDIT_START.match(low.strip())) \
        and not NEW_PIC.search(low)


# 111.7: "make me a photo of a girl" / "give me a picture of a cow" asks for a NEW picture, not a change
NEW_PIC = re.compile(r"^\s*(make|give|create|draw|generate|show)\s+(me|us)\s+(a|an|another|one|some|\d+)\s+(new\s+)?"
                     r"(picture|photo|image|pic|drawing|portrait)s?\s+(of|with|showing)\b", re.I)


def blend_images(paths, instruction):
    path, err = _gemini_image(instruction, blend=paths)
    if not path and err == "no key":
        err = "Blending photos needs a Gemini key. Type setkey and your key from aistudio.google.com/apikey."
    return path, (None if path else err)


def edit_image(instruction):
    """Change the last picture the way Gemini does: same person, only what was asked changes."""
    base = LAST_IMAGE["path"]
    path, err = _gemini_image(instruction, edit=base)
    if path:
        return path, None
    log(f"EDIT: Gemini couldn't ({err}); not redrawing, so the face and position never change")
    why = ("there's no Gemini key yet (type setkey and your key from aistudio.google.com/apikey)"
           if err == "no key" else str(err))
    return None, ("I couldn't make that AI change, so your picture is unchanged. Reason: " + why + "\n"
                  "AI edits need Nano Banana (a Gemini key with billing). Instant looks and effects in "
                  "Fun studio (say 'transform' or 'looks') work offline and keep your picture the same.")


def _img_part(path):
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(open(path, "rb").read()).decode()}}


def _gemini_image(prompt, ref=None, edit=None, blend=None):
    """Draw a picture from text with Gemini, optionally keeping the face in a reference photo.
    edit = path of the last picture: change only what the user asked (like Gemini's chat editing)."""
    if not os.path.exists(KEY_FILE):
        return None, "no key"
    key = clean_key(open(KEY_FILE).read())
    if blend:
        parts = [_img_part(b) for b in blend[:4]]
        parts.append({"text":
            "Combine these photos into ONE new real photograph: " + prompt + ". Keep every person's exact face, "
            "skin tone, hair and body from their photo. Matching light, shadows, perspective and colour so it "
            "looks like one real smartphone photo, real skin texture, correct hands. No text, no watermark."})
    elif edit:
        parts = [_img_part(edit)]
        face = my_photo()
        if face:
            parts.append(_img_part(face))
        parts.append({"text":
            "Edit the FIRST photo. Change: " + prompt + ". Keep the SAME person with the exact same face, "
            "head shape, skin tone, hair and body" + (" (the second photo shows their real face)" if face else "") +
            ". Keep their clothes, pose and everything else the same unless the change asks otherwise. "
            "Keep the exact same composition: the person stays in the same position, same size, same angle and "
            "same framing, same image width and height; do not move, crop, zoom, rotate or re-pose anything. "
            "Result must be a real, photorealistic smartphone photograph with natural light, real skin texture, "
            "correct hands and fingers, believable shadows and perspective. Not a cartoon, no text, no watermark."})
    elif ref:
        mime = "image/png" if ref.lower().endswith(".png") else "image/jpeg"
        parts = [{"inlineData": {"mimeType": mime, "data": base64.b64encode(open(ref, "rb").read()).decode()}},
                 {"text": "Photorealistic smartphone photo of the same person as in the reference image, same face "
                          "(head shape, hair, eyes, nose, lips, jaw, skin tone). Scene: " + prompt + ". "
                          "Relaxed confident pose, warm natural light (golden hour outdoors), the background softly "
                          "blurred so the person stands out, 35mm lens, real skin texture, correct hands. "
                          "Real photograph, no text, no watermark."}]
    else:
        parts = [{"text":
            "Create a highly realistic, photorealistic photograph of: " + prompt +
            ". Natural lighting, real textures, sharp focus, true-to-life colours, "
            "lifelike detail, like a real photo taken with a professional camera. "
            "Not a cartoon, not a drawing."}]
    body = json.dumps({
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": dict({"responseModalities": ["IMAGE", "TEXT"], "temperature": 0.8},
                                 **({"imageConfig": {"aspectRatio": BANANA["aspect"]}} if BANANA["aspect"] else {})),
    }).encode()
    last = "I couldn't draw that. Try again."
    for model in image_models():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json", "x-goog-api-key": key})
        try:
            try:
                r = urllib.request.urlopen(req, timeout=90, context=ssl_context())
            except urllib.error.URLError as e:
                if "CERTIFICATE" not in str(e).upper():
                    raise
                r = urllib.request.urlopen(req, timeout=90, context=ssl._create_unverified_context())
            with r:
                parts = json.load(r)["candidates"][0]["content"]["parts"]
            for part in parts:
                data = part.get("inlineData") or part.get("inline_data")
                if data and data.get("data"):
                    return save_picture(base64.b64decode(data["data"])), None
            last = "The model sent no picture. Try a simpler description."
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf8", "ignore")
            if e.code in (401, 403) or (e.code == 400 and "API key" in detail):
                return None, key_reason(e.code, detail)
            if e.code == 404:
                last = "Drawing isn't on this key's free plan yet."
                continue
            if e.code == 429:
                last = "Free drawing limit reached. Wait a while and try again."
            else:
                last = "Google is busy. Try again shortly."
            continue
        except Exception as e:
            log(f"DRAW net error on {model}: {e}")
            last = "Your internet is too slow for drawing right now. Move to better signal and try again."
            break                          # the network is the problem: other models won't help
    return None, last


def _gemini_try(key, use_search, max_tokens, timeout, deep):
    """One pass over a set of models. Returns (reply, err, fatal)."""
    models = DEEP_MODELS if use_search else FAST_MODELS
    payload = {
        "systemInstruction": {"parts": [{"text": DEEP_RULES if deep else FAST_RULES}]},
        "contents": history[-20:] if deep else history[-6:],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]
    body = json.dumps(payload).encode()
    err = "I couldn't reach Google. Try again."
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(2):          # one retry when Google is busy
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json", "x-goog-api-key": key})
            try:
                try:
                    r = urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
                except urllib.error.URLError as e:
                    if "CERTIFICATE" not in str(e).upper():
                        raise
                    r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
                with r:
                    parts = json.load(r)["candidates"][0]["content"]["parts"]
                reply = "\n".join(p["text"] for p in parts
                                  if "text" in p and not p.get("thought")).strip()
                if reply:
                    return reply, None, False
                break                      # empty answer: try next model
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf8", "ignore")
                if e.code in (401, 403) or (e.code == 400 and "API key" in detail):
                    return None, key_reason(e.code, detail), True
                if e.code == 429:
                    err = "Free limit reached for now. Wait a minute and ask again."
                    break                  # next model won't help the quota
                if e.code in (500, 503) and attempt == 0:
                    time.sleep(2)
                    continue               # busy: retry same model once
                err = "Google is busy right now. Ask again in a moment."
                break                      # try next model
            except Exception as e:
                err = ("Your internet is slow right now. Move to better signal, "
                       "or turn data off and on, then ask again.")
                if _is_net_error(e):
                    return None, err, False    # no internet: don't wait on more models
                break                      # odd reply: try next (lighter) model
    return None, err, False


def gemini_reply(text, deep=False):
    """Returns (reply, error). Deep tries the strong models + Google Search,
    then quietly falls back to the fast models so you still get an answer."""
    if not os.path.exists(KEY_FILE):
        return None, "no key"
    key = clean_key(open(KEY_FILE).read())
    history.append({"role": "user", "parts": [{"text": text}]})

    if deep:
        reply, err, fatal = _gemini_try(key, True, 2048, 90, True)
        if reply is None and not fatal:
            # the strong path failed; try the fast models with no web search
            reply, err2, fatal = _gemini_try(key, False, 800, 30, True)
            if reply is None:
                err = err2
    else:
        reply, err, fatal = _gemini_try(key, False, 220, 25, False)

    if reply is not None:
        history.append({"role": "model", "parts": [{"text": reply}]})
        save_memory()
        return reply, None
    history.pop()
    return None, err



# ---------------- agent: the AI chooses its own tools ----------------
ANSWER_STYLE = (" For questions about knowledge, people, places, history, science, school work or how something "
                "works, answer like Google's AI Mode: start with one clear sentence that directly answers, then "
                "2 to 5 short bullet points that each start with a bold label, like '- **Origin:** ...'. Use exact "
                "names, dates and numbers. If you searched the web, add a last-but-one line 'Sources: ' with the "
                "site names. Always finish knowledge answers with one final line exactly like "
                "'Ask next: <short follow-up question> | <another short follow-up question>'. "
                "For chat, feelings or simple tasks, just reply naturally without bullets or Ask next.")

AGENT_RULES = ("You are Genius, the private assistant of ssalimuto, a young person in Uganda "
               "(timezone Africa/Kampala). Reply in clear, simple English. "
               "You are their personal AI: a helper for anything in their life, and a warm, "
               "steady source of emotional support. When they share feelings, listen first: "
               "reflect what they feel, be kind and calm, never judge, ask one gentle question, "
               "then offer one small practical step if they want it. Encourage real people in "
               "their life (family, friends, a counsellor). You are an AI, not a person or a "
               "doctor; say so if asked. If they mention self-harm, suicide, abuse or danger, "
               "take it seriously, stay with them, and urge them to call 999 or 112, or Sauti "
               "116, or Mental Health Uganda 0800 21 21 21. Never help with anything that could "
               "harm them or others. Protect their privacy and safety. "
               "You have tools: use them "
               "whenever they help, and you may use several in a row (for example check the weather "
               "and then set a reminder). Use search_web for news, prices, people, facts you are not "
               "sure of, or anything recent. Never invent tool results. After using tools, answer in "
               "1 to 4 short sentences saying what you did. Never claim you did something a tool "
               "did not confirm.") + ANSWER_STYLE

AGENT_TOOLS = [{"functionDeclarations": [
    {"name": "get_time", "description": "Current local date and time.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "get_weather", "description": "Current weather and today's temperature range for a city.",
     "parameters": {"type": "OBJECT", "properties": {
         "city": {"type": "STRING", "description": "City name, e.g. Kampala"}}, "required": ["city"]}},
    {"name": "calculate", "description": "Do exact arithmetic, e.g. 12*8+5 or (2500-300)/4.",
     "parameters": {"type": "OBJECT", "properties": {
         "expression": {"type": "STRING"}}, "required": ["expression"]}},
    {"name": "add_note", "description": "Save a note for the owner.",
     "parameters": {"type": "OBJECT", "properties": {
         "text": {"type": "STRING"}}, "required": ["text"]}},
    {"name": "read_notes", "description": "Read the owner's saved notes.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "set_reminder", "description": "Remind the owner after some minutes (app must stay open).",
     "parameters": {"type": "OBJECT", "properties": {
         "minutes": {"type": "INTEGER"}, "text": {"type": "STRING"}},
         "required": ["minutes", "text"]}},
    {"name": "battery", "description": "Phone battery level and charging state.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "draw_picture", "description": "Create a realistic picture from a description and show it.",
     "parameters": {"type": "OBJECT", "properties": {
         "description": {"type": "STRING"}}, "required": ["description"]}},
    {"name": "remember_fact", "description": "Save a lasting fact about the owner (goals, school, likes, plans) so future answers fit them.",
     "parameters": {"type": "OBJECT", "properties": {
         "fact": {"type": "STRING"}}, "required": ["fact"]}},
    {"name": "log_money", "description": "Record money spent (kind out) or received (kind in) in UGX.",
     "parameters": {"type": "OBJECT", "properties": {
         "amount": {"type": "NUMBER"}, "kind": {"type": "STRING", "enum": ["in", "out"]},
         "category": {"type": "STRING"}, "note": {"type": "STRING"}},
         "required": ["amount", "kind", "category"]}},
    {"name": "money_summary", "description": "Owner's spending, income and savings goals.",
     "parameters": {"type": "OBJECT", "properties": {"days": {"type": "NUMBER"}}}},
    {"name": "study_status", "description": "Owner's subjects, exam countdown, quiz scores, weak topics.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "search_web", "description": "Search Google for up-to-date facts and return a short answer.",
     "parameters": {"type": "OBJECT", "properties": {
         "query": {"type": "STRING"}}, "required": ["query"]}},
]}]


def _post_gemini(key, model, payload, timeout):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", "x-goog-api-key": key})
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
    except urllib.error.URLError as e:
        if "CERTIFICATE" not in str(e).upper():
            raise
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
    with r:
        return json.load(r)


def _search_web(key, query):
    payload = {"contents": [{"role": "user", "parts": [{"text": query}]}],
               "tools": [{"google_search": {}}],
               "systemInstruction": {"parts": [{"text":
                   "Answer accurately and briefly (under 120 words) using Google Search."}]},
               "generationConfig": {"maxOutputTokens": 600}}
    for model in ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"):
        try:
            d = _post_gemini(key, model, payload, 45)
            parts = d["candidates"][0]["content"]["parts"]
            t = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if t:
                try:
                    chunks = d["candidates"][0].get("groundingMetadata", {}).get("groundingChunks", [])
                    names = []
                    for c in chunks:
                        n = (c.get("web") or {}).get("title", "").strip()
                        if n and n not in names:
                            names.append(n)
                    if names:
                        t += "\nSources: " + ", ".join(names[:4])
                except Exception:
                    pass
                return t
        except Exception as e:
            if _is_net_error(e):
                break
            continue
    return "Search failed right now."


ABOUT_FILE = "about_me.txt"


def about_me():
    try:
        return open(ABOUT_FILE).read().strip()[-3000:]
    except Exception:
        return ""


def remember_about_me(fact):
    with open(ABOUT_FILE, "a") as f:
        f.write("- " + fact.strip() + "\n")


def run_tool(name, args, key, ui):
    """Execute one tool. ui gives safe hooks into the screen."""
    try:
        if name == "get_time":
            return time.strftime("%I:%M %p, %A %d %B %Y")
        if name == "get_weather":
            return weather_report(args.get("city", "Kampala"))
        if name == "calculate":
            return do_calc(str(args.get("expression", "")))
        if name == "add_note":
            with open(NOTES_FILE, "a") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M") + " | " + str(args.get("text", "")) + "\n")
            return "Saved."
        if name == "read_notes":
            lines = open(NOTES_FILE).readlines() if os.path.exists(NOTES_FILE) else []
            return "".join(lines[-20:]) or "No notes yet."
        if name == "set_reminder":
            m = max(1, int(args.get("minutes", 1)))
            ui["remind"](m, str(args.get("text", "Reminder")))
            return f"Reminder set for {m} minutes from now."
        if name == "battery":
            return battery_text()
        if name == "draw_picture":
            desc = str(args.get("description", ""))
            path, err = gemini_image(desc)
            if path:
                ui["image"](path, desc)
                return "Picture created and shown on screen."
            return err or "Drawing failed."
        if name == "remember_fact":
            remember_about_me(str(args.get("fact", "")))
            return "Remembered."
        if name == "log_money":
            money_add(args.get("kind", "out"), float(args.get("amount", 0)),
                      str(args.get("category", "other")), str(args.get("note", "")))
            return "Recorded."
        if name == "money_summary":
            return money_summary(None, int(args.get("days", 7) or 7))
        if name == "study_status":
            return study_status()
        if name == "search_web":
            return _search_web(key, str(args.get("query", "")))
    except Exception as e:
        return f"Tool error: {e}"
    return "Unknown tool."



# ---------- Genius Brain: learns from every unique question and every correction ----------
BRAIN_FILE = "genius_brain.json"
LAST_QA = {"q": "", "a": ""}
_STOP = set("the a an is are was were to of in on for and or what how why who when which do does i you me my it this that with be can please tell about".split())


def _words(t):
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(w) > 2 and w not in _STOP}


def brain_load():
    try:
        return json.load(open(BRAIN_FILE))
    except Exception:
        return []


def brain_save(items):
    items = sorted(items, key=lambda x: (x.get("score", 0), x.get("t", 0)), reverse=True)[:400]
    try:
        json.dump(items, open(BRAIN_FILE, "w"))
    except Exception as e:
        log(f"brain save failed: {e}")


def brain_add(lesson, q="", score=1, kind="lesson"):
    lesson = (lesson or "").strip()
    if len(lesson) < 8:
        return
    items = brain_load()
    for it in items:                                   # same lesson again: make it stronger
        if it["lesson"].lower() == lesson.lower():
            it["score"] = it.get("score", 0) + 1
            it["t"] = time.time()
            brain_save(items)
            return
    items.append({"lesson": lesson[:400], "q": q[:200], "score": score, "kind": kind, "t": time.time()})
    brain_save(items)


# 111.6: lessons built into Genius's brain for good (the owner taught them; they never fade)
CORE_LESSONS = (
    ("picture photo image draw make create portrait selfie person people man woman boy girl",
     "When making pictures of people, show real Black Ugandans with dark brown skin and African features, unless "
     "the person asks for someone else."),
    ("picture photo image draw make create portrait selfie",
     "Pictures should look like real, unedited Android phone photos in everyday Ugandan places (painted walls, "
     "brick houses, red soil roads, markets, classrooms), not glossy studio or stock portraits with blurred backgrounds."),
    ("uganda ugandan african africa people",
     "The user lives in Uganda: give examples, places, prices (UGX) and people that fit Uganda first."),
)


def core_lessons(text):
    w = _words(text)
    return [ls for keys, ls in CORE_LESSONS if w & set(keys.split())]


def brain_recall(text, n=4):
    """The lessons that best match this question, strongest first (the owner's core lessons always come first)."""
    want = _words(text)
    if not want:
        return ""
    core = core_lessons(text)
    scored = []
    for it in brain_load():
        hit = len(want & _words(it["lesson"] + " " + it.get("q", "")))
        if hit and it.get("score", 0) > -2:
            scored.append((hit * 2 + it.get("score", 0) + (3 if it.get("kind") == "correction" else 0), it))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = core + [it["lesson"] for _, it in scored[:n]]
    return ("\nLessons you learned before (trust these, corrections most of all):\n- " + "\n- ".join(best)) if best else ""


def brain_reflect(q, a):
    """After a new kind of question, Genius writes itself one lesson for next time (in the background)."""
    if len(q.strip()) < 4 or len(a) < 30:
        return
    def go():
        ask = ("Question: " + q[:600] + "\nAnswer given: " + a[:1500] +
               "\n\nWrite ONE short, reusable lesson (max 30 words) that would help answer similar "
               "questions better or faster next time: a key fact, a better method, or a mistake to avoid. "
               "If there is nothing worth learning, reply exactly NONE.")
        sysm = "You improve an assistant by writing short lessons for it. Be accurate; never invent facts."
        out = None
        for prov in ranked_providers():
            out = other_ai(prov, ask, system=sysm, max_tokens=80)
            if out:
                break
        if not out:
            try:
                out = ask_gemini(sysm + "\n\n" + ask, 80)
            except Exception:
                out = None
        if out and "NONE" not in out.upper()[:8]:
            brain_add(out.strip().strip('"'), q=q)
        brain_count_question(q)
    threading.Thread(target=go, daemon=True).start()


def brain_count_question(q):
    try:
        st = json.load(open("genius_brain_stats.json"))
    except Exception:
        st = {"questions": 0, "topics": {}}
    st["questions"] = st.get("questions", 0) + 1
    for w in list(_words(q))[:6]:
        st["topics"][w] = st["topics"].get(w, 0) + 1
    st["topics"] = dict(sorted(st["topics"].items(), key=lambda x: -x[1])[:60])
    try:
        json.dump(st, open("genius_brain_stats.json", "w"))
    except Exception:
        pass


def brain_report():
    items = brain_load()
    if not items:
        return "I haven't learned anything yet. Ask me things, correct me with 'better: ...', or say 'teach ...'."
    top = items[:8]
    lines = [f"{i+1}. {it['lesson']}" for i, it in enumerate(top)]
    try:
        st = json.load(open("genius_brain_stats.json"))
        top_t = ", ".join(list(st.get("topics", {}))[:6])
        extra = f"\nQuestions studied: {st.get('questions', 0)}. Your top topics: {top_t}."
    except Exception:
        extra = ""
    return f"I've learned {len(items)} lessons. My strongest:\n" + "\n".join(lines) + extra


def agent_reply(text, ui, deep=False):
    """The AI thinks, picks tools, uses their results, and answers. Returns (reply, error)."""
    if not os.path.exists(KEY_FILE):
        return None, "no key"
    key = clean_key(open(KEY_FILE).read())
    convo = [m for m in history[-(16 if deep else 8):]]
    convo.append({"role": "user", "parts": [{"text": text}]})
    models = ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite") if deep \
        else ("gemini-2.5-flash-lite", "gemini-flash-lite-latest", "gemini-2.5-flash")
    err = "Google is busy right now. Ask again in a moment."
    for model in models:
        work = list(convo)
        try:
            for step in range(5):                     # up to 5 tool rounds
                me = about_me()
                rules = AGENT_RULES + ("\nWhat you know about your owner (use it to personalise answers):\n" + me if me else "") + brain_recall(text)
                payload = {"systemInstruction": {"parts": [{"text": rules}]},
                           "contents": work, "tools": AGENT_TOOLS,
                           "generationConfig": {"maxOutputTokens": 1500 if deep else 500,
                                                "temperature": 0.6}}
                d = None
                for attempt in range(2):
                    try:
                        d = _post_gemini(key, model, payload, 90 if deep else 40)
                        break
                    except urllib.error.HTTPError as e:
                        if e.code in (500, 503) and attempt == 0:
                            time.sleep(2)
                            continue
                        raise
                parts = d["candidates"][0]["content"].get("parts", [])
                calls = [p["functionCall"] for p in parts if "functionCall" in p]
                if not calls:
                    reply = "\n".join(p.get("text", "") for p in parts
                                      if not p.get("thought")).strip()
                    if not reply:
                        break
                    history.append({"role": "user", "parts": [{"text": text}]})
                    history.append({"role": "model", "parts": [{"text": reply}]})
                    save_memory()
                    return reply, None
                work.append({"role": "model", "parts": parts})
                responses = []
                for c in calls:
                    log(f"AGENT TOOL: {c.get('name')}")
                    result = run_tool(c.get("name"), c.get("args") or {}, key, ui)
                    responses.append({"functionResponse": {
                        "name": c.get("name"), "response": {"result": result}}})
                work.append({"role": "user", "parts": responses})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf8", "ignore")
            if e.code in (401, 403) or (e.code == 400 and "API key" in detail):
                return None, key_reason(e.code, detail)
            if e.code == 429:
                err = "Free limit reached for now. Wait a minute and ask again."
            continue
        except Exception as e:
            err = ("Your internet is slow right now. Move to better signal, "
                   "or turn data off and on, then ask again.")
            if _is_net_error(e):
                return None, err               # fail fast: the next AI in the chain takes over
            continue
    # last resort: plain answer without tools
    reply, e2 = gemini_reply(text, False)
    return (reply, None) if reply else (None, e2 or err)


# ================= LIFE TOOLS: study coach, money, morning brief, freelance =================
LIFE_FILE = "life_data.json"


def life_load():
    d = {}
    try:
        d = json.load(open(LIFE_FILE))
    except Exception:
        pass
    d.setdefault("study", {"subjects": [], "exam": None, "scores": {}})
    d.setdefault("money", {"entries": [], "goals": {}})
    d.setdefault("brief", {"auto": True, "at": "", "city": "Kampala", "last": ""})
    d.setdefault("work", {"skills": ""})
    return d


def life_save(d):
    tmp = LIFE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f)
    os.replace(tmp, LIFE_FILE)


def parse_amount(text):
    """'2k' -> 2000, '1.5m' -> 1500000, '5,000' -> 5000, 'UGX 300' -> 300."""
    m = re.search(r"(\d[\d,]*\.?\d*)\s*([kKmM]?)", text or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    n *= {"k": 1000, "m": 1000000}.get(m.group(2).lower(), 1)
    return int(round(n))


def ugx(n):
    return f"UGX {int(n):,}"


def _ask_gemini_only(prompt, max_tokens=600, json_mode=False, search=False, system=None):
    """One-off question to Gemini (doesn't touch chat history). Returns text or None."""
    if not os.path.exists(KEY_FILE):
        return None
    key = clean_key(open(KEY_FILE).read())
    if search:
        return _search_web(key, prompt)
    me = about_me()
    sys_txt = system or ("You help " + CURRENT["name"] + ", a young person in Uganda. Use simple, clear English and "
               "Ugandan examples (UGX, Kampala, boda bodas, MTN/Airtel money) where useful."
               + ("\nAbout them:\n" + me if me else ""))
    cfg = {"maxOutputTokens": max_tokens, "temperature": 0.7}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    payload = {"systemInstruction": {"parts": [{"text": sys_txt}]},
               "contents": [{"role": "user", "parts": [{"text": prompt}]}],
               "generationConfig": cfg}
    for model in ("gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"):
        try:
            d = _post_gemini(key, model, payload, 45)
            parts = d["candidates"][0]["content"]["parts"]
            t = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if t:
                return t
        except Exception as e:
            if _is_net_error(e):
                break                      # no internet: let the next provider try at once
            continue
    return None


# ---- study ----
OFFLINE_QUIZ = [
    {"q": "Which part of the plant cell makes food by photosynthesis?",
     "o": ["Nucleus", "Chloroplast", "Cell wall", "Vacuole"], "a": "B", "topic": "Biology: cells",
     "why": "Chloroplasts hold chlorophyll, which traps sunlight to make food."},
    {"q": "What is 15% of 40,000 shillings?", "o": ["4,000", "6,000", "5,500", "8,000"],
     "a": "B", "topic": "Maths: percentages", "why": "0.15 x 40,000 = 6,000."},
    {"q": "Which gas do we breathe out more of than we breathe in?",
     "o": ["Oxygen", "Nitrogen", "Carbon dioxide", "Hydrogen"], "a": "C",
     "topic": "Biology: respiration", "why": "Respiration in cells releases carbon dioxide."},
    {"q": "Lake Victoria is shared by Uganda, Kenya and which other country?",
     "o": ["Rwanda", "Tanzania", "Burundi", "South Sudan"], "a": "B",
     "topic": "Geography: East Africa", "why": "Uganda, Kenya and Tanzania share Lake Victoria."},
    {"q": "Solve: 3x + 5 = 20", "o": ["x = 3", "x = 5", "x = 15", "x = 25"], "a": "B",
     "topic": "Maths: equations", "why": "3x = 15, so x = 5."},
    {"q": "What is the chemical symbol for sodium?", "o": ["S", "So", "Na", "Sd"], "a": "C",
     "topic": "Chemistry: elements", "why": "Na comes from its Latin name, natrium."},
]


def make_quiz(topic, subjects):
    want = topic or (random.choice(subjects) if subjects else "any secondary school subject")
    raw = ask_gemini(
        f"Write ONE multiple-choice question for a Ugandan secondary school student "
        f"(new lower secondary / UCE or UACE level, NCDC syllabus) on: {want}. "
        f'Reply as JSON: {{"q": question, "o": [four options without letters], '
        f'"a": "A"|"B"|"C"|"D", "topic": "Subject: topic", "why": one-sentence explanation}}.',
        500, json_mode=True)
    try:
        q = json.loads(raw) if raw and connected_ais() else None
        if q and len(q["o"]) == 4 and str(q["a"]).strip().upper() in ("A", "B", "C", "D") and q.get("q"):
            q["a"] = str(q["a"]).strip().upper()
            q.setdefault("topic", str(want).title())
            return q
    except Exception:
        pass
    # offline: prefer a question from the asked subject, and don't repeat the last one
    w = str(want).lower().split(":")[0].strip()
    pool = [x for x in OFFLINE_QUIZ if w and w in x["topic"].lower()] or OFFLINE_QUIZ
    last = getattr(make_quiz, "_last", None)
    pool = [x for x in pool if x["q"] != last] or pool
    q = dict(random.choice(pool))
    make_quiz._last = q["q"]
    return q


def exam_countdown(d):
    ex = d["study"].get("exam")
    if not ex:
        return ""
    try:
        days = (time.mktime(time.strptime(ex["date"], "%Y-%m-%d")) - time.time()) / 86400
        days = int(days) + 1
    except Exception:
        return ""
    if days < 0:
        return f"{ex['name']} has passed."
    return f"{days} days until {ex['name']} ({ex['date']})."


def weak_topics(d, n=3):
    rows = []
    for t, (right, total) in d["study"]["scores"].items():
        if total:
            rows.append((right / total, total, t))
    rows.sort()
    return [f"{t} ({int(p*100)}%)" for p, tot, t in rows[:n] if p < 0.8]


def study_status(d=None):
    d = d or life_load()
    s = d["study"]
    lines = []
    lines.append("Subjects: " + (", ".join(s["subjects"]) or "not set (type: subjects Maths, Biology, ...)"))
    lines.append(exam_countdown(d) or "No exam date set (type: exam UCE 2026-11-02).")
    tot_r = sum(v[0] for v in s["scores"].values())
    tot = sum(v[1] for v in s["scores"].values())
    if tot:
        lines.append(f"Quiz score so far: {tot_r}/{tot} ({int(tot_r*100/tot)}%).")
    w = weak_topics(d)
    if w:
        lines.append("Work on: " + ", ".join(w))
    return "\n".join(lines)


# ---- money ----
def money_add(kind, amount, category, note=""):
    d = life_load()
    d["money"]["entries"].append({"t": time.strftime("%Y-%m-%d %H:%M"), "kind": kind,
                                  "amt": int(amount), "cat": category or "other", "note": note})
    life_save(d)


def money_summary(d=None, days=7):
    d = d or life_load()
    cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    spent, got, cats = 0, 0, {}
    for e in d["money"]["entries"]:
        if e["t"][:10] < cutoff:
            continue
        if e["kind"] == "out":
            spent += e["amt"]
            cats[e["cat"]] = cats.get(e["cat"], 0) + e["amt"]
        else:
            got += e["amt"]
    out = [f"Last {days} days: spent {ugx(spent)}, received {ugx(got)}."]
    if cats:
        top = sorted(cats.items(), key=lambda x: -x[1])[:4]
        out.append("Biggest: " + ", ".join(f"{c} {ugx(v)}" for c, v in top) + ".")
    for name, g in d["money"]["goals"].items():
        pct = int(100 * g["saved"] / g["target"]) if g["target"] else 0
        out.append(f"Goal {name}: {ugx(g['saved'])} of {ugx(g['target'])} ({pct}%).")
    if not d["money"]["entries"] and not d["money"]["goals"]:
        return "No money records yet. Try: spent 2000 airtime, or got 50k pocket money."
    return "\n".join(out)


# ---- morning brief ----
def build_brief(with_news=True):
    d = life_load()
    hour = time.localtime().tm_hour
    hi = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
    parts = [f"{hi}, {CURRENT['name']}. It's {time.strftime('%A %d %B')}."]
    w = weather_report(d["brief"].get("city") or "Kampala")
    if not w.startswith("I couldn't"):
        parts.append(w)
    ex = exam_countdown(d)
    if ex:
        parts.append(ex)
    weak = weak_topics(d, 1)
    if weak:
        parts.append("Today, practise " + weak[0].split(" (")[0] + ". Type quiz to start.")
    m = money_summary(d, 7)
    if not m.startswith("No money"):
        parts.append(m.split("\n")[0])
    if os.path.exists(NOTES_FILE):
        notes = [l.split("|", 1)[-1].strip() for l in open(NOTES_FILE).readlines()[-2:]]
        if notes:
            parts.append("Your latest notes: " + "; ".join(notes) + ".")
    if with_news:
        n = ask_gemini("In one sentence, the most important news in Uganda today. "
                       "Start with 'In the news:'.", search=True)
        if n and "failed" not in n.lower():
            parts.append(n.strip())
    return " ".join(parts)


LIFE_HELP = """Study coach
- study: your progress and exam countdown
- subjects Maths, Biology, English: save your subjects
- exam UCE 2026-11-02: set an exam date
- quiz (or quiz chemistry): a question; answer A, B, C or D
- explain photosynthesis: simple explanation
- studyplan: today's plan, focused on weak topics

Money
- spent 2000 airtime chips / got 50k pocket money
- money (or money 30 for 30 days)
- goal phone 300k / put phone 10k

Morning brief
- brief: weather, exam, money, notes, Uganda news (spoken)
- brief at 07:00 / brief off / brief city Mityana
(it also runs the first time you open me each day)

Freelancing
- skills typing, graphic design, Canva
- cv: write your CV
- proposal <paste a job>: a winning reply
- gigs: real beginner jobs for your skills
- price <task>: what to charge"""


# ================= SOFTWARE BUILDER: Genius writes small programs =================
APPS_DIR = "genius_apps"


def build_program(idea):
    """Ask Gemini to write one runnable Python file. Returns (name, path, code) or error text."""
    raw = ask_gemini(
        "Write ONE complete Python 3 program for this idea:\n" + idea + "\n"
        "Rules: standard library only; no input() (use example values instead); no network "
        "attacks, no deleting files, no hacking, no spying; print clear results; under 150 lines; "
        "comments in simple English. Reply as JSON: "
        '{"name": short_snake_case_name, "about": one sentence, "code": full source}.',
        4000, json_mode=True)
    try:
        d = json.loads(raw)
        name = re.sub(r"[^a-z0-9_]", "", re.sub(r"[\s-]+", "_", d["name"].strip().lower()))[:30] or "program"
        code = d["code"]
        compile(code, name, "exec")          # make sure it is valid Python
    except Exception:
        return None, None, None, "I couldn't build a working program. Describe it more simply."
    os.makedirs(APPS_DIR, exist_ok=True)
    path = os.path.join(APPS_DIR, name + ".py")
    with open(path, "w") as f:
        f.write(code)
    return name, path, code, d.get("about", "")


def list_programs():
    if not os.path.isdir(APPS_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(APPS_DIR) if f.endswith(".py"))


def run_program(name):
    import subprocess, sys
    path = os.path.join(APPS_DIR, re.sub(r"[^a-z0-9_]", "", name.lower()) + ".py")
    if not os.path.exists(path):
        return "No program called " + name + ". Type myapps to see them."
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           timeout=30, stdin=subprocess.DEVNULL)
        out = (r.stdout + ("\n" + r.stderr if r.returncode else "")).strip()
        return (out[-2500:] or "It ran but printed nothing.")
    except subprocess.TimeoutExpired:
        return "It ran for 30 seconds without finishing, so I stopped it."
    except Exception as e:
        return f"Couldn't run it: {e}"


def open_hotspot_settings():
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    for target in ("android.settings.TETHER_SETTINGS", "android.settings.WIRELESS_SETTINGS"):
        try:
            i = Intent(target)
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            act.startActivity(i)
            return True
        except BaseException:
            continue
    return False


# ================= AI MAKER: Genius creates its own specialist AIs =================
BOTS_FILE = "genius_bots.json"

BOT_TEMPLATE = '''# {title} - an AI made by Genius (created by Ssali Muto, Uganda)
# Run: python {name}.py "your question"   (needs a free Gemini key in gemini_key.txt)
import sys, json, urllib.request, os

INSTRUCTIONS = {prompt!r}


def ask(question):
    key_path = next((p for p in ("gemini_key.txt", "../gemini_key.txt") if os.path.exists(p)), None)
    if not key_path:
        return "Put your Gemini key in gemini_key.txt first."
    key = open(key_path).read().strip()
    body = {{"systemInstruction": {{"parts": [{{"text": INSTRUCTIONS}}]}},
            "contents": [{{"role": "user", "parts": [{{"text": question}}]}}]}}
    req = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        data=json.dumps(body).encode(),
        headers={{"Content-Type": "application/json", "x-goog-api-key": key}})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    return d["candidates"][0]["content"]["parts"][0]["text"]


# ===================== 112.6 Minerals near me =====================
# Real data only: Uganda Government (DGSM) mineral records + mines and quarries mapped on OpenStreetMap.
MIN_CACHE = "minerals_cache.json"
MIN_PORTAL = "https://dgsmportal.minerals.go.ug/"
MIN_SITES = [["Kamalenge", "Kassanda", "Gold", "5 million ounces (AUC Mining lease)", 0.6749, 31.7604, 0], ["Kisita", "Kassanda", "Gold", "Kisita Mining Company, rock and alluvial gold", 0.5333, 31.7628, 1], ["Ngugo", "Kassanda", "Gold", "alluvial gold (Kisita Mining)", 0.5333, 31.7628, 1], ["Bukuya", "Kassanda", "Gold", "high-potential gold field", 0.6786, 31.8197, 0], ["Kayonza", "Kassanda", "Gold", "high-potential gold field", 0.3565, 31.6493, 0], ["Lugigi", "Kassanda", "Gold", "high-potential gold field", 0.5333, 31.7628, 1], ["Kitumbi", "Kassanda", "Gold", "gold field area", 0.7461, 31.675, 0], ["Mbale Estate", "Mubende", "Beryl, lithium, columbite-tantalite", "pegmatites, needs exploration", 0.5154, 31.4095, 1], ["Nampeyo", "Mubende", "Lithium", "pegmatite, needs exploration", 0.5154, 31.4095, 1], ["Kyasampawo", "Mubende", "Tungsten (wolfram)", "occurrence", 0.5154, 31.4095, 1], ["Kiganda", "Mubende", "Granite", "granite mining lease, cut stone", 0.4563, 31.6702, 0], ["Mubende", "Mubende", "Silver", "silver in the Mubende granite, needs exploration", 0.5154, 31.4095, 1], ["Namasera", "Wakiso", "Kaolin", "kaolin clay", 0.3761, 32.4561, 1], ["Migadde", "Wakiso", "Kaolin", "kaolin clay", 0.5247, 32.5178, 0], ["Buwambo", "Wakiso", "Kaolin", "kaolin clay", 0.5028, 32.548, 0], ["Lunya", "Mukono", "Beryl, lithium, columbite-tantalite, feldspar", "pegmatites", 0.4417, 32.9243, 0], ["Kome Island", "Buvuma", "Silica (glass) sand", "99.95% silica", 0.1953, 33.2914, 1], ["Bukakata", "Masaka", "Silica (glass) sand", "99.93% silica", -0.3054, 32.0387, 0], ["Lwera", "Kalungu", "Silica sand", "sand", -0.0913, 31.8106, 1], ["Kisai", "Rakai", "Kaolin", "1 million tonnes", -0.7264, 31.3401, 1], ["Buyaga", "Rakai", "Tungsten (wolfram)", "occurrence", -0.7264, 31.3401, 1], ["Mashonga", "Bushenyi", "Gold", "1 million ounces (Sino Minerals)", -0.3824, 30.13, 0], ["Tiira", "Busia", "Gold", "500,000 ounces (Greenstone Resources)", 0.5084, 34.0851, 0], ["Alupe", "Busia", "Gold", "30 Mt at 1.2 g/t (Wagagai mine)", 0.4768, 34.1085, 0], ["Kilembe", "Kasese", "Copper, cobalt", "old Kilembe copper mine", 0.2314, 29.9799, 0], ["Muko", "Rubanda", "Iron ore", "152 Mt at 60-65% iron", -1.2052, 29.8137, 0], ["Sukulu", "Tororo", "Phosphate, iron, niobium, rare earths", "carbonatite", 0.6593, 34.1516, 0], ["Makuutu", "Bugweri", "Rare earth elements", "world-class clay-hosted deposit", 0.5066, 33.5906, 0], ["Namekhara", "Manafwa", "Vermiculite", "world-class vermiculite mine", 0.8813, 34.2696, 1], ["Hima", "Kasese", "Limestone", "cement", 0.2922, 30.183, 0], ["Rupa", "Moroto", "Marble, gold", "marble and gold", 2.5922, 34.7631, 0], ["Kikagati", "Isingiro", "Tin", "tin mining", -1.0437, 30.6578, 0], ["Mwerasandu", "Ntungamo", "Tin, lithium", "tin", -1.0057, 30.3869, 0], ["Nyamuliro", "Kabale", "Tungsten (wolfram)", "old tungsten mine", -1.15, 29.8, 0], ["Orom", "Kitgum", "Graphite", "graphite mining lease", 3.4017, 33.4685, 0], ["Katwe", "Kasese", "Salt", "salt lake", -0.1445, 29.8846, 0], ["Kaiso", "Hoima", "Bentonite", "over 1 billion tonnes", 1.5256, 30.9683, 0], ["Kitaka", "Kamwenge", "Copper, lead, zinc, silver", "needs exploration", -0.1191, 30.3129, 0], ["Katenga", "Buhweju", "Gold", "Buhweju gold field", -0.3203, 30.3162, 1], ["Kafunzo", "Ntungamo", "Tin, nickel", "small-scale tin mining", -1.0443, 30.4382, 0]]   # [place, district, minerals, note, lat, lon, approx] from DGSM "Mineral Potential of Uganda 2024"

MIN_STEPS = """[b]Turning a find into money, the honest way[/b]
1. [b]Look, don't dig yet.[/b] Note the place, take clear photos of the rock or sand, and collect a fist-sized sample from the surface.
2. [b]Test it for real.[/b] The Government mineral laboratory (DGSM, Plot 21-29 Johnstone Road, Entebbe, tel 0414 320656) tests rocks, soil and gold for what is inside. A lab result is the only proof.
3. [b]Check who holds the land.[/b] Search the official Mining Cadastre map (dgsmportal.minerals.go.ug) to see if a company already holds a licence there.
4. [b]Get the right licence.[/b] Minerals belong to the Government. Ugandans can apply through the cadastre portal (an artisanal licence is the small one). Mining without one can lead to arrest and losing everything.
5. [b]Sell only to licensed dealers.[/b] The portal lists every Mineral Dealer's Licence.

[b]Scam alarm[/b]
- Anyone selling "gold" cheap, or asking you to pay first for "gold in a box", fake export papers or "black money" cleaning: it's a scam.
- Real gold doesn't stick to a magnet, isn't light, and is never sold by the roadside at a discount.
- Genius will never tell you there is gold under your land without a lab result."""


def _min_get(url, timeout=25, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "Genius/" + VERSION + " (Android; minerals)"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _min_km(a, b, c, d):
    import math
    r = 6371.0
    p1, p2 = math.radians(a), math.radians(c)
    dp_, dl = math.radians(c - a), math.radians(d - b)
    h = math.sin(dp_ / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _min_cache():
    try:
        return json.load(open(MIN_CACHE))
    except Exception:
        return {}


def min_geocode(place):
    c = _min_cache()
    key = place.lower().strip()
    if key in c:
        return c[key]
    q = urllib.parse.urlencode({"q": place + ", Uganda", "format": "json", "limit": 1, "countrycodes": "ug",
                                "addressdetails": 1})
    try:
        res = _min_get("https://nominatim.openstreetmap.org/search?" + q)
    except Exception as e:
        log(f"MINERALS: nominatim {type(e).__name__}")
        res = []
    if not res:
        try:
            ph = _min_get("https://photon.komoot.io/api/?" + urllib.parse.urlencode({"q": place + " Uganda", "limit": 5}))
            for f in ph.get("features", []):
                p = f.get("properties", {})
                if p.get("countrycode") == "UG":
                    lo, la = f["geometry"]["coordinates"]
                    g = {"lat": la, "lon": lo, "name": p.get("name") or place,
                         "district": (p.get("county") or p.get("state") or "").replace(" District", "")}
                    c[key] = g
                    json.dump(c, open(MIN_CACHE, "w"))
                    return g
        except Exception as e:
            log(f"MINERALS: photon {type(e).__name__}")
        return None
    a = res[0].get("address", {})
    g = {"lat": float(res[0]["lat"]), "lon": float(res[0]["lon"]),
         "name": res[0].get("display_name", place).split(",")[0],
         "district": (a.get("county") or a.get("state_district") or a.get("city") or "").replace(" District", "")}
    c[key] = g
    try:
        json.dump(c, open(MIN_CACHE, "w"))
    except Exception:
        pass
    return g


def min_osm_nearby(lat, lon, radius_m=30000):
    q = f"""[out:json][timeout:25];
(nwr["landuse"="quarry"](around:{radius_m},{lat},{lon});
 nwr["man_made"="mineshaft"](around:{radius_m},{lat},{lon});
 nwr["industrial"="mine"](around:{radius_m},{lat},{lon});
 nwr["historic"="mine"](around:{radius_m},{lat},{lon});
 nwr["resource"](around:{radius_m},{lat},{lon}););
out center tags 60;"""
    for host in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            d = _min_get(host, timeout=35, data=urllib.parse.urlencode({"data": q}).encode())
            out = []
            for e in d.get("elements", []):
                t = e.get("tags", {})
                la = e.get("lat") or e.get("center", {}).get("lat")
                lo = e.get("lon") or e.get("center", {}).get("lon")
                if la is None:
                    continue
                what = t.get("resource") or t.get("product") or t.get("mineral") or \
                    ("quarry" if t.get("landuse") == "quarry" else "mine")
                out.append({"name": t.get("name") or "", "what": what.replace(";", ", "),
                            "km": _min_km(lat, lon, la, lo)})
            out.sort(key=lambda x: x["km"])
            return out
        except Exception as e:
            log(f"MINERALS: overpass {host} {type(e).__name__}")
    return None


def minerals_report(place):
    g = min_geocode(place)
    if not g:
        return (f"I couldn't find '{place}' on the map. Try a bigger nearby town or your district, "
                "e.g. minerals Mityana.")
    lat, lon = g["lat"], g["lon"]
    near = sorted(([_min_km(lat, lon, s[4], s[5])] + s for s in MIN_SITES), key=lambda x: x[0])
    lines = [f"[b]Minerals near {g['name']}[/b]" + (f" ({g['district']})" if g.get("district") else ""),
             "", "[b]Official mineral areas (Uganda Government records)[/b]"]
    for km, p, dist, mins, note, la, lo, ap in near[:8]:
        lines.append(f"- {p}, {dist}: [b]{mins}[/b], {'about ' if ap else ''}{km:.0f} km away. {note}")
    gold = [x for x in near if "Gold" in x[3]]
    if gold:
        k = gold[0]
        lines.append(f"\nNearest recorded gold area: {k[1]} ({k[2]}), about {k[0]:.0f} km away.")
    osm = min_osm_nearby(lat, lon)
    lines.append("\n[b]Mines and quarries mapped within 30 km[/b]")
    if osm is None:
        lines.append("The map service didn't answer. Say minerals again in a minute.")
    elif not osm:
        lines.append("None mapped yet near you. Most local work here is stone, sand and clay.")
    else:
        kinds = {}
        for o in osm:
            kinds[o["what"]] = kinds.get(o["what"], 0) + 1
        lines.append(", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda x: -x[1])[:6]))
        for o in osm[:6]:
            lines.append(f"- {o['name'] or o['what'].title()}: {o['what']}, {o['km']:.1f} km")
    lines.append("\n[b]What this means[/b]\nThese are places where minerals are officially recorded or mined. "
                 "It does NOT prove minerals are under your own land. Only a lab test of a sample can say that.")
    lines.append("\n" + MIN_STEPS)
    lines.append(f"\nLicences map: {MIN_PORTAL}\nSay 'minerals <another place>' to check somewhere else.")
    return "\n".join(lines)


def minerals_handle(screen, line, action, arg, low):
    lw = low.strip(" .!?")
    trig = ("minerals near me", "mineral map", "minerals around me", "find minerals", "minerals here",
            "minerals in my area", "mineral near me")
    if action in ("minerals", "mineral", "ebyobugagga") or any(t in lw for t in trig) and len(lw.split()) <= 8:
        a = arg.strip()
        for junk in ("near me", "around me", "here", "in my area", "map"):
            if a.lower() == junk:
                a = ""
        if a.lower().startswith(("near ", "in ", "at ", "around ")):
            a = a.split(" ", 1)[1].strip()
        if a.lower() in ("steps", "how", "sell", "licence", "license", "test", "scam", "help"):
            screen.show("AI", MIN_STEPS)
            return True
        d = life_load()
        if a:
            d["my_place"] = a
            life_save(d)
        place = a or d.get("my_place")
        if not place:
            screen.say("Which village or town are you near? Type it like: minerals Mityana. "
                       "Genius saves it for next time.")
            return True
        screen._bg(lambda: minerals_report(place), f"Checking Government mineral records and maps around {place}...",
                   speak=False)
        return True
    return False
# =================== end Minerals near me ===================


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Introduce yourself in two sentences."
    print(ask(q))
'''


def bots_load():
    try:
        return json.load(open(BOTS_FILE))
    except Exception:
        return {}


def make_bot(name, purpose):
    """Design a specialist AI: Gemini writes its instructions; save it and export a .py file."""
    name = re.sub(r"[^a-z0-9_]", "", re.sub(r"[\s-]+", "_", name.strip().lower()))[:24] or "helper"
    prompt = ask_gemini(
        "Write the system instructions (under 180 words) for a specialist AI assistant. "
        f"Its job: {purpose}. It serves a young person in Uganda. Say who it is, what it "
        "does, how it answers (simple English, short, accurate, local examples), and that "
        "it admits when it is unsure. Reply with only the instructions.", 600)
    if not prompt:
        prompt = (f"You are {name}, a specialist AI. Your job: {purpose}. Answer in simple, "
                  "short, accurate English with Ugandan examples. Say when you are unsure.")
    bots = bots_load()
    bots[name] = {"purpose": purpose, "prompt": prompt.strip(), "made": time.strftime("%Y-%m-%d")}
    json.dump(bots, open(BOTS_FILE, "w"))
    os.makedirs(APPS_DIR, exist_ok=True)
    path = os.path.join(APPS_DIR, name + "_ai.py")
    open(path, "w").write(BOT_TEMPLATE.format(title=name.replace("_", " ").title(),
                                              name=name + "_ai", prompt=prompt.strip()))
    return name, path


def ask_bot(name, question):
    bot = bots_load().get(name.lower())
    if not bot:
        return None
    return ask_gemini(question, 900, system=bot["prompt"]) or "No AI could be reached after trying every way. Check your data or Wi-Fi, then send it again."


# ================= BACKUP / RESTORE =================
BACKUP_ITEMS = ("life_data.json", "notes.txt", "chat_memory.json", "about_me.txt",
                "genius_bots.json", "my_cv.txt", "ai_log.txt", "genius_apps")
# Keys and the locker are left out on purpose, so a lost backup can't leak them.


def backup_dir():
    for d in (genius_dl(),):
        try:
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, ".w")
            open(test, "w").write("1")
            os.remove(test)
            return d
        except Exception:
            continue
    os.makedirs("genius_backups", exist_ok=True)
    return os.path.abspath("genius_backups")


def make_backup():
    import zipfile
    path = os.path.join(backup_dir(), "genius_backup_" + time.strftime("%Y%m%d_%H%M") + ".zip")
    n = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in BACKUP_ITEMS:
            if os.path.isfile(item):
                z.write(item)
                n += 1
            elif os.path.isdir(item):
                for f in os.listdir(item):
                    z.write(os.path.join(item, f))
                    n += 1
    kb = os.path.getsize(path) // 1024 + 1
    return (f"Backed up {n} files ({kb} KB) to {path}. Upload it to your Google Drive "
            "to keep it safe if you lose the phone.")


def restore_backup():
    import zipfile, glob
    files = sorted(glob.glob(os.path.join(backup_dir(), "genius_backup_*.zip")))
    if not files:
        return "No backup found. Put a genius_backup zip in Download/Genius, or type backup first."
    with zipfile.ZipFile(files[-1]) as z:
        names = [n for n in z.namelist()
                 if n.split("/")[0] in BACKUP_ITEMS and ".." not in n and not n.startswith("/")]
        z.extractall(".", members=names)
    return f"Restored {len(names)} files from {os.path.basename(files[-1])}. Restart Genius to load them."



# ================= PROBLEM SOLVER =================
PROBLEMS_FILE = "problems.json"
KNOW_FILE = "knowledge.json"


def problems_load():
    try:
        return json.load(open(PROBLEMS_FILE))
    except Exception:
        return []


def problems_save(p):
    json.dump(p, open(PROBLEMS_FILE, "w"), indent=1)


def know_load():
    try:
        return json.load(open(KNOW_FILE))
    except Exception:
        return {}


def know_add(text):
    topic, sep, info = text.partition(":")
    if not sep:
        topic, info = "general", text
    k = know_load()
    k.setdefault(topic.strip().lower() or "general", []).append(info.strip())
    json.dump(k, open(KNOW_FILE, "w"), indent=1)
    return topic.strip().lower() or "general"


def know_text(limit=2500):
    k = know_load()
    lines = [f"{t}: {i}" for t, items in k.items() for i in items]
    return "\n".join(lines)[-limit:]


SOLVE_SYSTEM = ("You are Genius, a wise, kind problem-solving coach for a young person in Uganda. "
                "Be practical, honest and specific to their life and money (UGX). Never give dangerous, "
                "illegal or medical-dosage advice; for health, legal or safety problems include who to ask "
                "for real help. Reply with only valid JSON.")


def solve_problem(problem):
    ctx = ""
    if about_me():
        ctx += "About them:\n" + about_me() + "\n"
    if know_text():
        ctx += "Facts they taught you:\n" + know_text() + "\n"
    prompt = (ctx + "\nTheir problem: " + problem + "\n\nReturn JSON with keys: "
              '"title" (max 6 words), "understand" (1-2 sentences showing you understand), '
              '"causes" (list of up to 4 likely root causes), '
              '"options" (list of up to 3 objects with "option", "pros", "cons"), '
              '"best" (which option and why, 1-2 sentences), '
              '"steps" (list of 3-6 small concrete steps), '
              '"today" (one tiny step they can do in the next hour), '
              '"help" (who could help them, or empty string).')
    raw = ask_gemini(prompt, max_tokens=1200, json_mode=True, system=SOLVE_SYSTEM)
    plan = None
    try:
        t = (raw or "").strip().strip("`")
        t = t[t.find("{"):t.rfind("}") + 1]
        plan = json.loads(t)
    except Exception:
        plan = None
    if not plan or not plan.get("steps"):
        plan = {"title": problem[:40], "understand": "I couldn't reach an AI, so here is a plan you can fill in.",
                "causes": ["What started this?", "What keeps it going?"],
                "options": [{"option": "Fix it yourself", "pros": "Fast, free", "cons": "Hard alone"},
                            {"option": "Ask someone you trust", "pros": "Support, ideas", "cons": "Need to open up"}],
                "best": "Talk to one trusted person, then pick one small action.",
                "steps": ["Write the problem in one sentence", "List 3 things you could try",
                          "Pick the easiest one", "Do it and note what happened"],
                "today": "Write the problem in one sentence in your notes.", "help": ""}
    plan["problem"] = problem
    plan["done"] = []
    plan["created"] = time.strftime("%Y-%m-%d")
    p = problems_load()
    p.append(plan)
    problems_save(p)
    return len(p), plan


def plan_text(n, plan):
    out = [f"[b]Problem {n}: {plan.get('title', '')}[/b]", plan.get("understand", "")]
    if plan.get("causes"):
        out.append("\n[b]Why it's happening[/b]\n" + "\n".join("- " + c for c in plan["causes"]))
    if plan.get("options"):
        out.append("\n[b]Options[/b]")
        for o in plan["options"]:
            out.append(f"- {o.get('option')}: + {o.get('pros')} / - {o.get('cons')}")
    if plan.get("best"):
        out.append("\n[b]Best choice[/b]\n" + plan["best"])
    out.append("\n[b]Steps[/b]")
    for i, st in enumerate(plan.get("steps", []), 1):
        mark = "[x]" if i in plan.get("done", []) else "[ ]"
        out.append(f"{mark} {i}. {st}")
    if plan.get("today"):
        out.append("\n[b]Do this in the next hour[/b]\n" + plan["today"])
    if plan.get("help"):
        out.append("\n[b]Who can help[/b]\n" + plan["help"])
    out.append(f"\nTick steps with: step {n} 1")
    return "\n".join(out)


# ================= SELF-UPGRADE (safe) =================
INTEGRITY_FILE = os.path.join(ROOT, "integrity.json")


def own_file():
    try:
        return os.path.abspath(__file__)
    except Exception:
        return None


def file_sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def integrity_check():
    """Remember Genius's own fingerprint; warn if the code changed without an upgrade."""
    me = own_file()
    if not me or not os.path.exists(me):
        return "unknown"
    now = file_sha(me)
    try:
        saved = json.load(open(INTEGRITY_FILE))
    except Exception:
        saved = {}
    if not saved.get("sha"):
        json.dump({"sha": now, "version": VERSION}, open(INTEGRITY_FILE, "w"))
        return "ok"
    if saved["sha"] == now:
        return "ok"
    if saved.get("version") != VERSION:   # a new APK version was installed

        json.dump({"sha": now, "version": VERSION}, open(INTEGRITY_FILE, "w"))
        return "ok"
    intruder_log("code changed outside upgrade", now[:12])
    return "changed"


def integrity_accept():
    me = own_file()
    if me and os.path.exists(me):
        json.dump({"sha": file_sha(me), "version": VERSION}, open(INTEGRITY_FILE, "w"))


def find_update():
    d = os.path.join(backup_dir(), "update")
    os.makedirs(d, exist_ok=True)
    code = os.path.join(d, "genius_update.py")
    sha = os.path.join(d, "genius_update.sha256")
    if not os.path.exists(code):
        return None, (f"No update found. Put genius_update.py and genius_update.sha256 in {d}, "
                      "then type upgrade.")
    if not os.path.exists(sha):
        return None, "The update has no genius_update.sha256 fingerprint, so I won't install it."
    want = open(sha).read().split()[0].strip().lower() if open(sha).read().strip() else ""
    got = file_sha(code)
    if not want or want != got:
        intruder_log("upgrade rejected: fingerprint mismatch", got[:12])
        return None, "Blocked: the update's fingerprint doesn't match. It may have been changed by someone."
    src = open(code, encoding="utf-8").read()
    try:
        compile(src, "genius_update.py", "exec")
    except SyntaxError as e:
        return None, f"Blocked: the update has an error on line {e.lineno}, so I kept this version."
    if "class GeniusApp" not in src or "def check_login" not in src:
        return None, "Blocked: that file doesn't look like Genius (no login firewall inside)."
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', src)
    return {"path": code, "sha": got, "version": m.group(1) if m else "?"}, ""


def apply_update(upd):
    me = own_file()
    if not me or not os.access(me, os.W_OK):
        return ("This copy of Genius is an installed app, so its code can't be replaced from inside. "
                "Install the new Genius APK instead; your data stays.")
    import shutil
    shutil.copy2(me, os.path.join(os.path.dirname(me), "genius_previous.py"))
    shutil.copy2(upd["path"], me)
    json.dump({"sha": file_sha(me), "version": upd["version"], "pending": file_sha(me)},
              open(INTEGRITY_FILE, "w"))
    log(f"UPGRADE to {upd['version']}")
    return f"Upgraded to Genius {upd['version']}. Old version saved for rollback. Restart Genius to use it."


def rollback():
    me = own_file()
    if not me:
        return "I can't find my own file."
    prev = os.path.join(os.path.dirname(me), "genius_previous.py")
    if not os.path.exists(prev):
        return "There's no previous version saved."
    if not os.access(me, os.W_OK):
        return "This is an installed app; reinstall the older APK to go back."
    import shutil
    shutil.copy2(prev, me)
    json.dump({"sha": file_sha(me), "version": "previous", "pending": file_sha(me)},
              open(INTEGRITY_FILE, "w"))
    log("ROLLBACK")
    return "Rolled back to the previous version. Restart Genius."


# ================= DISTRACTION FIREWALL: decoy + tripwires =================
TRIPWIRE_FILE = os.path.join(ROOT, "tripwires.json")
DECOY_NOTES = ["2026-10-01 | buy exercise books", "2026-10-03 | football practice Saturday",
               "2026-10-08 | return library book", "2026-10-12 | call grandma"]


def tripwires():
    try:
        t = json.load(open(TRIPWIRE_FILE))
    except Exception:
        t = {}
    if not t:
        t = {"bank_pin": str(random.randint(1000, 9999)),
             "momo_pin": str(random.randint(10000, 99999)),
             "email_password": "Sunrise" + str(random.randint(100, 999)) + "!"}
        json.dump(t, open(TRIPWIRE_FILE, "w"))
    return t


def tripwire_add(label):
    t = tripwires()
    t[label.lower()] = "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(8))
    json.dump(t, open(TRIPWIRE_FILE, "w"))


def security_report():
    st = load_state()
    ev = intruder_data()["events"]
    trips = [e for e in ev if e["e"].startswith("TRIPWIRE")]
    locked = st.get("locked_until", 0) > time.time()
    lines = ["[b]Genius security[/b]",
             "Login firewall: ON (owner name + password + this phone only)",
             f"Lockouts: escalate 5 min > 15 min > 1 hour. Locked now: {'yes' if locked else 'no'}",
             "Distraction firewall: ON. Intruders get a fake decoy Genius with fake data and slow replies",
             f"Tripwires (fake secrets in the decoy): {', '.join(tripwires().keys())}",
             f"Break-in events logged: {len(ev)}. Tripwires touched: {len(trips)}",
             f"Code tamper check: {integrity_check()}",
             "Keys and locker: stay on this phone, left out of backups",
             "Watcher: blocks copying itself, deleting files and disabling stop",
             "\nNote: this guards Genius on your phone. Keep Android updated and use a screen lock too."]
    return "\n".join(lines)


# ================= MANY AIs: Groq (very fast) + OpenRouter (many models) =================
GROQ_KEY_FILE = os.path.join(ROOT, "groq_key.txt")
ROUTER_KEY_FILE = os.path.join(ROOT, "openrouter_key.txt")
PROVIDERS = {
    "groq": {"file": GROQ_KEY_FILE, "base": "https://api.groq.com/openai/v1",
             "prefer": ("gpt-oss-120b", "llama-3.3-70b", "llama-4", "qwen", "gpt-oss", "llama", "gemma")},
    "openrouter": {"file": ROUTER_KEY_FILE, "base": "https://openrouter.ai/api/v1",
                   "prefer": (":free",)},
    "cerebras": {"file": os.path.join(ROOT, "cerebras_key.txt"), "base": "https://api.cerebras.ai/v1",
                 "prefer": ("gpt-oss-120b", "llama-3.3-70b", "qwen-3", "llama")},
    "mistral": {"file": os.path.join(ROOT, "mistral_key.txt"), "base": "https://api.mistral.ai/v1",
                "prefer": ("mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "mistral")},
    "sambanova": {"file": os.path.join(ROOT, "sambanova_key.txt"), "base": "https://api.sambanova.ai/v1",
                  "prefer": ("llama-4-maverick", "deepseek-v3", "meta-llama-3.3-70b", "llama")},
}
AI_NAMES = {"groq": "Groq", "openrouter": "OpenRouter", "cerebras": "Cerebras", "mistral": "Mistral",
            "sambanova": "SambaNova", "gemini": "Gemini"}

# ---- 111.5 smart AI picker: Genius learns which AI is fastest and most reliable on THIS phone ----
AI_STATS_FILE = os.path.join(ROOT, "ai_stats.json")
_AI_STATS = {}
_AI_STATS_LOCK = threading.Lock()


def _ai_stats():
    global _AI_STATS
    if not _AI_STATS:
        try:
            _AI_STATS = json.load(open(AI_STATS_FILE))
        except Exception:
            _AI_STATS = {}
    return _AI_STATS


def ai_record(name, ok, secs=0.0, liked=None):
    """Remember how an AI did: success, speed, and the user's thumbs up/down."""
    with _AI_STATS_LOCK:
        st = _ai_stats().setdefault(name, {"ok": 0, "fail": 0, "avg": 3.0, "up": 0, "down": 0})
        if liked is True:
            st["up"] += 1
        elif liked is False:
            st["down"] += 1
        elif ok:
            st["ok"] += 1
            st["avg"] = round(st["avg"] * 0.8 + float(secs) * 0.2, 2)
        else:
            st["fail"] += 1
        try:
            json.dump(_AI_STATS, open(AI_STATS_FILE, "w"))
        except Exception:
            pass


def ai_score(name):
    st = _ai_stats().get(name, {"ok": 0, "fail": 0, "avg": 3.0, "up": 0, "down": 0})
    tries = st["ok"] + st["fail"]
    reliab = (st["ok"] + 2) / (tries + 3.0)                     # starts near 0.67, learns fast
    likes = (st["up"] + 1) / (st["up"] + st["down"] + 2.0)
    speed = 1.0 / (1.0 + max(0.2, st["avg"]) / 3.0)
    return reliab * 0.5 + likes * 0.3 + speed * 0.2


def ranked_providers():
    """Connected chat AIs (not Gemini), best first."""
    have = [n for n in PROVIDERS if provider_key(n)]
    base = list(PROVIDERS)
    return sorted(have, key=lambda n: (-ai_score(n), base.index(n)))


# ---- 111.5 help improve Genius: opt-in, anonymous reports to the developer ----
REPORT_TOPIC = "genius-dev-4b6b6740e6de68e5"          # read by the developer at ntfy.sh/<topic>
REPORT_OPT_FILE = os.path.join(ROOT, "help_improve.json")


def reports_opt():
    try:
        return json.load(open(REPORT_OPT_FILE))
    except Exception:
        return {"on": None, "last": 0}


def reports_set(on):
    d = reports_opt()
    d["on"] = bool(on)
    json.dump(d, open(REPORT_OPT_FILE, "w"))


def send_report(title, body):
    """Send a short, anonymous note to the developer. Only when the person turned 'Help improve Genius' on."""
    if not reports_opt().get("on"):
        return False

    def go():
        try:
            data = (f"Genius {VERSION}\n" + body)[:3500].encode("utf-8")
            req = urllib.request.Request("https://ntfy.sh/" + REPORT_TOPIC, data=data,
                                         headers={"Title": title[:80].encode("ascii", "ignore").decode() or "Genius",
                                                  "Tags": "genius"})
            urllib.request.urlopen(req, timeout=15, context=ssl_context()).read(200)
        except Exception as e:
            log(f"REPORT send: {type(e).__name__}")
    threading.Thread(target=go, daemon=True).start()
    return True


def problem_summary(hours=24):
    """Which parts of Genius had trouble lately: only part names and error types, never what anyone typed."""
    since = time.time() - hours * 3600
    counts = {}
    try:
        for line in open(LOG_FILE, errors="ignore").readlines()[-4000:]:
            try:
                ts, ev = line.split(" | ", 1)
                if time.mktime(time.strptime(ts.strip(), "%Y-%m-%d %H:%M:%S")) < since:
                    continue
            except Exception:
                continue
            if not re.search(r"fail|error|exception|couldn", ev, re.I):
                continue
            part = re.sub(r"[^A-Za-z ]", " ", ev.split(":", 1)[0])
            part = " ".join(part.split()[:3])[:30] or "unknown"
            err = re.search(r"\b([A-Z][A-Za-z]+(?:Error|Exception))\b", ev)
            k = part + (" / " + err.group(1) if err else "")
            counts[k] = counts.get(k, 0) + 1
    except Exception:
        pass
    return sorted(counts.items(), key=lambda x: -x[1])[:25]


def daily_problem_report():
    d = reports_opt()
    if not d.get("on") or time.time() - d.get("last", 0) < 86400:
        return
    probs = problem_summary()
    d["last"] = time.time()
    json.dump(d, open(REPORT_OPT_FILE, "w"))
    if probs:
        model = ""
        try:
            from jnius import autoclass
            B = autoclass("android.os.Build")
            model = f"{B.MANUFACTURER} {B.MODEL}, Android {android_sdk()}"
        except Exception:
            pass
        ais = ", ".join(f"{AI_NAMES.get(n, n)} {ai_score(n) * 100:.0f}" for n in connected_ais() if n != "gemini")
        send_report("Daily problems", f"{model}\nAI scores: {ais or 'none'}\n" +
                    "\n".join(f"{n}x {k}" for k, n in probs))


def ai_report():
    rows = []
    for n in ["gemini"] + list(PROVIDERS):
        if n not in connected_ais():
            continue
        st = _ai_stats().get(n, {})
        rows.append(f"{AI_NAMES.get(n, n)}: score {ai_score(n) * 100:.0f}, {st.get('ok', 0)} good, "
                    f"{st.get('fail', 0)} failed, about {st.get('avg', 0):.1f}s, "
                    f"{st.get('up', 0)} likes, {st.get('down', 0)} dislikes")
    return rows
_model_cache = {}
_answer_cache = {}


def provider_key(name):
    f = PROVIDERS[name]["file"]
    try:
        k = clean_key(open(f).read()) if os.path.exists(f) else None
    except Exception:
        return None
    return k or None


def _http_json(url, key, body=None, timeout=30):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + key})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as r:
        return json.load(r)


def pick_model(name, key):
    """Ask the provider which models exist today, so old model names never break Genius."""
    if name in _model_cache:
        return _model_cache[name]
    ids = [m["id"] for m in _http_json(PROVIDERS[name]["base"] + "/models", key, timeout=20)["data"]]
    ids = [i for i in ids if not any(x in i.lower() for x in ("whisper", "tts", "guard", "embed", "vision", "orpheus", "allam", "safeguard"))]
    for want in PROVIDERS[name]["prefer"]:
        for i in ids:
            if want in i.lower():
                _model_cache[name] = i
                return i
    _model_cache[name] = ids[0]
    return ids[0]


# ---------------- 110.5 fast lane: streamed Groq answers on a kept-open connection ----------------
_GROQ_CONN = {}
_GROQ_IDS = []
_SLOW_WORDS = re.compile(r"\b(explain|essay|write|story|poem|code|program|solve|calculate|compare|analy[sz]e|"
                         r"describe|discuss|plan|letter|summar|why|how does|how do|step)\w*", re.I)


def _groq_conn(fresh=False):
    import http.client
    c = _GROQ_CONN.get("c")
    if fresh and c is not None:
        try:
            c.close()
        except Exception:
            pass
        c = None
    if c is None:
        c = http.client.HTTPSConnection("api.groq.com", timeout=20, context=ssl_context())
        _GROQ_CONN["c"] = c
    return c


def groq_warmup():
    """Open the secure line to Groq and learn its models before the first question (saves a second or two)."""
    key = provider_key("groq")
    if not key:
        return
    try:
        if not _GROQ_IDS:
            _GROQ_IDS.extend(m["id"] for m in _http_json(PROVIDERS["groq"]["base"] + "/models", key, timeout=15)["data"])
        pick_model("groq", key)
        _groq_conn().connect()
    except Exception as e:
        log(f"GROQ warmup: {type(e).__name__}")


def fast_model(text, key):
    """Short everyday questions go to the quickest model; bigger jobs to the smartest fast one."""
    if len(text.split()) <= 14 and not _SLOW_WORDS.search(text):
        for want in ("llama-3.1-8b-instant", "llama-3.3-70b-versatile"):
            if want in _GROQ_IDS:
                return want
    return pick_model("groq", key)


def groq_stream(text, convo=None, on_text=None, max_tokens=700):
    """Ask Groq and hand back the words while they arrive, so the answer starts showing in under a second."""
    key = provider_key("groq")
    if not key:
        return None
    msgs = [{"role": "system", "content":
             "You are Genius, the private assistant of " + CURRENT["name"] + ", a young person in Uganda, made by "
             "Ssali Muto. Answer in clear, simple English, briefly and accurately. Say when you are "
             "unsure. You can't see the time, weather or internet in this mode." + ANSWER_STYLE + brain_recall(text)}]
    for m in (convo or [])[-8:]:
        t = " ".join(p.get("text", "") for p in m.get("parts", []))
        if t:
            msgs.append({"role": "assistant" if m["role"] == "model" else "user", "content": t})
    msgs.append({"role": "user", "content": text})
    try:
        model = fast_model(text, key)
    except Exception as e:
        log(f"GROQ model: {type(e).__name__}")
        return None
    body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.6, "stream": True}
    if "gpt-oss" in model:
        body.update(reasoning_effort="low", include_reasoning=False)
    data = json.dumps(body)
    out = []
    for attempt in range(2):
        try:
            c = _groq_conn(fresh=attempt > 0)
            c.request("POST", "/openai/v1/chat/completions", data,
                      {"Content-Type": "application/json", "Authorization": "Bearer " + key})
            r = c.getresponse()
            if r.status != 200:
                detail = r.read()[:200]
                log(f"GROQ stream HTTP {r.status}: {detail!r}")
                if r.status in (400, 404):
                    _model_cache.pop("groq", None)
                    if model in _GROQ_IDS and attempt == 0:
                        _GROQ_IDS.remove(model)
                        body["model"] = model = pick_model("groq", key)
                        body.pop("reasoning_effort", None), body.pop("include_reasoning", None)
                        data = json.dumps(body)
                        continue
                return None
            while True:
                line = r.readline()
                if not line:
                    break
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                d = line[5:].strip()
                if d == b"[DONE]":
                    break
                try:
                    piece = json.loads(d)["choices"][0]["delta"].get("content") or ""
                except Exception:
                    continue
                if piece:
                    out.append(piece)
                    if on_text:
                        on_text("".join(out))
            try:
                r.read()            # finish cleanly so the same line can be reused next time
            except Exception:
                _GROQ_CONN.pop("c", None)
            return "".join(out).strip() or None
        except Exception as e:
            log(f"GROQ stream: {type(e).__name__}: {e}")
            _GROQ_CONN.pop("c", None)
            if out:
                return "".join(out).strip()
            if _is_net_error(e) and attempt:
                return None
    return None


LAST_AI = {"name": None}


def other_ai(name, text, system=None, convo=None, max_tokens=700):
    """Ask Groq or OpenRouter. Returns text or None."""
    key = provider_key(name)
    if not key:
        return None
    msgs = [{"role": "system", "content": system or (
        "You are Genius, the private assistant of " + CURRENT["name"] + ", a young person in Uganda, made by "
        "Ssali Muto. Answer in clear, simple English, briefly and accurately. Say when you are "
        "unsure. You can't see the time, weather or internet in this mode." + ANSWER_STYLE + brain_recall(text))}]
    for m in (convo or [])[-8:]:
        t = " ".join(p.get("text", "") for p in m.get("parts", []))
        if t:
            msgs.append({"role": "assistant" if m["role"] == "model" else "user", "content": t})
    msgs.append({"role": "user", "content": text})
    for attempt in range(2):
        try:
            model = pick_model(name, key)
            t0 = time.time()
            body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": 0.6}
            if "gpt-oss" in model:            # thinking models: keep the thinking short so the answer fits
                body["reasoning_effort"] = "low"
                body["max_tokens"] = max_tokens + 1200
            d = _http_json(PROVIDERS[name]["base"] + "/chat/completions", key, body, timeout=45)
            out = (d["choices"][0]["message"].get("content") or "").strip()
            if not out:
                raise ValueError("empty answer")
            ai_record(name, bool(out), time.time() - t0)
            LAST_AI["name"] = name
            return out
        except Exception as e:
            log(f"{name} failed: {e}")
            if not _is_net_error(e):
                ai_record(name, False)
            if _is_net_error(e):
                break                          # no internet: retrying only wastes time
            _model_cache.pop(name, None)       # maybe the model was retired; re-pick once
    return None


NO_AI_MSG = ("I need an AI key to answer that. Type key and I'll walk you through getting a free one "
             "in about 2 minutes (or type setgroq / setkey if you already have one). "
             "Offline I can still do notes, calc, money, quiz, music, effects and more: type help.")
NET_AI_MSG = ("I couldn't reach any AI just now. Check your internet or move to better signal, "
              "then ask again.")


# ================= Key wizard: anyone can get and save a free AI key by themselves =================
KEY_WIZARD = (
    ("groq", {"name": "Groq", "tag": "Free and the fastest. Best first choice.",
              "url": "https://console.groq.com/keys", "starts": ("gsk_",), "file": GROQ_KEY_FILE,
              "steps": ("Tap 'Open the key page' below.",
                        "Sign in with your Google account (or email).",
                        "Tap 'Create API Key'. Type any name, like Genius, then tap Submit.",
                        "Tap 'Copy' next to the new key. It starts with gsk_",
                        "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
    ("gemini", {"name": "Google Gemini", "tag": "Free. Needed to change pictures (Nano Banana) and read photos.",
                "url": "https://aistudio.google.com/apikey", "starts": ("AIza", "AQ."), "file": KEY_FILE,
                "steps": ("Tap 'Open the key page' below.",
                          "Sign in with your Google account and accept the terms if asked.",
                          "Tap 'Create API key' (choose any project if it asks).",
                          "Tap 'Copy' next to the new key. It starts with AIza",
                          "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
    ("openrouter", {"name": "OpenRouter", "tag": "Many AIs with one key, including some free ones.",
                    "url": "https://openrouter.ai/keys", "starts": ("sk-or-",), "file": ROUTER_KEY_FILE,
                    "steps": ("Tap 'Open the key page' below.",
                              "Sign in with Google.",
                              "Tap 'Create API Key', give it any name, then tap Create.",
                              "Tap 'Copy'. The key starts with sk-or- and is shown only once.",
                              "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
    ("cerebras", {"name": "Cerebras", "tag": "Free and super fast. Great backup.",
                  "url": "https://cloud.cerebras.ai", "starts": ("csk-",), "file": PROVIDERS["cerebras"]["file"],
                  "steps": ("Tap 'Open the key page' below.",
                            "Sign up or sign in with Google.",
                            "Open 'API Keys' on the left, then tap 'Generate API key'.",
                            "Copy the key. It starts with csk-",
                            "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
    ("mistral", {"name": "Mistral", "tag": "Free plan. Strong at writing and languages.",
                 "url": "https://console.mistral.ai/api-keys", "starts": ("",), "file": PROVIDERS["mistral"]["file"],
                 "steps": ("Tap 'Open the key page' below.",
                           "Sign in with Google, and choose the free 'Experiment' plan if asked.",
                           "Tap 'Create new key', give it any name, then Create.",
                           "Copy the key (it's shown only once).",
                           "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
    ("sambanova", {"name": "SambaNova", "tag": "Free. Big open AIs like Llama and DeepSeek.",
                   "url": "https://cloud.sambanova.ai/apis", "starts": ("",), "file": PROVIDERS["sambanova"]["file"],
                   "steps": ("Tap 'Open the key page' below.",
                             "Sign in with Google.",
                             "Tap 'Generate new API key' and give it any name.",
                             "Copy the key.",
                             "Come back to Genius and tap 'Paste', then 'Test and save'.")}),
)
KEY_WIZARD_INFO = dict(KEY_WIZARD)
KEY_WIZARD_WORDS = ("key", "setup", "getkey", "apikey", "ekisumuluzo")
_KEY_PATTERNS = {"groq": r"gsk_[A-Za-z0-9]{20,}", "openrouter": r"sk-or-[A-Za-z0-9_\-]{20,}",
                 "cerebras": r"csk-[A-Za-z0-9]{20,}", "mistral": r"[A-Za-z0-9]{32}",
                 "sambanova": r"[A-Za-z0-9\-]{30,}",
                 "gemini": r"AIza[A-Za-z0-9_\-]{20,}|AQ\.[A-Za-z0-9_\-]{20,}"}


def key_tail(key):
    """Only ever show the last 4 characters of a key."""
    return (key or "")[-4:]


def wizard_clean_key(prov, text):
    """Pull the key out of whatever was pasted (spaces, quotes, a whole sentence)."""
    text = (text or "").strip()
    m = re.search(_KEY_PATTERNS.get(prov, r"\S+"), text)
    return m.group(0) if m else text.strip().strip("'\"")


def key_format_check(prov, key):
    """(ok, friendly_message). A quick check before any internet is used."""
    info = KEY_WIZARD_INFO.get(prov)
    if not info:
        return False, "Pick an AI first."
    if not key:
        return False, "The box is empty. Copy your key on the website, then tap Paste."
    if info["starts"] == ("",):
        for other, oi in KEY_WIZARD:
            if other != prov and oi["starts"] != ("",) and key.startswith(oi["starts"]):
                return False, (f"That looks like a {oi['name']} key, not a {info['name']} key. "
                               f"Go back and pick {oi['name']}.")
    elif not key.startswith(info["starts"]):
        for other, oi in KEY_WIZARD:
            if other != prov and oi["starts"] != ("",) and key.startswith(oi["starts"]):
                return False, (f"That looks like a {oi['name']} key, not a {info['name']} key. "
                               f"Go back and pick {oi['name']}.")
        return False, (f"That doesn't look like a {info['name']} key. It should start with "
                       f"{info['starts'][0]}. Copy the key itself, not the page address.")
    if len(key) < 24 or re.search(r"\s", key):
        return False, "That key looks cut short. Copy the whole key again and paste it."
    return True, ""


def key_test_request(prov, key):
    """The tiny real request that proves a key works (never sent anywhere else)."""
    if prov == "groq":
        return urllib.request.Request("https://api.groq.com/openai/v1/models",
                                      headers={"Authorization": "Bearer " + key})
    if prov == "gemini":
        return urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?key="
                                      + urllib.parse.quote(key, safe=""))
    if prov in ("cerebras", "mistral", "sambanova"):
        return urllib.request.Request(PROVIDERS[prov]["base"] + "/models",
                                      headers={"Authorization": "Bearer " + key})
    return urllib.request.Request("https://openrouter.ai/api/v1/auth/key",
                                  headers={"Authorization": "Bearer " + key})


def test_ai_key(prov, key, timeout=12, opener=None):
    """(ok, friendly_message). Runs off the UI thread; never logs or returns the key."""
    ok, why = key_format_check(prov, key)
    if not ok:
        return False, why
    name = KEY_WIZARD_INFO[prov]["name"]
    try:
        req = key_test_request(prov, key)
        if opener:
            r = opener(req, timeout)
        else:
            r = urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
        with r:
            r.read(2048)
        return True, f"Key works! Ending in {key_tail(key)}."
    except urllib.error.HTTPError as e:
        code = e.code
        log(f"KEY WIZARD: {prov} test said HTTP {code}")
        if code == 429:
            return True, f"Key works (it's busy right now, so wait a minute). Ending in {key_tail(key)}."
        if code in (400, 401, 403):
            return False, (f"{name} says this key is wrong, expired or deleted. "
                           "Make a new key on the key page, copy it, and try again.")
        if code >= 500:
            return False, f"{name} is having trouble right now. Wait a few minutes and try again."
        return False, f"{name} didn't accept the key (error {code}). Make a new key and try again."
    except Exception as e:
        log(f"KEY WIZARD: {prov} test failed: {type(e).__name__}")
        if _is_net_error(e):
            return False, ("I couldn't reach the internet. Turn on data or Wi-Fi, "
                           "move to better signal, then tap Try again.")
        return False, "Something went wrong while checking the key. Tap Try again."


def save_ai_key(prov, key):
    """Write a tested key to the right file, so every part of Genius uses it at once."""
    path = KEY_WIZARD_INFO[prov]["file"]
    with open(path, "w") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    _model_cache.pop(prov, None)
    log(f"KEY WIZARD: saved a {prov} key ending in {key_tail(key)}")
    return path


def _needs_key_text(text):
    """True when a message is telling the user an AI key is missing."""
    t = text.lower()
    return ("ai key" in t or "gemini key" in t) and ("type key" in t or "setkey" in t or "need" in t) \
        and "key saved" not in t and "key works" not in t


def connected_ais():
    out = []
    if os.path.exists(KEY_FILE):
        out.append("gemini")
    out += [n for n in PROVIDERS if provider_key(n)]
    return out


TOOL_WORDS = ("weather", "remind", "note", "time", "date", "battery", "draw", "picture",
              "search", "news", "today", "latest", "price", "spent", "money", "exam", "study",
              "remember", "calculate", "rain", "who won", "current", "now")


_TOOL_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in TOOL_WORDS) + r")\b")


def needs_tools(text):
    """Whole words only: 'know' is not 'now', 'update' is not 'date', so normal questions take the fast lane."""
    return bool(_TOOL_RE.search(text.lower()))


def ask_all(question):
    """Ask every connected AI at the same time and return all answers."""
    have = connected_ais()
    jobs = {"Gemini": lambda: _ask_gemini_only(question, 500)} if "gemini" in have else {}
    for n in ranked_providers():
        jobs[AI_NAMES.get(n, n)] = (lambda n=n: other_ai(n, question, max_tokens=500))
    results = {}

    def run(k, fn):
        t0 = time.time()
        try:
            r = fn()
        except Exception:
            r = None
        results[k] = (r or "No answer.", time.time() - t0)
    th = [threading.Thread(target=run, args=(k, f), daemon=True) for k, f in jobs.items()]
    for t in th:
        t.start()
    for t in th:
        t.join(70)
    if not results:
        return NO_AI_MSG
    return "\n\n".join(f"[b]{k}[/b] ({sec:.1f}s)\n{r}" for k, (r, sec) in
                       sorted(results.items(), key=lambda x: x[1][1]))


_FAST_CACHE = {}


def fast_answer(question):
    """Race every connected AI at once and return the FIRST good answer (Groq usually wins in under a second)."""
    key = question.strip().lower()
    hit = _FAST_CACHE.get(key)
    if hit and time.time() - hit[1] < 1800:
        return hit[0] + "\n[size=11sp][color=9aa0c0]instant (remembered)[/color][/size]"
    import queue
    q = queue.Queue()
    have = connected_ais()
    jobs = {n: (lambda n=n: other_ai(n, question, max_tokens=400)) for n in ranked_providers()[:3]}
    if "gemini" in have:
        jobs["gemini"] = lambda: _ask_gemini_only(question, 400)
    if not jobs:
        return NO_AI_MSG
    t0 = time.time()

    def run(k, fn):
        try:
            r = fn()
        except Exception:
            r = None
        q.put((k, r))
    for k, fn in jobs.items():
        threading.Thread(target=run, args=(k, fn), daemon=True).start()
    for _ in jobs:
        try:
            k, r = q.get(timeout=40)
        except Exception:
            break
        if r and len(r.strip()) > 1:
            _FAST_CACHE[key] = (r.strip(), time.time())
            if len(_FAST_CACHE) > 200:
                _FAST_CACHE.pop(next(iter(_FAST_CACHE)))
            return r.strip() + f"\n[size=11sp][color=9aa0c0]{time.time() - t0:.1f}s[/color][/size]"
    return rescue_answer(question, max_tokens=400) or NET_AI_MSG


PIC_ASK = re.compile(r"\b(draw|paint|sketch)\b|\b(create|make|generate|give|show|design)\b.{0,40}"
                     r"\b(picture|pictures|photo|photos|image|images|pic|pics|portrait|selfie|drawing)\b", re.I)


def _ok(t):
    return t if t and not t.startswith(("Search failed", "Something went wrong")) else None


def genius_mind(question):
    """Genius Mind: plan, ask every AI, cross-check with live web search, critique, then one best answer."""
    if not connected_ais():
        return NO_AI_MSG
    plan = ask_gemini("Break this question into the key sub-questions and facts needed. Short list only."
                      + brain_recall(question) + "\n\n" + question,
                      300) or ""
    views = ask_all(question + "\n\nThink step by step. Key points only.")
    draft = _ok(ask_gemini(f"Question: {question}\n\nPlan:\n{plan}\n\nAnswers from several AIs:\n{views}\n\n"
                       "Combine the best reasoning, check facts with web search, fix mistakes, and write the best answer.",
                       1200, search=True)) or _ok(ask_gemini(f"Question: {question}\n\nAnswers from several AIs:\n"
                       f"{views}\n\nCombine the best reasoning and write the best answer.", 1200)) or views
    final = _ok(ask_gemini(f"Question: {question}\n\nDraft answer:\n{draft}\n\nAct as a strict expert reviewer. Find any "
                       "error, missing step, weak logic or outdated fact, then rewrite the final answer: correct, clear, "
                       "practical, with a short 'Confidence:' line (high/medium/low) and what to verify.", 1200, search=True))
    out = final or draft
    if not _ok(out):
        return "Genius Mind couldn't reach the AIs just now. Check your internet and ask again in a minute."
    return "Genius Mind\n" + out




# ================= Genius Agent, Skills and nightly self-review =================
SKILLBOOK_FILE = "genius_skillbook.json"


def _ai_text(prompt, tokens=900, search=False):
    r = None
    try:
        r = ask_gemini(prompt, tokens, search=search)
    except Exception as e:
        log(f"agent gemini failed: {e}")
    if not r:
        for prov in ranked_providers():
            r = other_ai(prov, prompt, max_tokens=tokens)
            if r:
                break
    return r or ""


def genius_agent(task, steps=None):
    """Plans a job, does each step (with web search), checks itself, and saves the result."""
    if not connected_ais():
        return NO_AI_MSG
    if not steps:
        raw = _ai_text("Plan this job as 3 to 6 short, concrete steps an assistant can do with thinking and "
                       "web search only (no payments, no sending messages). Reply ONLY a JSON list of strings.\n\n"
                       "Job: " + task, 300)
        try:
            steps = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
        except Exception:
            steps = [l.strip(" -*0123456789.") for l in raw.splitlines() if l.strip()][:6]
    steps = [str(x) for x in steps if str(x).strip()][:6] or [task]
    notes = []
    for i, st in enumerate(steps, 1):
        done = "\n".join(f"Step {j}: {n[:700]}" for j, n in enumerate(notes, 1))
        out = _ai_text(f"Overall job: {task}\nResults so far:\n{done or 'none'}\n\nNow do step {i}: {st}\n"
                       "Give the actual result (facts, numbers, text), not advice about how to do it.", 900, search=True)
        if not out and not notes:
            return NET_AI_MSG                 # first step got nothing: the AIs are unreachable
        notes.append(out or "(no result)")
    body = "\n\n".join(f"Step {i}: {st}\n{n}" for i, (st, n) in enumerate(zip(steps, notes), 1))
    final = _ai_text(f"Job: {task}\n\nWork done:\n{body[:7000]}\n\nAs a strict reviewer, fix any mistakes and write "
                     "the finished result for the owner: clear, complete, practical. End with 'Confidence:' "
                     "(high/medium/low).", 1500, search=True) or body
    saved = ""
    try:
        name = "job_" + re.sub(r"\W+", "_", task.lower())[:40].strip("_") + ".txt"
        with open(os.path.join(storage_dir(), name), "w") as f:
            f.write(f"Job: {task}\n\n{final}\n\n--- Steps ---\n{body}")
        saved = f"\n\n(Saved to your storage as {name})"
    except Exception as e:
        log(f"agent save failed: {e}")
    brain_add(f"For jobs like '{task[:100]}', these steps worked: " + "; ".join(steps)[:280], q=task)
    plan = "\n".join(f"{i}. {st}" for i, st in enumerate(steps, 1))
    return f"Genius Agent finished\nPlan:\n{plan}\n\n{final}{saved}"


def skillbook_load():
    try:
        return json.load(open(SKILLBOOK_FILE))
    except Exception:
        return {}


def skillbook_save(d):
    json.dump(d, open(SKILLBOOK_FILE, "w"))


def brain_self_review(force=False):
    """Once a day Genius studies its lessons, merges repeats, drops weak ones and sharpens the rest."""
    stamp = "genius_brain_review.txt"
    try:
        last = float(open(stamp).read())
    except Exception:
        last = 0
    if not force and time.time() - last < 20 * 3600:
        return None
    items = brain_load()
    keep = [it for it in items if it.get("kind") == "correction"]
    rest = [it for it in items if it.get("kind") != "correction"]
    open(stamp, "w").write(str(time.time()))
    if len(rest) < 6:
        return f"Self-review done. {len(items)} lessons, nothing to merge yet."
    listing = "\n".join("- " + it["lesson"] for it in rest[:80])
    raw = _ai_text("These are lessons an assistant wrote for itself. Merge duplicates, delete wrong or useless ones, "
                   "and sharpen the rest so each is a clear, accurate, reusable rule under 30 words. "
                   "Reply ONLY a JSON list of strings.\n\n" + listing, 1500)
    try:
        better = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
    except Exception:
        return "Self-review skipped: the AI didn't reply clearly."
    new = keep + [{"lesson": str(b)[:400], "q": "", "score": 2, "kind": "lesson", "t": time.time()}
                  for b in better if str(b).strip()]
    brain_save(new)
    return f"Self-review done. {len(rest)} lessons became {len(better)} sharper ones; {len(keep)} corrections kept."


# ================= ATTACH: the + button (pictures and files) =================
TEXT_EXTS = (".txt", ".md", ".py", ".json", ".csv", ".html", ".htm", ".xml", ".log", ".kv", ".spec", ".yml", ".yaml")
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic")


def attach_dir():
    return genius_dl("attached")


STORAGE_LIMIT_MB = 200


def storage_dir():
    return genius_dl("storage")


def storage_files():
    d = storage_dir()
    out = []
    for n in os.listdir(d):
        f = os.path.join(d, n)
        if os.path.isfile(f) and not n.startswith("."):
            out.append(f)
    return sorted(out, key=os.path.getmtime, reverse=True)


def storage_used():
    return sum(os.path.getsize(f) for f in storage_files())


def nice_size(b):
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024 or unit == "GB":
            return (f"{b:.0f} {unit}" if unit == "B" else f"{b:.1f} {unit}")
        b /= 1024.0


def storage_put(path, move=False):
    """Copy (or move) a file into Genius storage. Returns (new_path, message)."""
    import shutil
    size = os.path.getsize(path)
    if storage_used() + size > STORAGE_LIMIT_MB * 1024 * 1024:
        return None, f"Storage is full ({STORAGE_LIMIT_MB} MB). Delete something first."
    name = os.path.basename(path)
    name = re.sub(r"^\d{9,}_", "", name)
    dest = os.path.join(storage_dir(), name)
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = f"{base}_{i}{ext}"
        i += 1
    (shutil.move if move else shutil.copy2)(path, dest)
    return dest, f"Saved {os.path.basename(dest)} to your storage ({nice_size(size)})."


def storage_note(text):
    name = "note_" + time.strftime("%Y%m%d_%H%M%S") + ".txt"
    f = os.path.join(storage_dir(), name)
    open(f, "w", encoding="utf8").write(text)
    return f


# ---------------- Fun studio: collage, picture transformations, video slideshow ----------------
FUN_STYLES = ("HD clear", "Warm", "Cool", "Teal & orange", "Cinematic", "Fade", "Dreamy", "Film grain",
              "Glitch", "Neon", "Cartoon", "Duotone pink", "Polaroid", "Vignette",
              "Black & white", "Vintage", "Pencil sketch", "Vivid colours", "Soft glow",
              "Mirror", "Rotate", "Blur", "Sharpen", "Negative", "Pixel art", "Poster", "Emboss", "Bright")
AI_STYLES = (("Oil painting", "turn it into a realistic oil painting"),
             ("Watercolour", "turn it into a soft watercolour painting"),
             ("Old 1950s photo", "make it look like an old 1950s photograph"),
             ("Sunset", "change the light to a golden sunset"),
             ("Night city", "change it to night with city lights"),
             ("Rainy day", "make it a rainy day with wet reflections"))


KEEP = (" Change ONLY that. Keep the same person with the identical face, skin tone, hair, body shape and pose, "
        "in exactly the same position, size and framing; do not move, crop, zoom or rotate anything. "
        "Photorealistic, natural light.")
OUTFITS = (("Smart suit", "dress the person in a smart, well-fitted dark suit with a white shirt"),
           ("Kanzu", "dress the person in a clean white Ugandan kanzu with a dark coat"),
           ("Gomesi", "dress the person in a beautiful colourful Ugandan gomesi"),
           ("Football jersey", "dress the person in a Uganda Cranes football jersey"),
           ("Graduation gown", "dress the person in a graduation gown and cap"),
           ("Doctor coat", "dress the person in a doctor's white coat with a stethoscope"),
           ("Pilot uniform", "dress the person in an airline pilot uniform"),
           ("Streetwear", "dress the person in stylish modern streetwear and sneakers"),
           ("Wedding outfit", "dress the person in an elegant wedding outfit"),
           ("Traditional Kitenge", "dress the person in a stylish African kitenge outfit"),
           ("Winter coat", "dress the person in a warm stylish winter coat and scarf"),
           ("Sports kit", "dress the person in a sporty running outfit"))
PLACES = (("Beach", "put the person on a beautiful sunny beach with blue sea"),
          ("Kampala city", "put the person in Kampala city centre with tall buildings"),
          ("Source of the Nile", "put the person at the Source of the Nile in Jinja"),
          ("Murchison Falls", "put the person in front of Murchison Falls in Uganda"),
          ("Mountains", "put the person in green mountains like the Rwenzori"),
          ("Paris", "put the person in Paris with the Eiffel Tower behind"),
          ("New York", "put the person on a New York street with skyscrapers"),
          ("Dubai", "put the person in Dubai with the Burj Khalifa behind"),
          ("Luxury car", "put the person standing next to a shiny luxury car"),
          ("Office", "put the person in a modern bright office"),
          ("Stadium", "put the person on the pitch of a big football stadium"),
          ("Safari", "put the person on a safari in Queen Elizabeth park with animals far behind"),
          ("Night city", "put the person in a city at night with beautiful lights"),
          ("Studio portrait", "put the person in a professional photo studio with a plain soft background"))
REPLACE = (("Replace sky (blue)", "replace the sky with a clear beautiful blue sky with soft clouds"),
           ("Replace sky (sunset)", "replace the sky with a dramatic orange and pink sunset"),
           ("Replace background", "replace the background with a beautiful blurred modern city street"),
           ("Portrait mode", "make it look like iPhone Portrait mode: person razor sharp, background beautifully blurred with soft bokeh"),
           ("Studio light", "relight the person like iPhone Studio Light portrait lighting, bright and flattering"),
           ("Replace shoes", "replace the shoes with clean white sneakers"),
           ("Replace phone", "replace the phone in the hand with a new premium smartphone"),
           ("Replace car", "replace the car with a shiny modern luxury car"),
           ("Night to day", "make it bright daytime with natural sunlight"),
           ("Day to night", "make it night with beautiful lights and a dark blue sky"))
BEAUTY = (("Make it beautiful", "make this a beautiful professional photo: better light, sharp, rich colours, clean background"),
          ("Clear skin", "gently clear the skin and remove spots while keeping it natural"),
          ("Better lighting", "improve the lighting to soft, flattering golden light"),
          ("Blur background", "blur the background like a professional camera, keep the person sharp"),
          ("Smile", "give the person a natural, happy smile"),
          ("Neat hair", "make the hair neat and well styled"))


PRO_LOOKS = ("iPhone Vibrant", "iPhone Warm", "iPhone Cool", "Rich Contrast", "Luminous", "HDR Pop",
             "Cinematic", "Golden Hour", "Moody Film", "Clean Portrait", "Soft Pastel", "Dramatic B&W")


def _curve(im, lift=0, gamma=1.0, gain=1.0):
    lut = [max(0, min(255, int(lift + (255 - lift) * ((i / 255.0) ** gamma) * gain))) for i in range(256)]
    return im.point(lut * 3)


def _vignette(im, strength=0.35):
    from PIL import Image, ImageDraw, ImageFilter
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-w * 0.15, -h * 0.15, w * 1.15, h * 1.15), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    dark = Image.eval(im, lambda x: int(x * (1 - strength)))
    return Image.composite(im, dark, mask)


def _tint(im, r=1.0, g=1.0, b=1.0):
    from PIL import Image
    R, G, B = im.split()
    return Image.merge("RGB", (R.point(lambda x: min(255, int(x * r))), G.point(lambda x: min(255, int(x * g))),
                               B.point(lambda x: min(255, int(x * b)))))


def _local_contrast(im, amount=0.6):
    from PIL import Image, ImageFilter, ImageChops
    blur = im.filter(ImageFilter.GaussianBlur(max(im.size) // 40 or 2))
    detail = ImageChops.subtract(im, blur, scale=1, offset=128)
    return ImageChops.add(im, Image.eval(detail, lambda x: int((x - 128) * amount)), scale=1, offset=0) \
        if False else im.filter(ImageFilter.UnsharpMask(max(im.size) // 60 or 2, int(80 * amount + 40), 2))


def pro_look(path, look):
    """Phone-camera style looks (like iPhone Photographic Styles) done on the phone, instant."""
    from PIL import ImageOps, ImageEnhance, ImageFilter, Image
    im = _open_rgb(path)
    im.thumbnail((4096, 4096))
    im = ImageOps.autocontrast(im, cutoff=0.5)
    L = look.lower()
    if "vibrant" in L:
        im = ImageEnhance.Color(im).enhance(1.35)
        im = _curve(im, 0, 0.92, 1.0)
        im = _local_contrast(im, 0.5)
    elif "warm" in L and "golden" not in L:
        im = _tint(ImageEnhance.Color(im).enhance(1.12), 1.06, 1.01, 0.92)
        im = _curve(im, 4, 0.95)
    elif "cool" in L:
        im = _tint(ImageEnhance.Color(im).enhance(1.08), 0.94, 1.0, 1.07)
        im = _curve(im, 2, 0.97)
    elif "rich" in L:
        im = ImageEnhance.Contrast(im).enhance(1.28)
        im = ImageEnhance.Color(im).enhance(1.12)
        im = _curve(im, 0, 1.08)
        im = _local_contrast(im, 0.7)
    elif "luminous" in L:
        im = _curve(im, 14, 0.85)
        im = Image.blend(im, im.filter(ImageFilter.GaussianBlur(8)), 0.18)
        im = ImageEnhance.Color(im).enhance(1.1)
    elif "hdr" in L:
        im = _local_contrast(im, 1.0)
        im = _curve(im, 10, 0.88)
        im = ImageEnhance.Color(im).enhance(1.25)
        im = ImageEnhance.Sharpness(im).enhance(1.4)
    elif "cinematic" in L:
        im = ImageEnhance.Contrast(im).enhance(1.15)
        sh = _tint(im, 0.92, 1.0, 1.08)          # teal shadows, orange highlights
        hi = _tint(im, 1.08, 1.0, 0.9)
        im = Image.composite(hi, sh, ImageOps.grayscale(im))
        im = _vignette(ImageEnhance.Color(im).enhance(0.92), 0.3)
    elif "golden" in L:
        im = _tint(im, 1.12, 1.03, 0.85)
        im = _curve(im, 8, 0.9)
        im = _vignette(ImageEnhance.Color(im).enhance(1.15), 0.22)
    elif "film" in L:
        im = _curve(im, 22, 1.0, 0.94)            # faded blacks
        im = _tint(ImageEnhance.Color(im).enhance(0.8), 1.02, 1.0, 0.95)
        im = _vignette(im, 0.3)
    elif "portrait" in L:
        im = Image.blend(im, im.filter(ImageFilter.SMOOTH_MORE), 0.45)
        im = _curve(im, 6, 0.92)
        im = ImageEnhance.Color(_tint(im, 1.03, 1.0, 0.97)).enhance(1.08)
        im = _vignette(im, 0.15)
    elif "pastel" in L:
        im = _curve(im, 30, 0.85, 0.95)
        im = ImageEnhance.Color(im).enhance(0.75)
        im = _tint(im, 1.03, 1.0, 1.05)
    elif "b&w" in L or "dramatic" in L:
        g = ImageOps.grayscale(im)
        g = ImageEnhance.Contrast(g).enhance(1.45)
        im = _vignette(g.convert("RGB"), 0.35)
    else:
        return None, "I don't know that look."
    im = im.filter(ImageFilter.UnsharpMask(2, 70, 3))
    out = fun_out("look_" + re.sub(r"\W+", "", L)[:12])
    im.save(out, quality=95)
    return out, look + " look done."


# ================= Genius Music Maker =================
# 109.5 "real" engine: 44.1 kHz 16-bit stereo, plucked strings (Karplus-Strong), additive/FM keys,
# synthesised drums, humanised timing and velocity, panning, reverb, delay, bus compression and a limiter.
# Pure Python (stdlib only) so it ships as a quiet code update.
import math as _m, random as _r, wave as _wave, array as _array, sys as _sys

SR = 44100
_NOTE = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6,
         "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}
_SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10],
           "dorian": [0, 2, 3, 5, 7, 9, 10], "mixolydian": [0, 2, 4, 5, 7, 9, 10]}

# Every genre: tempo, scale, keys, chord progressions, drum kit pattern, swing, and which
# instrument plays chords / bass / lead melody / arpeggio / pad, plus their rhythms.
_STYLES = {
    "afrobeat":  dict(label="Afrobeat", bpm=104, scale="minor", keys=("A", "G", "F#", "C"),
                      progs=([6, 4, 1, 5], [1, 6, 4, 5], [2, 5, 1, 1]), drums="afro", swing=0.10,
                      chords="epiano", crhythm="offbeat", bass="bass", brhythm="afro", lead="kora",
                      arp="guitar", pad="pad", sevenths=True, family="party"),
    "amapiano":  dict(label="Amapiano", bpm=112, scale="dorian", keys=("F", "G", "A", "D"),
                      progs=([2, 5, 1, 6], [1, 4, 2, 5], [6, 2, 5, 1]), drums="amapiano", swing=0.16,
                      chords="epiano", crhythm="piano_stab", bass="logdrum", brhythm="amapiano", lead="flute",
                      arp=None, pad="pad", sevenths=True, family="party"),
    "gospel":    dict(label="Gospel", bpm=76, scale="major", keys=("C", "D", "Eb", "F"),
                      progs=([1, 4, 6, 5], [1, 6, 2, 5], [4, 5, 3, 6]), drums="gospel", swing=0.12,
                      chords="piano", crhythm="gospel", bass="bass", brhythm="gospel", lead="piano",
                      arp=None, pad="organ", sevenths=True, family="praise"),
    "praise":    dict(label="Luganda praise", bpm=120, scale="major", keys=("D", "E", "G", "A"),
                      progs=([1, 4, 5, 1], [1, 5, 6, 4], [4, 1, 5, 1]), drums="praise", swing=0.06,
                      chords="guitar", crhythm="strum8", bass="bass", brhythm="bouncy", lead="organ",
                      arp="kora", pad="organ", sevenths=False, family="praise", lang="lg"),
    "kadongo":   dict(label="Kadongo Kamu", bpm=96, scale="major", keys=("G", "D", "A", "C"),
                      progs=([1, 4, 5, 1], [1, 5, 4, 1], [1, 4, 1, 5]), drums="kadongo", swing=0.08,
                      chords="guitar", crhythm="fingerpick", bass="ksbass", brhythm="kadongo", lead="guitar",
                      arp=None, pad=None, sevenths=False, family="story"),
    "dancehall": dict(label="Dancehall", bpm=96, scale="minor", keys=("A", "C", "D", "E"),
                      progs=([1, 6, 7, 1], [1, 4, 6, 5], [6, 7, 1, 1]), drums="dembow", swing=0.0,
                      chords="lead", crhythm="dembow_stab", bass="808", brhythm="dembow", lead="brass",
                      arp=None, pad="pad", sevenths=False, family="party"),
    "hiphop":    dict(label="Hip hop", bpm=88, scale="minor", keys=("C", "D", "F", "G"),
                      progs=([1, 6, 4, 5], [1, 1, 6, 7], [6, 4, 1, 7]), drums="boombap", swing=0.18,
                      chords="piano", crhythm="sparse", bass="808", brhythm="trap", lead="bell",
                      arp=None, pad="strings", sevenths=True, family="hustle"),
    "rnb":       dict(label="RnB", bpm=74, scale="dorian", keys=("Eb", "F", "Bb", "C"),
                      progs=([2, 5, 1, 6], [1, 6, 2, 5], [4, 3, 2, 1]), drums="rnb", swing=0.14,
                      chords="epiano", crhythm="rnb", bass="808", brhythm="rnb", lead="lead",
                      arp=None, pad="pad", sevenths=True, family="love"),
    "ballad":    dict(label="Love ballad", bpm=68, scale="major", keys=("C", "D", "F", "G"),
                      progs=([1, 5, 6, 4], [1, 6, 4, 5], [4, 1, 5, 6]), drums="ballad", swing=0.0,
                      chords="piano", crhythm="arp8", bass="bass", brhythm="ballad", lead="violin",
                      arp=None, pad="strings", sevenths=False, family="love"),
    "kids":      dict(label="Kids song", bpm=116, scale="major", keys=("C", "F", "G", "D"),
                      progs=([1, 4, 5, 1], [1, 5, 1, 4], [1, 4, 1, 5]), drums="kids", swing=0.0,
                      chords="piano", crhythm="bouncy", bass="bass", brhythm="bouncy", lead="marimba",
                      arp="bell", pad=None, sevenths=False, family="kids"),
    "pop":       dict(label="Pop", bpm=110, scale="major", keys=("C", "G", "D", "A"),
                      progs=([1, 5, 6, 4], [6, 4, 1, 5], [1, 6, 4, 5]), drums="pop", swing=0.0,
                      chords="piano", crhythm="pop", bass="bass", brhythm="pop", lead="lead",
                      arp="guitar", pad="pad", sevenths=False, family="party"),
    "lofi":      dict(label="Lo-fi chill", bpm=78, scale="dorian", keys=("D", "F", "G", "A"),
                      progs=([2, 5, 1, 6], [4, 3, 2, 1], [1, 6, 2, 5]), drums="lofi", swing=0.22,
                      chords="epiano", crhythm="sustain", bass="ksbass", brhythm="root8", lead="epiano",
                      arp=None, pad="pad", sevenths=True, family="calm"),
    "cinematic": dict(label="Cinematic", bpm=70, scale="minor", keys=("D", "C", "E", "A"),
                      progs=([1, 6, 3, 7], [6, 4, 1, 5], [1, 4, 6, 5]), drums="cine", swing=0.0,
                      chords="strings", crhythm="sustain", bass="bass", brhythm="whole", lead="violin",
                      arp="piano", pad="pad", sevenths=False, family="story"),
    "dance":     dict(label="Dance", bpm=124, scale="minor", keys=("A", "F", "G", "C"),
                      progs=([6, 4, 1, 5], [1, 6, 7, 5], [1, 4, 6, 5]), drums="four", swing=0.0,
                      chords="lead", crhythm="offbeat", bass="bass", brhythm="offbeat", lead="lead",
                      arp="pluck", pad="pad", sevenths=False, family="party"),
}
_STYLE_WORDS = (  # checked in order: the first match wins
    ("luganda praise", "praise"), ("kadongo", "kadongo"), ("dancehall", "dancehall"), ("dance hall", "dancehall"),
    ("ragga", "dancehall"), ("amapiano", "amapiano"), ("ama piano", "amapiano"), ("piano", None),
    ("afrobeat", "afrobeat"), ("afro beat", "afrobeat"), ("afro", "afrobeat"), ("hip hop", "hiphop"),
    ("hiphop", "hiphop"), ("hip-hop", "hiphop"), ("rap", "hiphop"), ("trap", "hiphop"), ("drill", "hiphop"),
    ("rnb", "rnb"), ("r&b", "rnb"), ("r and b", "rnb"), ("soul", "rnb"), ("love ballad", "ballad"),
    ("ballad", "ballad"), ("kids", "kids"), ("kid", "kids"), ("children", "kids"), ("nursery", "kids"),
    ("gospel", "gospel"), ("worship", "gospel"), ("hymn", "gospel"), ("praise", "praise"), ("tumutendereze", "praise"),
    ("lofi", "lofi"), ("lo-fi", "lofi"), ("lo fi", "lofi"), ("chill", "lofi"), ("study", "lofi"),
    ("cinematic", "cinematic"), ("epic", "cinematic"), ("movie", "cinematic"), ("film", "cinematic"),
    ("edm", "dance"), ("house", "dance"), ("dance", "dance"), ("club", "dance"), ("pop", "pop"),
)
_FAMILY_STYLE = {"love": "rnb", "praise": "gospel", "party": "afrobeat", "kids": "kids", "mum": "ballad",
                 "sad": "ballad", "hustle": "hiphop", "friends": "afrobeat", "story": "kadongo", "calm": "lofi"}

_PAT = {  # 16 steps a bar. x = hit, o = soft ghost hit
    "afro":     dict(kick="x..x..x...x..x..", snare="....x.......x...", rim="...x..x....x..x.",
                     hat="x.xxx.xxx.xxx.xx", shaker="xoxoxoxoxoxoxoxo", conga="..x.o..x..x.o.x."),
    "amapiano": dict(kick="x...x...x...x...", clap="....x.......x...", shaker="oxoxoxoxoxoxoxox",
                     ohat="..x...x...x...x.", rim="......x.......x."),
    "gospel":   dict(kick="x.....x...x.....", snare="....x.......x..o", hat="x.x.x.x.x.x.x.x.",
                     shaker="..x...x...x...x."),
    "praise":   dict(kick="x...x...x...x...", snare="....x.......x...", hat="xoxxxoxxxoxxxoxx",
                     shaker="xoxoxoxoxoxoxoxo", conga="x..x.x..x..x.x.."),
    "kadongo":  dict(kick="x.......x.......", rim="....x.......x...", shaker="x.xox.xox.xox.xo",
                     ngoma="x..o..x.x..o..x."),
    "dembow":   dict(kick="x...x...x...x...", snare="...x..x....x..x.", hat="x.x.x.x.x.x.x.x.",
                     rim="..x.......x....."),
    "boombap":  dict(kick="x.....x..x......", snare="....x.......x...", hat="x.x.x.x.x.xox.x."),
    "trap":     dict(kick="x......x..x.....", clap="........x.......", hat="xxxxxxxxxxxxxxxx"),
    "rnb":      dict(kick="x......x..x.....", snare="....x.......x...", hat="x.x.x.x.xxx.x.x.",
                     rim="..o.......o....."),
    "ballad":   dict(kick="x.........x.....", snare="........x.......", hat="x...x...x...x..."),
    "kids":     dict(kick="x...x...x...x...", clap="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                     shaker="xoxoxoxoxoxoxoxo"),
    "pop":      dict(kick="x.....x.x.......", snare="....x.......x...", hat="x.x.x.x.x.x.x.x.",
                     shaker="oxoxoxoxoxoxoxox"),
    "lofi":     dict(kick="x......x..x.....", snare="....x.......x...", hat="x.xox.xox.xox.xo"),
    "cine":     dict(kick="x...............", tom="x.....x...x.....", hat="........x......."),
    "four":     dict(kick="x...x...x...x...", clap="....x.......x...", ohat="..x...x...x...x.",
                     hat="x.x.x.x.x.x.x.x."),
}
_CR = {  # chord rhythms: (start step, length in steps)
    "sustain": [(0, 16)], "offbeat": [(2, 2), (6, 2), (10, 2), (14, 2)],
    "piano_stab": [(0, 2), (3, 2), (6, 3), (10, 2), (12, 4)],
    "gospel": [(0, 6), (6, 2), (8, 6), (14, 2)], "strum8": [(s, 2) for s in range(0, 16, 2)],
    "dembow_stab": [(0, 2), (3, 2), (6, 2), (8, 2), (11, 2), (14, 2)], "sparse": [(0, 8), (10, 6)],
    "rnb": [(0, 10), (10, 6)], "bouncy": [(0, 2), (4, 2), (8, 2), (12, 2)], "pop": [(0, 6), (6, 4), (10, 6)],
    "arp8": "arp", "fingerpick": "arp",
}
_BR = {  # bass rhythms: (step, length, semitones above the chord root)
    "afro": [(0, 3, 0), (3, 3, 0), (6, 2, 7), (10, 3, 0), (14, 2, 12)],
    "amapiano": [(0, 4, 0), (3, 4, 0), (7, 3, 7), (10, 4, 0), (14, 2, -5)],
    "gospel": [(0, 6, 0), (6, 2, 7), (8, 6, 0), (14, 2, 12)], "root8": [(0, 8, 0), (8, 8, 0)],
    "whole": [(0, 16, 0)], "kadongo": [(0, 4, 0), (4, 4, 7), (8, 4, 0), (12, 4, 7)],
    "dembow": [(0, 3, 0), (3, 5, 0), (8, 3, 0), (11, 5, 7)], "trap": [(0, 6, 0), (7, 3, 0), (10, 6, 12)],
    "rnb": [(0, 7, 0), (7, 3, 0), (10, 6, -5)], "bouncy": [(0, 2, 0), (4, 2, 12), (8, 2, 7), (12, 2, 12)],
    "pop": [(0, 3, 0), (3, 3, 0), (6, 2, 0), (8, 3, 0), (11, 3, 0), (14, 2, 7)],
    "offbeat": [(2, 2, 0), (6, 2, 0), (10, 2, 0), (14, 2, 0)], "ballad": [(0, 8, 0), (8, 8, 7)],
}
_FORM = (("intro", 2), ("verse1", 4), ("chorus", 4), ("verse2", 4), ("chorus", 4),
         ("bridge", 2), ("chorus", 4), ("outro", 2))
_PAN = {"kick": 0.0, "snare": 0.05, "clap": -0.05, "rim": 0.3, "hat": 0.35, "ohat": 0.4, "shaker": -0.45,
        "conga": 0.5, "ngoma": -0.35, "tom": -0.2, "crash": -0.3}


def _freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)


# ---------- wavetables ----------
_TN = 4096
_TABS = {}


def _table(kind):
    if kind not in _TABS:
        sin, c = _m.sin, 2 * _m.pi / _TN
        if kind == "soft":
            h = [(1, 1.0), (2, 0.35), (3, 0.15), (4, 0.07)]
        elif kind == "saw":
            h = [(k, 1.0 / k) for k in range(1, 13)]
        elif kind == "dark":
            h = [(k, 1.0 / (k * k ** 0.5)) for k in range(1, 9)]
        elif kind == "organ":                         # drawbars 16' 8' 5 1/3' 4' 2 2/3' 2' (base = f/2)
            h = [(1, 0.6), (2, 1.0), (3, 0.6), (4, 0.45), (6, 0.25), (8, 0.2)]
        else:
            h = [(1, 1.0)]
        t = [sum(a * sin(k * i * c) for k, a in h) for i in range(_TN)]
        pk = max(abs(x) for x in t) or 1.0
        _TABS[kind] = [x / pk for x in t]
    return _TABS[kind]


def _osc(tab, f, n, detune=(1.0,), vib=0.0, vib_rate=5.5, vib_delay=0.0):
    """Wavetable oscillator (one or more detuned voices, optional delayed vibrato)."""
    out = [0.0] * n
    mask, sin = _TN - 1, _m.sin
    w = 2 * _m.pi * vib_rate / SR
    vd = int(vib_delay * SR)
    for dt in detune:
        inc = f * dt * _TN / SR
        ph = _r.random() * _TN
        if vib:
            for i in range(n):
                v = vib * sin(i * w) * (min(1.0, (i - vd) / (0.3 * SR)) if i > vd else 0.0)
                ph += inc * (1 + v)
                out[i] += tab[int(ph) & mask]
        else:
            for i in range(n):
                ph += inc
                out[i] += tab[int(ph) & mask]
    if len(detune) > 1:
        g = 1.0 / len(detune) ** 0.5
        out = [x * g for x in out]
    return out


def _adsr(n, a, d, s, r=0.0):
    A, D = max(1, int(a * SR)), max(1, int(d * SR))
    out = []
    for i in range(n):
        if i < A:
            out.append(i / A)
        elif i < A + D:
            out.append(1 - (1 - s) * (i - A) / D)
        else:
            out.append(s)
    return out


def _lp(x, passes=1):
    for _ in range(passes):
        x = [(a + b) * 0.5 for a, b in zip(x, [x[0]] + x[:-1])]
    return x


def _ks(f, n, decay_s, smooth=1, pick=0.2):
    """Karplus-Strong plucked string, computed one period at a time (fast in pure Python)."""
    p = max(2, int(SR / f + 0.5))
    exc = _lp([_r.uniform(-1, 1) for _ in range(p)], smooth)
    q = max(1, int(p * pick))
    exc = [exc[i] - 0.7 * exc[i - q] for i in range(p)]           # pick position
    g = 0.001 ** (1.0 / max(1.0, f * decay_s))
    out, buf = [], exc
    while len(out) < n:
        out.extend(buf)
        buf = [g * 0.5 * (a + b) for a, b in zip(buf, [buf[-1]] + buf[:-1])]
    return out[:n]


_CAP = {"piano": 2.0, "epiano": 1.6, "guitar": 2.0, "kora": 2.2, "ksbass": 1.6, "bass": 1.6, "808": 1.8,
        "logdrum": 0.7, "marimba": 1.1, "bell": 1.8, "pluck": 1.0}   # decaying sounds: render once, cut to length
_CACHE = {}


def _base(inst, midi, n):
    """Raw note, before the release fade. Decaying instruments render once per pitch."""
    cap = _CAP.get(inst)
    key = (inst, midi) if cap else (inst, midi, n)
    if key in _CACHE:
        return _CACHE[key]
    f = _freq(midi)
    N = int(cap * SR) if cap else n
    sin, exp, w = _m.sin, _m.exp, 2 * _m.pi / SR
    out = []
    if inst == "piano":                                   # additive, stretched partials, 2 detuned strings, hammer
        B = 0.00035
        parts = [(k * (1 + B * k * k) ** 0.5, 1.0 / k ** 1.1, exp(-1 / (SR * 2.4 * (440.0 / f) ** 0.35 / (1 + 0.7 * (k - 1)))))
                 for k in range(1, 7) if k * f < SR / 2.2]
        amps, decs = [a for _, a, _ in parts], [d for _, _, d in parts]
        incs = [w * f * m for m, _, _ in parts]
        inc2 = w * f * 1.0013
        lvl = list(amps)
        for i in range(N):
            s = 0.0
            for j in range(len(incs)):
                s += sin(i * incs[j]) * lvl[j]
                lvl[j] *= decs[j]
            s += 0.5 * sin(i * inc2) * lvl[0]
            if i < 180:
                s += _r.uniform(-1, 1) * 0.25 * (1 - i / 180.0)
            out.append(s * min(1.0, i / 60.0) * 0.36)
    elif inst == "epiano":                                # FM tine piano
        inc = w * f
        tine = 14 * f < SR / 2.2
        for i in range(N):
            t = i * inc
            idx = 1.6 * exp(-i / (0.28 * SR)) + 0.25
            s = sin(t + idx * sin(t))
            if tine:
                s += 0.12 * sin(14 * t) * exp(-i / (0.04 * SR))
            out.append(s * exp(-i / (1.5 * SR)) * min(1.0, i / 40.0) * 0.6)
    elif inst == "marimba":                               # modal bar: partials 1 : 3.93 : 9.2
        a1, a2, a3 = w * f, w * f * 3.93, w * f * 9.2
        hi = f * 9.2 < SR / 2.2
        for i in range(N):
            s = sin(i * a1) * exp(-i / (0.45 * SR)) + 0.35 * sin(i * a2) * exp(-i / (0.09 * SR))
            if hi:
                s += 0.12 * sin(i * a3) * exp(-i / (0.025 * SR))
            out.append(s * min(1.0, i / 30.0) * 0.5)
    elif inst == "bell":                                  # FM bell, ratio 3.5
        inc = w * f
        for i in range(N):
            t = i * inc
            out.append(sin(t + 2.0 * exp(-i / (0.35 * SR)) * sin(3.5 * t)) * exp(-i / (0.9 * SR)) * min(1.0, i / 30.0) * 0.38)
    elif inst == "guitar":
        out = [x * 0.8 for x in _lp(_ks(f, N, 2.2, smooth=2, pick=0.18), 1)]
    elif inst == "kora":
        k = _ks(f, N, 2.8, smooth=0, pick=0.11)
        out = [x * 0.85 for x in _lp(k, 1)]
    elif inst == "pluck":
        out = [x * 0.45 for x in _ks(f, N, 0.8, smooth=1, pick=0.3)]
    elif inst == "ksbass":
        k = _lp(_ks(f, N, 1.2, smooth=4, pick=0.25), 2)
        inc = w * f
        out = [0.7 * a + 0.45 * sin(i * inc) * exp(-i / (0.9 * SR)) for i, a in enumerate(k)]
    elif inst == "bass":                                  # finger bass
        inc = w * f
        th = _m.tanh
        for i in range(N):
            t = i * inc
            e = exp(-i / (1.1 * SR)) * min(1.0, i / 90.0)
            out.append(th(1.6 * (sin(t) + 0.3 * sin(2 * t) * exp(-i / (0.15 * SR)) + 0.1 * sin(3 * t))) * e * 0.38)
    elif inst == "808":                                   # 808 bass: pitch drop + saturation (heard on phone speakers)
        th = _m.tanh
        ph = 0.0
        for i in range(N):
            fr = f * (1 + 0.8 * exp(-i / (0.012 * SR)))
            ph += w * fr
            out.append(th(2.2 * sin(ph)) * exp(-i / (0.9 * SR)) * min(1.0, i / 40.0) * 0.6)
    elif inst == "logdrum":                               # amapiano log drum
        th = _m.tanh
        ph = 0.0
        for i in range(N):
            fr = f * (1 + 0.55 * exp(-i / (0.018 * SR)))
            ph += w * fr
            s = sin(ph) + 0.3 * sin(2 * ph) * exp(-i / (0.05 * SR))
            out.append(th(1.7 * s) * exp(-i / (0.26 * SR)) * min(1.0, i / 25.0) * 0.7)
    elif inst in ("pad", "strings"):
        tab = _table("soft" if inst == "pad" else "saw")
        o = _osc(tab, f, N, detune=(0.994, 1.0, 1.006), vib=0.0 if inst == "pad" else 0.003, vib_rate=5.0)
        env = _adsr(N, 0.4 if inst == "pad" else 0.2, 0.3, 0.85)
        o = _lp(o, 2 if inst == "strings" else 1)
        out = [a * e * (0.22 if inst == "pad" else 0.18) for a, e in zip(o, env)]
    elif inst == "violin":
        o = _lp(_osc(_table("saw"), f, N, vib=0.006, vib_rate=5.6, vib_delay=0.18), 1)
        env = _adsr(N, 0.07, 0.2, 0.8)
        out = [a * e * 0.3 for a, e in zip(o, env)]
    elif inst == "organ":                                 # drawbar organ with a slow Leslie wobble
        o = _osc(_table("organ"), f / 2, N, vib=0.0035, vib_rate=6.2)
        out = [a * (0.85 + 0.15 * sin(i * w * 6.2)) * min(1.0, i / 220.0) * 0.3 for i, a in enumerate(o)]
    elif inst == "flute":
        o = _osc(_table("soft"), f, N, vib=0.005, vib_rate=5.0, vib_delay=0.15)
        env = _adsr(N, 0.06, 0.15, 0.8)
        br = _lp([_r.uniform(-1, 1) for _ in range(N)], 3)
        out = [(a * 0.9 + b * 0.12) * e * 0.32 for a, b, e in zip(o, br, env)]
    elif inst == "lead":
        o = _lp(_osc(_table("saw"), f, N, detune=(0.996, 1.004), vib=0.003, vib_delay=0.2), 1)
        env = _adsr(N, 0.012, 0.25, 0.65)
        out = [a * e * 0.26 for a, e in zip(o, env)]
    elif inst == "brass":                                 # swell from dark to bright like a horn
        o1, o2 = _osc(_table("dark"), f, N), _osc(_table("saw"), f, N, vib=0.003, vib_delay=0.2)
        A = int(0.06 * SR)
        out = []
        for i in range(N):
            e = min(1.0, i / A)
            out.append((o1[i] * (1 - e * 0.6) + o2[i] * e * 0.6) * (0.4 + 0.6 * e) * 0.3)
    else:
        inc = w * f
        out = [sin(i * inc) * 0.4 for i in range(N)]
    _CACHE[key] = out
    return out


def _voice(inst, midi, n):
    """A note of length n samples with a short natural release."""
    key = ("v", inst, midi, n)
    if key in _CACHE:
        return _CACHE[key]
    src = _base(inst, midi, n)
    v = src[:n] if len(src) >= n else src + [0.0] * (n - len(src))
    rel = min(len(v), int(0.07 * SR))
    if rel > 1:
        k = len(v) - rel
        v = v[:k] + [x * (1 - i / rel) for i, x in enumerate(v[k:])]
    _CACHE[key] = v
    return v


def _chord(inst, notes, n, spread=0, gains=None):
    """All notes of a chord summed into one buffer (strummed by `spread` samples), mixed in one go."""
    key = ("c", inst, tuple(notes), n, spread)
    if key in _CACHE:
        return _CACHE[key]
    out = [0.0] * (n + spread * len(notes))
    for k, nt in enumerate(notes):
        v = _voice(inst, nt, n)
        o = k * spread
        g = gains[k] if gains else 1.0
        out[o:o + n] = [a + b * g for a, b in zip(out[o:o + n], v)]
    _CACHE[key] = out
    return out


def _noise(n):
    u = _r.uniform
    return [u(-1, 1) for _ in range(n)]


def _hp(x):
    return [a - b for a, b in zip(x, [0.0] + x[:-1])]


def _drum(kind, var=0):
    key = ("drum", kind, var)
    if key in _CACHE:
        return _CACHE[key]
    sin, exp, th = _m.sin, _m.exp, _m.tanh
    out = []
    if kind == "kick":                                    # pitch drop + beater click + saturation
        ph = 0.0
        for i in range(int(0.42 * SR)):
            fr = 47 + 115 * exp(-i / (0.032 * SR))
            ph += 2 * _m.pi * fr / SR
            s = sin(ph) * exp(-i / (0.2 * SR))
            if i < 160:
                s += _r.uniform(-1, 1) * 0.35 * (1 - i / 160.0)
            out.append(th(1.5 * s) * 0.75)
    elif kind == "snare":                                 # two body tones + bright noise
        nz = _hp(_noise(int(0.24 * SR)))
        for i, x in enumerate(nz):
            body = 0.55 * sin(2 * _m.pi * 182 * i / SR) * exp(-i / (0.05 * SR)) + 0.3 * sin(2 * _m.pi * 330 * i / SR) * exp(-i / (0.03 * SR))
            out.append((body + 0.6 * x * exp(-i / (0.075 * SR))) * 0.55)
    elif kind == "clap":                                  # 3 quick bursts and a tail
        nz = _hp(_lp(_noise(int(0.3 * SR)), 1))
        for i, x in enumerate(nz):
            t = i / SR
            e = sum(exp(-(t - o) / 0.006) for o in (0.0, 0.011, 0.022) if t >= o) * 0.5 + 0.6 * exp(-t / 0.09) * (t > 0.022)
            out.append(x * e * 0.5)
    elif kind in ("hat", "ohat", "crash"):                # metallic 808-style partials + noise
        n = int((0.06 if kind == "hat" else 0.35 if kind == "ohat" else 1.4) * SR)
        fr = [205.3, 304.4, 369.6, 522.7, 540.0, 800.0]
        mult = 1.0 if kind != "crash" else 1.3
        nz = _noise(n)
        dec = 0.022 if kind == "hat" else 0.12 if kind == "ohat" else 0.55
        for i in range(n):
            m = sum(1.0 if sin(2 * _m.pi * f * mult * 8 * i / SR) > 0 else -1.0 for f in fr[:4]) * 0.12
            out.append((m + nz[i] * 0.8) * exp(-i / (dec * SR)))
        out = _hp(_hp(out))
        g = 0.16 if kind == "hat" else 0.12 if kind == "ohat" else 0.10
        out = [x * g for x in out]
    elif kind == "shaker":
        nz = _hp(_hp(_noise(int(0.08 * SR))))
        A = 0.012 * SR
        out = [x * min(1.0, i / A) * exp(-i / (0.03 * SR)) * 0.12 for i, x in enumerate(nz)]
    elif kind == "rim":
        for i in range(int(0.05 * SR)):
            out.append((sin(2 * _m.pi * 1700 * i / SR) * exp(-i / (0.008 * SR)) + 0.6 * sin(2 * _m.pi * 820 * i / SR)
                        * exp(-i / (0.015 * SR)) + (_r.uniform(-1, 1) * 0.5 if i < 60 else 0)) * 0.3)
    elif kind in ("conga", "ngoma", "tom"):               # hand drums: pitch drop + slap
        f0 = {"conga": 215, "ngoma": 135, "tom": 105}[kind] * (1 + 0.04 * var)
        dec = {"conga": 0.17, "ngoma": 0.26, "tom": 0.35}[kind]
        ph = 0.0
        for i in range(int(dec * 3 * SR)):
            ph += 2 * _m.pi * f0 * (1 + 0.25 * exp(-i / (0.015 * SR))) / SR
            s = sin(ph) * exp(-i / (dec * SR)) + (_r.uniform(-1, 1) * 0.4 * exp(-i / (0.004 * SR)))
            out.append(th(1.3 * s) * 0.5)
    _CACHE[key] = out
    return out


# ---------- mixing helpers (float32 buffers keep memory low on phones) ----------
def _buf(n):
    return _array.array("f", bytes(4 * n))


def _addm(buf, src, pos, g):
    if pos < 0:
        src, pos = src[-pos:], 0
    end = min(len(buf), pos + len(src))
    if end > pos:
        buf[pos:end] = _array.array("f", [a + b * g for a, b in zip(buf[pos:end], src)])


def _comb(x, d, fb):
    """y[n] = x[n] + fb*y[n-d], one block of d samples at a time."""
    y = _array.array("f", x)
    n = len(y)
    for i in range(d, n, d):
        j = min(n, i + d)
        y[i:j] = _array.array("f", [a + b * fb for a, b in zip(y[i:j], y[i - d:j - d])])
    return y


def _allpass(x, d, g=0.5):
    y = _array.array("f", x)
    n = len(y)
    for i in range(0, n, d):
        j = min(n, i + d)
        if i < d:
            y[i:j] = _array.array("f", [-g * a for a in x[i:j]])
        else:
            y[i:j] = _array.array("f", [-g * a + b + g * c for a, b, c in zip(x[i:j], x[i - d:j - d], y[i - d:j - d])])
    return y


def _reverb(send):
    """Small hall: runs at half rate (the tail is dark anyway), 3 combs + allpass per side."""
    h = _array.array("f", [(a + b) * 0.5 for a, b in zip(send[0::2], send[1::2])])
    h = _array.array("f", _lp(list(h), 1))
    sr2 = SR // 2
    outs = []
    for delays in ((0.0297, 0.0371, 0.0411), (0.0313, 0.0389, 0.0437)):
        acc = None
        for dl, fb in zip(delays, (0.82, 0.80, 0.78)):
            c = _comb(h, int(dl * sr2), fb)
            acc = c if acc is None else _array.array("f", [a + b for a, b in zip(acc, c)])
        acc = _allpass(acc, int(0.0051 * sr2), 0.6)
        full = _array.array("f", bytes(4 * len(send)))
        half = len(full[0::2])
        if len(acc) < half:
            acc.extend([0.0] * (half - len(acc)))
        full[0::2] = acc[:half]
        full[1::2] = acc[:len(full[1::2])]
        outs.append(full)
    return outs


# ---------- what the user asked for ----------
_FAMILY_WORDS = (
    ("mum", ("mum", "mom", "mother", "mama", "maama", "mummy", "mommy")),
    ("family", ("dad", "father", "taata", "daddy", "family", "sister", "brother", "grandma", "jjajja", "parents")),
    ("praise", ("god", "jesus", "lord", "praise", "worship", "katonda", "yesu", "mukama", "church", "blessing")),
    ("sad", ("sad", "miss", "lost", "cry", "broken", "goodbye", "pain", "lonely")),
    ("love", ("love", "girl", "boy", "baby", "heart", "crush", "darling", "omukwano", "wife", "husband", "valentine")),
    ("kids", ("kid", "child", "abc", "alphabet", "count", "animals", "birthday", "school children")),
    ("friends", ("friend", "friends", "mates", "crew", "squad", "mikwano")),
    ("party", ("party", "dance", "weekend", "friday", "club", "celebrate", "fun", "vibe", "jaguza")),
    ("hustle", ("school", "exam", "hustle", "money", "dream", "success", "work", "freelanc", "future", "study")),
    ("home", ("uganda", "kampala", "home", "village", "africa", "buganda", "mityana")),
)
_LG_WORDS = ("luganda", "oluganda", "ganda", "katonda", "maama", "omukwano", "nkwagala", "webale", "tujaguze")
_MOODS = {"happy": "major", "joy": "major", "bright": "major", "sad": "minor", "dark": "minor",
          "emotional": "minor", "deep": "minor"}


def song_request(desc):
    """Read simple words like 'amapiano about my mum' or 'sad luganda love song'."""
    d = " " + re.sub(r"\s+", " ", (desc or "").lower()) + " "
    style = None
    for word, st in _STYLE_WORDS:
        if (" " + word + " " in d) or (len(word) > 4 and word in d):
            if st is None:                       # plain 'piano' means piano music, not amapiano
                if "ama" in d:
                    style = "amapiano"
                    break
                continue
            style = st
            break
    family = next((f for f, ws in _FAMILY_WORDS if any(re.search(r"\b" + re.escape(w), d) for w in ws)), None)
    if family == "home":
        family = None                            # 'about my village' keeps the genre's own feel
    m = re.search(r"\b(?:about|for|to|on)\s+(.+)", d)
    topic = m.group(1).strip(" .!?") if m else ""
    topic = re.sub(r"\b(in luganda|in english|luganda|english|song|music|please|beat)\b", "", topic).strip(" ,.")
    lang = "en"
    if "english and luganda" in d or "luganda and english" in d or " mix" in d or "both" in d:
        lang = "mix"
    elif any(w in d for w in _LG_WORDS):
        lang = "lg"
    chosen = "you" if style else "genius"
    if not style:
        style = _FAMILY_STYLE.get(family or "", "afrobeat")
    if lang == "en" and _STYLES[style].get("lang") == "lg" and "english" not in d:
        lang = "lg"
    mood = next((v for k, v in _MOODS.items() if re.search(r"\b" + k + r"\b", d)), None)
    family = family or _STYLES[style]["family"]
    return dict(style=style, chosen=chosen, family=family, topic=topic[:60], lang=lang, mood=mood)


# ---------- lyrics: built-in templates (rhymes stay at the line ends; the topic goes inside) ----------
_LYR_EN = {
    "mum": dict(
        hook="Mama, you're my everything",
        verse1=["You woke up early, before the sun", "Worked so hard till the day was done",
                "When I was sick you stayed by me", "You gave me all so I could be"],
        chorus=["Mama, you're my everything", "Your love's the reason that I sing",
                "Mama, you're my everything", "For you my heart will always ring"],
        verse2=["Every lesson, every prayer", "Every time I turned, you were there",
                "Now I'm growing, standing tall", "{T}, you gave me it all"],
        bridge=["Thank you, thank you, from my heart", "Nothing can tear our love apart"],
        intro=["Ooh, this one's for {t}", "Yeah, listen"], outro=["Mama, you're my everything", "Forever, mama"]),
    "family": dict(
        hook="Family, we stand as one",
        verse1=["Round the table, sharing food", "Laughing loud in a happy mood",
                "When the rain falls, we hold on tight", "Together we turn the dark to light"],
        chorus=["Family, we stand as one", "From the morning to the setting sun",
                "Family, we stand as one", "Our love is never, never done"],
        verse2=["{T} taught me how to stand", "Always ready with a helping hand",
                "Through the hard days, through the pain", "We dance together in the rain"],
        bridge=["Hold my hand and don't let go", "Home is where the love will grow"],
        intro=["This one's for {t}", "Come on"], outro=["Family, we stand as one", "As one, yeah"]),
    "praise": dict(
        hook="Lift Him higher, sing it loud",
        verse1=["When I was lost, You found my way", "You turned my night into the day",
                "Your grace is new with every sun", "The battle's won, the battle's won"],
        chorus=["Lift Him higher, sing it loud", "Raise your hands above the crowd",
                "Lift Him higher, sing it loud", "Our God is good, we're singing proud"],
        verse2=["Through every storm You hold my hand", "On solid rock I'm going to stand",
                "{T}, You are my song", "In You, Lord, I belong"],
        bridge=["Hallelujah, hallelujah", "Glory, glory, hallelujah"],
        intro=["Ooh, hallelujah", "Lift your hands"], outro=["Lift Him higher, sing it loud", "Hallelujah"]),
    "love": dict(
        hook="You're the one, you're the one",
        verse1=["The first time that I saw your face", "My heart was beating out of place",
                "Your smile is shining like the sun", "I knew that you would be the one"],
        chorus=["You're the one, you're the one", "My moonlight and my morning sun",
                "You're the one, you're the one", "With you my life has just begun"],
        verse2=["We walk together hand in hand", "You always seem to understand",
                "{T}, you light my way", "I need you here with me to stay"],
        bridge=["Hold me close, don't let me go", "Forever, baby, you should know"],
        intro=["Ooh, baby", "This one's for you"], outro=["You're the one, you're the one", "Only you"]),
    "sad": dict(
        hook="I still hear you in the rain",
        verse1=["The house is quiet, empty chair", "I turn around, you are not there",
                "The nights are long, the stars are few", "And every song reminds me of you"],
        chorus=["I still hear you in the rain", "I still feel you through the pain",
                "I still hear you in the rain", "One day I'll smile again"],
        verse2=["I keep the pictures on the wall", "I wish that I could hear you call",
                "{T}, you're in my heart", "Even though we're far apart"],
        bridge=["Time will heal, the sun will rise", "I'll see your light in morning skies"],
        intro=["Mm, mm", "Listen"], outro=["I still hear you in the rain", "One day"]),
    "kids": dict(
        hook="Clap your hands and sing along",
        verse1=["One, two, three, come and play", "It's a happy, sunny day",
                "Jump up high and touch the sky", "Wave your hands and say hi"],
        chorus=["Clap your hands and sing along", "Everybody join the song",
                "Clap your hands and sing along", "Together we are big and strong"],
        verse2=["Let's all sing about {t}", "Learning is a lot of fun",
                "Stomp your feet and turn around", "Make a happy, happy sound"],
        bridge=["La la la, la la la", "Ha ha ha, hooray"],
        intro=["Hello friends", "Are you ready"], outro=["Clap your hands and sing along", "Yay"]),
    "friends": dict(
        hook="We ride together, all the way",
        verse1=["From the classroom to the street", "My friends and me, we never cheat",
                "When I fall you pick me up", "We share the joy, we share the cup"],
        chorus=["We ride together, all the way", "Through every night and every day",
                "We ride together, all the way", "My friends forever, here to stay"],
        verse2=["Laughing loud on a boda ride", "With {t} right by my side",
                "No matter where the road may bend", "I know I always have a friend"],
        bridge=["Hands up if you got my back", "Hands up, we're on the right track"],
        intro=["Yeah, my people", "Let's go"], outro=["We ride together, all the way", "All the way"]),
    "party": dict(
        hook="Everybody move tonight",
        verse1=["The music's playing, feel the beat", "Kampala's dancing in the street",
                "Put your worries on the shelf", "Come on and dance and free yourself"],
        chorus=["Everybody move tonight", "Hands up, the vibe is right",
                "Everybody move tonight", "We go dancing till the light"],
        verse2=["We're singing about {t}", "We're here to party, have some fun",
                "Left foot, right foot, side to side", "Feel the rhythm, enjoy the ride"],
        bridge=["Drop it low and bring it back", "Genius on the music track"],
        intro=["Eh eh, yeah", "Let's go"], outro=["Everybody move tonight", "Tonight, eh"]),
    "hustle": dict(
        hook="I'm rising up, I won't stop",
        verse1=["Started from the bottom, little I had", "Turned every lesson, good and bad",
                "Late night reading, morning grind", "I keep the future on my mind"],
        chorus=["I'm rising up, I won't stop", "From the bottom to the top",
                "I'm rising up, I won't stop", "Working hard till the money drop"],
        verse2=["They said I'd never make it far", "Now I'm shining like a star",
                "{T} keeps me strong", "I've been ready all along"],
        bridge=["Step by step and day by day", "Nothing standing in my way"],
        intro=["Yeah, uh", "Listen"], outro=["I'm rising up, I won't stop", "Won't stop"]),
    "story": dict(
        hook="Listen, let me tell you a story",
        verse1=["In a village by the hill", "Lived a dreamer, quiet and still",
                "Every evening by the fire", "He sang a song of his desire"],
        chorus=["Listen, let me tell you a story", "Of the hard times and the glory",
                "Listen, let me tell you a story", "Of {t}, so don't you worry"],
        verse2=["Through the rain and through the sun", "He walked the road till it was done",
                "Now the people sing his name", "And nothing ever stayed the same"],
        bridge=["Every road has a turning", "Every heart has a learning"],
        intro=["Mm, gather round", "Listen"], outro=["Listen, let me tell you a story", "That's my story"]),
    "calm": dict(
        hook="Breathe in, let it go",
        verse1=["Rain is falling soft and slow", "Books are open, lights are low",
                "Every worry fades away", "Here's a quiet, gentle day"],
        chorus=["Breathe in, let it go", "Take it easy, take it slow",
                "Breathe in, let it go", "Let the peaceful feeling grow"],
        verse2=["Thinking softly of {t}", "Like the warmth of morning sun",
                "Step by step, the work gets done", "One by one, by one"],
        bridge=["Close your eyes and count to four", "Calm is waiting at the door"],
        intro=["Mm", "Relax"], outro=["Breathe in, let it go", "Slow"]),
}
_LYR_LG = {   # simple, common Luganda (a fluent speaker should check before sharing widely)
    "mum": dict(hook="Maama wange, nkwagala nnyo",
                verse1=["Maama wange, webale nnyo", "Wankuza bulungi, ndi musanyufu nnyo",
                        "Bwe nnali omulwadde wali nange", "Okwagala kwo kwe kunsanyusa"],
                chorus=["Maama wange, nkwagala nnyo", "Webale, webale nnyo",
                        "Maama wange, nkwagala nnyo", "Katonda akuwe emirembe"],
                bridge=["Webale okunkuza, maama", "Webale, maama wange"]),
    "praise": dict(hook="Katonda mulungi, bulijjo",
                   verse1=["Katonda mulungi, bulijjo", "Yesu ye Mukama, ayagala nze",
                           "Mu kizikiza ye musana gwange", "Tumutendereze ffenna leero"],
                   chorus=["Katonda mulungi, bulijjo", "Tumutendereze, tumutendereze",
                           "Katonda mulungi, bulijjo", "Aleluya, aleluya"],
                   bridge=["Ayi Mukama, webale", "Aleluya, Mukama webale"]),
    "love": dict(hook="Nkwagala nnyo, omukwano gwange",
                 verse1=["Bwe nkulaba omutima gubuuka", "Ggwe wange, ggwe wange bulijjo",
                         "Sijja kukuleka, sijja kukuleka", "Omukwano gwaffe gwa bulijjo"],
                 chorus=["Nkwagala nnyo, omukwano gwange", "Ggwe wange bulijjo",
                         "Nkwagala nnyo, omukwano gwange", "Sijja kukuleka"],
                 bridge=["Tuli wamu, tuli wamu", "Omukwano gwaffe gwa bulijjo"]),
    "party": dict(hook="Kale tujaguze, tuzine",
                  verse1=["Ennyimba zino zituyita", "Kampala yonna ezina leero",
                          "Ssa emikono waggulu", "Ffenna tuli wamu leero"],
                  chorus=["Kale tujaguze, tuzine", "Ssa emikono waggulu",
                          "Kale tujaguze, tuzine", "Essanyu lingi leero"],
                  bridge=["Tuzine, tuzine", "Essanyu, essanyu lingi"]),
    "generic": dict(hook="Tuli wamu, bulijjo",
                    verse1=["Leero tuyimba wamu", "Essanyu lingi mu mutima",
                            "Tukole nnyo, tuli wamu", "Ebirooto byaffe bijja"],
                    chorus=["Tuli wamu, bulijjo", "Webale, webale nnyo",
                            "Tuli wamu, bulijjo", "Katonda atukuume"],
                    bridge=["Tuli wamu, tuli wamu", "Bulijjo, bulijjo"]),
}
_LG_FAMILY = {"mum": "mum", "family": "mum", "praise": "praise", "love": "love", "sad": "love",
              "party": "party", "friends": "party"}
_LG_TOPIC = {"my mum": "maama wange", "mum": "maama", "my mom": "maama wange", "my mother": "maama wange",
             "my dad": "taata wange", "god": "Katonda", "jesus": "Yesu", "my friends": "mikwano gyange",
             "love": "omukwano", "uganda": "Uganda"}


def template_lyrics(req):
    fam = req.get("family") or "party"
    base = _LYR_EN.get(fam) or _LYR_EN.get("hustle" if fam == "home" else "party")
    default_topic = {"mum": "my mum", "praise": "Jesus", "love": "my love", "sad": "you", "kids": "the ABC",
                     "friends": "my friends", "family": "my family", "party": "the weekend",
                     "hustle": "my dream", "story": "a dreamer", "calm": "the quiet"}.get(fam, "life")
    t = (req.get("topic") or default_topic).strip()
    t = re.sub(r"^(a song|song)\s*", "", t) or default_topic
    T = t[:1].upper() + t[1:]
    fill = lambda lines: [ln.replace("{t}", t).replace("{T}", T) for ln in lines]
    L = {k: (fill(v) if isinstance(v, list) else v) for k, v in base.items()}
    lang = req.get("lang", "en")
    if lang in ("lg", "mix"):
        lg = _LYR_LG[_LG_FAMILY.get(fam, "generic")]
        if lang == "lg":
            L.update(verse1=list(lg["verse1"]), verse2=list(lg["verse1"][2:] + lg["verse1"][:2]),
                     chorus=list(lg["chorus"]), bridge=list(lg["bridge"]), hook=lg["hook"],
                     intro=["Eh, eh", _LG_TOPIC.get(t.lower(), t)], outro=[lg["hook"], "Webale nnyo"])
        else:                                       # English verses, Luganda hook
            L.update(chorus=list(lg["chorus"]), hook=lg["hook"], outro=[lg["hook"], L["outro"][-1]])
    L["title"] = L["hook"].strip()[:40]
    return L


_LYR_KEYS = (("intro", 2), ("verse1", 4), ("chorus", 4), ("verse2", 4), ("bridge", 2), ("outro", 2))


def ai_lyrics(req, plan):
    """Ask a connected AI to write the song. Returns a dict like template_lyrics, or None."""
    lang = {"en": "English", "lg": "Luganda (Oluganda) - simple, natural, correct Luganda",
            "mix": "English verses with a Luganda chorus/hook"}[req.get("lang", "en")]
    prompt = (
        "You are a hit songwriter from Uganda. Write an original, family-friendly song.\n"
        f"Genre: {plan['label']} ({plan['bpm']} BPM). Topic: {req.get('topic') or req.get('family')}. "
        f"Mood: {req.get('mood') or 'fits the genre'}. Language: {lang}.\n"
        "Rules: every line 5 to 10 syllables so it is easy to sing on one bar of music; "
        "simple everyday words; strong end rhymes (AABB or ABAB); the HOOK is a short catchy phrase (3-7 words); "
        "chorus lines 1 and 3 are exactly the hook; verses tell a small story with concrete images; "
        "bridge changes the feeling; outro repeats the hook. No profanity. No stage directions.\n"
        "Reply JSON only: {\"title\": str, \"hook\": str, \"intro\": [2 short ad-lib lines], "
        "\"verse1\": [4 lines], \"chorus\": [4 lines], \"verse2\": [4 lines], \"bridge\": [2 lines], "
        "\"outro\": [2 lines]}")
    try:
        r = ask_gemini(prompt, max_tokens=900, json_mode=True)
        j = json.loads(re.search(r"\{.*\}", r or "", re.S).group(0))
    except Exception as e:
        log(f"MUSIC lyrics AI: {e}")
        return None
    base = template_lyrics(req)
    out = {}
    for k, n in _LYR_KEYS:
        got = [re.sub(r"\s+", " ", str(x)).strip()[:70] for x in (j.get(k) or []) if str(x).strip()]
        out[k] = (got + base[k])[:n] if got else base[k]
    out["hook"] = str(j.get("hook") or out["chorus"][0])[:60]
    out["title"] = str(j.get("title") or out["hook"])[:50]
    return out


def music_plan(desc, use_ai=None):
    """Picks the genre from simple words, then tempo, key, scale, chords and instruments to fit it,
    and writes structured lyrics (AI if a key is connected, otherwise built-in templates)."""
    req = song_request(desc)
    st = _STYLES[req["style"]]
    plan = dict(st)
    plan.update(style=req["style"], chosen=req["chosen"], request=req)
    plan["bpm"] = st["bpm"] + _r.randint(-3, 3)
    plan["key"] = _r.choice(st["keys"])
    plan["prog"] = list(_r.choice(st["progs"]))
    if req["mood"] == "minor" and plan["scale"] == "major":
        plan["scale"] = "minor"
        plan["prog"] = [6, 4, 1, 5]
    elif req["mood"] == "major" and plan["scale"] in ("minor", "dorian"):
        plan["scale"], plan["prog"] = "major", [1, 5, 6, 4]
    if req["style"] == "hiphop" and "trap" in (desc or "").lower():
        plan["drums"] = "trap"
    if use_ai is None:
        try:
            use_ai = bool(connected_ais())
        except Exception:
            use_ai = False
    lyr = ai_lyrics(req, plan) if use_ai else None
    plan["lyrics_by"] = "AI" if lyr else "Genius templates"
    lyr = lyr or template_lyrics(req)
    plan["sections"] = {k: lyr[k] for k, _ in _LYR_KEYS}
    plan["hook"] = lyr["hook"]
    plan["title"] = lyr.get("title") or "Genius Song"
    plan["lyrics"] = "\n".join(lyr["chorus"])          # chorus text, as before
    return plan


def _syllables(line):
    words = re.findall(r"[a-zA-Z']+", line.lower())
    n = 0
    for w in words:
        k = len(re.findall(r"[aeiouy]+", w))
        if w.endswith("e") and k > 1 and not w.endswith(("le", "ee")):
            k -= 1
        n += max(1, k)
    return n or 4


def _line_melody(nsyl, chord, prev, seed, end_tonic=False):
    """One sung line on one bar: syllables -> 16th-note rhythm; chord tones on strong beats."""
    rnd = _r.Random(seed)
    n = max(3, min(12, nsyl))
    pos = sorted(set(int(round(i * 13.0 / max(1, n - 1))) for i in range(n)))
    if rnd.random() < 0.5 and pos and pos[0] == 0:
        pos[0] = 1 if 1 not in pos else 0                  # a little pickup/syncopation
        pos = sorted(set(pos))
    tones = sorted({(chord - 1 + k) % 7 + 1 for k in (0, 2, 4)})
    cands = [t + 7 * o for o in (0, 1) for t in tones]     # degrees 1..14 around the lead octave
    notes, cur = [], prev
    for i, p in enumerate(pos):
        last = i == len(pos) - 1
        if last and end_tonic:
            cur = min((1, 8), key=lambda c: abs(c - cur))
        elif p % 4 == 0 or last:
            cur = min(cands, key=lambda c: abs(c - cur) + rnd.random() * 1.5)
        else:
            cur = max(3, min(12, cur + rnd.choice((-1, -1, 1, 1, 2, -2, 0))))
        ln = (pos[i + 1] - p) if not last else (16 - p)
        notes.append((p, max(1, ln), cur))
    return notes, cur


def song_meta_path(wav):
    return os.path.splitext(wav)[0] + ".json"


def make_song(desc, plan=None, seconds_cb=None):
    """Compose, arrange and master a full song. Returns (wav path, plan). Also writes <song>.json
    with the lyrics and the time of every line for the karaoke view."""
    plan = plan or music_plan(desc)
    t_start = time.time()
    root = 48 + _NOTE.get(plan["key"].upper(), 0)
    if root > 53:
        root -= 12
    sc = _SCALES[plan["scale"]]
    deg = lambda d, base: base + 12 * ((d - 1) // 7) + sc[(d - 1) % 7]
    step = SR * 60.0 / plan["bpm"] / 4
    bar = step * 16
    nbars = sum(b for _, b in _FORM)
    total = int(bar * nbars + SR * 3.5)
    total += total % 2
    L, R, verb, dly = _buf(total), _buf(total), _buf(total), _buf(total)
    rnd = _r.Random()
    cos, sin, pi = _m.cos, _m.sin, _m.pi

    def hit(src, t, gain, pan=0.0, rev=0.0, delay=0.0, jit=0.004):
        p = int(t + rnd.uniform(-jit, jit) * SR)
        a = (pan + 1) * pi / 4
        if gain:
            _addm(L, src, p, gain * cos(a))
            _addm(R, src, p, gain * sin(a))
        if rev:
            _addm(verb, src, p, gain * rev)
        if delay:
            _addm(dly, src, p, gain * delay)

    pat = _PAT.get(plan["drums"], _PAT["pop"])
    swing = plan.get("swing", 0.0)
    cinst, binst, linst = plan["chords"], plan["bass"], plan["lead"]
    crh, brh = _CR.get(plan["crhythm"], _CR["sustain"]), _BR.get(plan["brhythm"], _BR["root8"])
    lead_base = root + 12 if linst not in ("violin", "flute", "bell", "marimba", "kora") else root + 24
    if linst == "organ":
        lead_base = root + 12
    lines_out = []
    prev_deg = 5
    bar_i = 0
    sections = plan.get("sections") or {}
    chorus_seen = 0
    for part, bars in _FORM:
        texts = list(sections.get(part) or [])
        is_ch = part == "chorus"
        if is_ch:
            chorus_seen += 1
        for b in range(bars):
            pos = bar * bar_i
            chord = plan["prog"][b % 4]
            ext = (0, 2, 4, 6) if plan.get("sevenths") else (0, 2, 4)
            voicing = []
            for k in ext:
                nt = deg(chord + k, root + 12)
                while nt > root + 26:
                    nt -= 12
                while nt < root + 9:
                    nt += 12
                voicing.append(nt)
            voicing.sort()
            energy = {"intro": 0.55, "verse1": 0.8, "verse2": 0.85, "chorus": 1.0, "bridge": 0.65, "outro": 0.6}[part]
            # ---- chords ----
            if crh == "arp":
                order = (0, 2, 1, 2, len(voicing) - 1, 2, 1, 2) if plan["crhythm"] == "fingerpick" else (0, 1, 2, 1, 0, 1, 2, len(voicing) - 1)
                for s in range(8):
                    nt = voicing[order[s] % len(voicing)] + (12 if s in (4,) and plan["crhythm"] == "fingerpick" else 0)
                    v = _voice(cinst, nt, int(step * 4))
                    hit(v, pos + s * 2 * step, 0.55 * energy * rnd.uniform(0.85, 1.0), -0.2 + 0.1 * (s % 3), rev=0.35)
                if plan["crhythm"] == "fingerpick" and part != "intro":
                    hit(_voice(cinst, voicing[0] - 12, int(step * 8)), pos, 0.35 * energy, 0.1, rev=0.2)
            else:
                strum = int(0.012 * SR if cinst == "guitar" else 0.004 * SR)
                for hi, (s, ln) in enumerate(crh):
                    if part == "intro" and hi % 2:
                        continue
                    up = cinst == "guitar" and hi % 2 == 1
                    notes = voicing[::-1] if up else voicing
                    vel = energy * (0.8 if up else 1.0) * rnd.uniform(0.85, 1.0)
                    v = _chord(cinst, notes, int(step * ln), strum)
                    hit(v, pos + (s + (swing if s % 2 else 0)) * step, 0.42 * vel, -0.25 if hi % 2 else -0.1, rev=0.3)
            # ---- pad ----
            if plan.get("pad") and part in ("intro", "chorus", "bridge", "outro"):
                v = _chord(plan["pad"], voicing[:3], int(bar))
                hit(v, pos, 0.26 * energy, -0.75, rev=0.5, jit=0)
                hit(v, pos + 400, 0.26 * energy, 0.75, jit=0)
            # ---- bass ----
            if part != "intro" or binst == "ksbass":
                bnote = deg(chord, root - 12)
                while bnote < 33:
                    bnote += 12
                pattern = brh if part not in ("bridge", "outro") else brh[:1]
                for s, ln, iv in pattern:
                    v = _voice(binst, bnote + iv, int(step * ln))
                    g = (0.5 if binst != "logdrum" else 0.45) * rnd.uniform(0.9, 1.0) * (1 if part != "intro" else 0.6)
                    hit(v, pos + (s + (swing if s % 2 else 0)) * step, g, 0.0, jit=0.002)
            # ---- arpeggio (chorus, and the 2nd half of verse 2) ----
            if plan.get("arp") and (is_ch or (part == "verse2" and b >= 2)):
                for s in range(0, 16, 2):
                    nt = voicing[(s // 2) % len(voicing)] + 12
                    v = _voice(plan["arp"], nt, int(step * 2))
                    hit(v, pos + (s + (swing if s % 2 else 0)) * step, 0.22 * rnd.uniform(0.8, 1.0),
                        0.55 if (s // 2) % 2 else 0.35, rev=0.3, delay=0.25)
            # ---- lead melody: "sings" the lyric line on this bar ----
            text = texts[b] if b < len(texts) else ""
            first = None
            if part in ("verse1", "verse2", "chorus", "bridge") or (part == "outro" and b == 0):
                seed = hash((plan["title"], part if part != "verse2" else "verse1", b % 4)) & 0xffff
                end_t = (is_ch and b == 3) or part == "outro"
                mel, prev_deg = _line_melody(_syllables(text) if text else 7, chord, prev_deg, seed, end_t)
                first = mel[0][0] if mel else 0
                for p, ln, dg in mel:
                    nt = deg(dg, lead_base)
                    v = _voice(linst, nt, int(step * min(ln, 6)))
                    g = (0.85 if is_ch else 0.72) * rnd.uniform(0.85, 1.0)
                    t = pos + (p + (swing if p % 2 else 0)) * step
                    hit(v, t, g, 0.05, rev=0.4, delay=0.18 if is_ch else 0.1, jit=0.008)
                    if is_ch and dg > 2:                     # backing "voice" a third below
                        hit(_voice(linst, deg(dg - 2, lead_base), int(step * min(ln, 6))), t, g * 0.4, -0.45,
                            rev=0.5, jit=0.012)
            if text:
                start = pos + (first or 0) * step
                lines_out.append(dict(t=round(max(0.0, start / SR - 0.15), 2), section=part, text=text))
            # ---- drums ----
            drum_on = part not in ("intro",) or b == bars - 1
            if part == "outro" and b > 0:
                drum_on = False
            if drum_on:
                for kind, row in pat.items():
                    if part == "intro" and kind not in ("hat", "shaker", "rim"):
                        continue
                    if part == "bridge" and kind in ("snare", "clap", "conga") and b == 0:
                        continue
                    if part.startswith("verse") and kind == "ohat":
                        continue
                    for s in range(16):
                        ch = row[s]
                        if ch not in "xo":
                            continue
                        if part == "bridge" and kind == "kick" and s % 8:
                            continue
                        vel = (1.0 if ch == "x" else 0.45) * rnd.uniform(0.82, 1.0) * (0.95 + 0.1 * (s % 4 == 0))
                        t = pos + (s + (swing if s % 2 else 0)) * step
                        src = _drum(kind, rnd.randrange(3) if kind not in ("kick",) else 0)
                        gain = {"kick": 0.72, "snare": 0.75, "clap": 0.7, "hat": 0.55, "ohat": 0.45,
                                "shaker": 0.6, "rim": 0.45, "conga": 0.5, "ngoma": 0.6, "tom": 0.6}.get(kind, 0.6)
                        hit(src, t, gain * vel, _PAN.get(kind, 0.0), rev=0.12 if kind in ("snare", "clap", "rim") else 0.0,
                            jit=0.002)
                # fill into each chorus
                nxt_ch = (b == bars - 1) and part in ("verse1", "verse2", "bridge")
                if nxt_ch:
                    fk = "snare" if "snare" in pat else ("clap" if "clap" in pat else "conga")
                    for s in range(12, 16):
                        hit(_drum(fk, s % 3), pos + s * step, 0.35 + 0.1 * (s - 12), 0.1, rev=0.15)
            if is_ch and b == 0:
                hit(_drum("crash"), pos, 0.55, -0.3, rev=0.2)
            bar_i += 1
    # ---- effects: delay (dotted 8th ping-pong) and reverb ----
    d = int(step * 3)
    echo = _comb(dly, d, 0.38)
    echo = _array.array("f", [a - b for a, b in zip(echo, dly)])       # only the echoes
    _addm(L, echo, 0, 0.35)
    _addm(R, echo, d // 2, 0.35)
    rl, rr = _reverb(verb)
    _addm(L, rl, 0, 0.11)
    _addm(R, rr, 0, 0.11)
    # ---- master: bus compression (block envelope), soft limiter, fades, 16-bit ----
    blk = 1024
    nb = (total + blk - 1) // blk
    peak = max(1e-6, max(max(L), -min(L), max(R), -min(R)))
    norm = 1.0 / peak
    gains, peaks, g = [], [], 1.0
    thr, ratio = 0.35, 3.0
    for bi in range(nb):
        s, e = bi * blk, min(total, (bi + 1) * blk)
        p = max(max(L[s:e]), -min(L[s:e]), max(R[s:e]), -min(R[s:e])) * norm
        want = (thr / p) ** (1 - 1 / ratio) if p > thr else 1.0
        g = want if want < g else g + (want - g) * 0.08          # fast attack, slow release
        gains.append(g)
        peaks.append(p * g)
    makeup = min(3.0, 1.0 / max(1e-6, max(peaks)))
    th = _m.tanh
    k = 0.92 * 32767
    fade_in, fade_out = int(0.4 * SR), int(3.0 * SR)
    pcm = _array.array("h")
    for bi in range(nb):
        s, e = bi * blk, min(total, (bi + 1) * blk)
        f = min(1.0, (s + 1) / fade_in, max(0.0, (total - s) / fade_out))
        gg = gains[bi] * norm * makeup * 1.15
        kk = k * f
        inter = [0] * (2 * (e - s))
        inter[0::2] = [int(th(x * gg) * kk) for x in L[s:e]]
        inter[1::2] = [int(th(x * gg) * kk) for x in R[s:e]]
        pcm.extend(inter)
    if _sys.byteorder != "little":
        pcm.byteswap()
    L = R = verb = dly = None          # free the mix buffers before writing
    _CACHE.clear()
    out = os.path.join(genius_dl("music"), re.sub(r"[^A-Za-z0-9]+", "_", plan["title"]).strip("_")[:40]
                       + time.strftime("_%H%M%S") + ".wav")
    with _wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    dur = round(total / float(SR), 2)
    for i, ln in enumerate(lines_out):
        ln["end"] = lines_out[i + 1]["t"] if i + 1 < len(lines_out) else dur
    if lines_out:
        lines_out[0]["t"] = 0.0
    meta = dict(title=plan["title"], style=plan["style"], label=plan.get("label", plan["style"]),
                chosen=plan.get("chosen", "genius"), key=plan["key"], scale=plan["scale"], bpm=plan["bpm"],
                instruments=list(dict.fromkeys(x for x in (cinst, binst, linst, plan.get("arp"), plan.get("pad")) if x)),
                lyrics_by=plan.get("lyrics_by", ""), hook=plan.get("hook", ""), duration=dur, lines=lines_out,
                made_in=round(time.time() - t_start, 1), version=VERSION)
    try:
        with open(song_meta_path(out), "w") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"MUSIC meta: {e}")
    plan["duration"], plan["meta"] = dur, meta
    return out, plan


def wav_seconds(path):
    try:
        with _wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def spread_lines(texts, duration):
    """Older songs have no timing: spread the lines evenly over the song."""
    texts = [t for t in texts if t.strip()] or ["~ instrumental ~"]
    n = len(texts)
    seg = max(0.5, duration) / n
    return [dict(t=round(i * seg, 2), end=round((i + 1) * seg, 2), section="", text=t) for i, t in enumerate(texts)]


def load_song_timeline(wav, plan=None):
    """(meta, lines) for the karaoke view; works for songs made before 109.5 too."""
    meta = {}
    try:
        with open(song_meta_path(wav)) as fh:
            meta = json.load(fh)
    except Exception:
        pass
    dur = float(meta.get("duration") or wav_seconds(wav) or 0)
    lines = meta.get("lines") or []
    if not lines or "t" not in lines[0]:
        texts = [l.get("text", "") if isinstance(l, dict) else str(l) for l in lines]
        if not any(texts) and plan and plan.get("lyrics"):
            texts = plan["lyrics"].split("\n")
        lines = spread_lines(texts, dur)
    meta.setdefault("title", os.path.splitext(os.path.basename(wav))[0].replace("_", " "))
    meta["duration"] = dur
    return meta, lines


def current_line(lines, pos):
    idx = -1
    for i, ln in enumerate(lines):
        if pos >= ln["t"]:
            idx = i
        else:
            break
    return idx


# ---------------- 111.9: Vocal studio (sing your song in your own voice) ----------------
VOCAL_SR = 44100
VOCAL_LATENCY = 0.12          # seconds the phone's mic runs behind the beat


class VocalRecorder:
    """Records the microphone to a mono 16-bit WAV with Android AudioRecord. .level is 0..1 for the meter."""

    def __init__(self):
        self.running = False
        self.level = 0.0
        self.error = ""
        self.path = ""
        self.seconds = 0.0
        self._th = None

    def start(self, path):
        self.path, self.running, self.error, self.level, self.seconds = path, True, "", 0.0, 0.0
        self._th = threading.Thread(target=self._run, daemon=True)
        self._th.start()

    def stop(self):
        self.running = False
        if self._th is not None:
            self._th.join(4)
        return self.path if os.path.exists(self.path) and self.seconds > 0.5 else None

    def _run(self):
        rec = None
        try:
            from jnius import autoclass
            AR = autoclass("android.media.AudioRecord")
            minb = AR.getMinBufferSize(VOCAL_SR, 16, 2)            # mono, 16-bit
            if minb <= 0:
                raise RuntimeError("this phone's microphone can't record at studio quality")
            rec = AR(1, VOCAL_SR, 16, 2, max(minb * 4, 32768))
            if rec.getState() != 1:
                raise RuntimeError("the microphone is busy or not allowed")
            rec.startRecording()
            chunk = bytearray(4410)                                 # 50 ms
            with _wave.open(self.path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(VOCAL_SR)
                total = 0
                while self.running:
                    n = rec.read(chunk, 0, len(chunk))
                    if n is None or n <= 0:
                        time.sleep(0.01)
                        continue
                    data = bytes(chunk[:n])
                    w.writeframes(data)
                    total += n
                    self.seconds = total / (2.0 * VOCAL_SR)
                    self.level = min(1.0, _pcm_rms(data) / 9000.0)
        except Exception as e:
            self.error = str(e) or type(e).__name__
            log(f"VOCAL record failed: {self.error}")
        finally:
            self.running = False
            try:
                if rec is not None:
                    rec.stop()
                    rec.release()
            except Exception:
                pass


def _pcm_rms(data):
    try:
        import audioop
        return audioop.rms(data, 2)
    except Exception:
        a = _array.array("h", data[: len(data) // 2 * 2])
        if not a:
            return 0
        step = max(1, len(a) // 400)
        v = a[::step]
        return (sum(x * x for x in v) / len(v)) ** 0.5


def mix_vocals(beat_wav, vocal_wav, out_wav, vocal_gain=1.0, beat_gain=0.55, latency=None):
    """Put the recorded voice on top of the beat with a little room echo. Returns out_wav."""
    with _wave.open(beat_wav, "rb") as w:
        bch, bsr = w.getnchannels(), w.getframerate()
        beat = w.readframes(w.getnframes())
    with _wave.open(vocal_wav, "rb") as w:
        voc = w.readframes(w.getnframes())
    cut = int((VOCAL_LATENCY if latency is None else latency) * VOCAL_SR) * 2
    voc = voc[cut:] if len(voc) > cut else voc
    try:
        import audioop
        voc = audioop.bias(voc, 2, -int(audioop.avg(voc, 2)))          # remove mic hum offset
        peak = max(1, audioop.max(voc, 2))
        voc = audioop.mul(voc, 2, min(8.0, 0.72 * 32767 / peak) * vocal_gain)
        d = int(0.085 * VOCAL_SR) * 2                                    # small room echo
        echo = b"\x00" * d + audioop.mul(voc, 2, 0.22)[:max(0, len(voc) - d)]
        voc = audioop.add(voc, echo[:len(voc)], 2)
        if bsr != VOCAL_SR:
            voc, _ = audioop.ratecv(voc, 2, 1, VOCAL_SR, bsr, None)
        vs = audioop.tostereo(voc, 2, 1, 1) if bch == 2 else voc
        beat = audioop.mul(beat, 2, beat_gain)
        n = max(len(beat), len(vs))
        beat += b"\x00" * (n - len(beat))
        vs += b"\x00" * (n - len(vs))
        mixed = audioop.add(beat, vs, 2)
    except ImportError:
        b = _array.array("h", beat)
        v = _array.array("h", voc)
        peak = max(1, max(v, default=1), -min(v, default=-1))
        g = min(8.0, 0.72 * 32767 / peak) * vocal_gain
        d = int(0.085 * VOCAL_SR)
        n = max(len(b), len(v) * bch)
        b.extend([0] * (n - len(b)))
        out = _array.array("h", bytes(2 * n))
        for i in range(n):
            j = i // bch
            x = v[j] if j < len(v) else 0
            e = v[j - d] if d <= j < len(v) + d else 0
            y = b[i] * beat_gain + (x + 0.22 * e) * g
            out[i] = 32767 if y > 32767 else -32768 if y < -32768 else int(y)
        mixed = out.tobytes()
    with _wave.open(out_wav, "wb") as w:
        w.setnchannels(bch)
        w.setsampwidth(2)
        w.setframerate(bsr)
        w.writeframes(mixed)
    try:                                                     # keep the lyrics so karaoke still works
        meta, lines = load_song_timeline(beat_wav)
        meta = dict(meta, title=meta.get("title", "My song") + " (my voice)", lines=lines,
                    duration=round(len(mixed) / (2.0 * bch * bsr), 2), sung_by="you")
        with open(song_meta_path(out_wav), "w") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"VOCAL meta: {e}")
    return out_wav


# ---------------- 112.1: AI sings the song in YOUR voice (ElevenLabs voice clone, user's own key) ----------------
ELEVEN_KEY_FILE = os.path.join(ROOT, "eleven_key.txt")
ELEVEN_VOICE_FILE = os.path.join(ROOT, "eleven_voice.txt")
ELEVEN_API = "https://api.elevenlabs.io/v1"


def eleven_key():
    try:
        return open(ELEVEN_KEY_FILE).read().strip() or None
    except Exception:
        return None


def eleven_voice():
    try:
        return open(ELEVEN_VOICE_FILE).read().strip() or None
    except Exception:
        return None


def _eleven_err(e):
    try:
        body = e.read().decode("utf-8", "ignore")
        msg = json.loads(body).get("detail")
        msg = msg.get("message") if isinstance(msg, dict) else msg
    except Exception:
        msg = ""
    code = getattr(e, "code", 0)
    if code == 401:
        return "ElevenLabs didn't accept your key. Type seteleven and your key again."
    if code in (402, 403) or "subscription" in str(msg).lower() or "upgrade" in str(msg).lower():
        return "Your ElevenLabs plan doesn't include voice cloning. The Starter plan has it."
    if code == 429 or "quota" in str(msg).lower():
        return "Your ElevenLabs credits are used up for this month."
    return f"ElevenLabs said: {msg or code or e}"


def eleven_clone(sample_wav, name="Genius - my voice"):
    """Upload the voice sample, make an instant voice clone, save its id. Returns voice id."""
    key = eleven_key()
    if not key:
        raise RuntimeError("Add your ElevenLabs key first: type seteleven, a space, then the key.")
    bnd = "----genius" + hashlib.sha1(str(time.time()).encode()).hexdigest()[:16]
    audio = open(sample_wav, "rb").read()
    parts = [f'--{bnd}\r\nContent-Disposition: form-data; name="name"\r\n\r\n{name}\r\n'.encode(),
             f'--{bnd}\r\nContent-Disposition: form-data; name="remove_background_noise"\r\n\r\ntrue\r\n'.encode(),
             f'--{bnd}\r\nContent-Disposition: form-data; name="files"; filename="voice.wav"\r\n'
             f'Content-Type: audio/wav\r\n\r\n'.encode() + audio + b"\r\n",
             f"--{bnd}--\r\n".encode()]
    req = urllib.request.Request(ELEVEN_API + "/voices/add", data=b"".join(parts), method="POST",
                                 headers={"xi-api-key": key, "Content-Type": "multipart/form-data; boundary=" + bnd})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=120, context=ssl_context()))
    except urllib.error.HTTPError as e:
        raise RuntimeError(_eleven_err(e))
    vid = r.get("voice_id")
    if not vid:
        raise RuntimeError("ElevenLabs didn't return a voice. Try again.")
    old = eleven_voice()
    open(ELEVEN_VOICE_FILE, "w").write(vid)
    if old and old != vid:                                      # don't fill the user's voice slots
        try:
            urllib.request.urlopen(urllib.request.Request(ELEVEN_API + "/voices/" + old, method="DELETE",
                                                          headers={"xi-api-key": key}), timeout=20, context=ssl_context())
        except Exception:
            pass
    return vid


def _eleven_line(text, prev="", nxt=""):
    """One lyric line in the user's cloned voice as mono 16-bit PCM at 22050 Hz."""
    key, vid = eleven_key(), eleven_voice()
    tries = [("eleven_v3", "[sings] " + text), ("eleven_multilingual_v2", text)]
    if ELEVEN_STATE.get("model") == "eleven_multilingual_v2":
        tries = tries[1:]
    last = None
    for model, words in tries:
        body = {"text": words, "model_id": model,
                "voice_settings": {"stability": 0.35, "similarity_boost": 0.9, "style": 0.6, "use_speaker_boost": True}}
        if model != "eleven_v3":
            body.update(previous_text=prev, next_text=nxt)
        req = urllib.request.Request(ELEVEN_API + f"/text-to-speech/{vid}?output_format=pcm_22050",
                                     data=json.dumps(body).encode(), method="POST",
                                     headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            data = urllib.request.urlopen(req, timeout=90, context=ssl_context()).read()
            ELEVEN_STATE["model"] = model
            return data
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 402, 429):
                break
    raise RuntimeError(_eleven_err(last) if last is not None else "ElevenLabs failed.")


ELEVEN_STATE = {}


def ai_sing_song(beat_wav, progress=None):
    """Your voice clone performs every lyric line at its place in the song, mixed onto the beat. Returns path."""
    import audioop
    if not eleven_key() or not eleven_voice():
        raise RuntimeError("Set up your voice clone first: say clone my voice.")
    meta, lines = load_song_timeline(beat_wav)
    sung = [ln for ln in lines if ln.get("text", "").strip() and not ln["text"].strip().startswith("~")
            and not re.match(r"^\(?\[?(verse|chorus|bridge|intro|outro|hook)\b", ln["text"].strip(), re.I)]
    if not sung:
        raise RuntimeError("This song has no words to sing.")
    total = int((meta.get("duration") or wav_seconds(beat_wav)) * VOCAL_SR) + VOCAL_SR * 4
    track = bytearray(total * 2)
    pos_free = 0
    for i, ln in enumerate(sung):
        if progress:
            progress(i, len(sung))
        pcm = _eleven_line(ln["text"].strip(), sung[i - 1]["text"] if i else "",
                           sung[i + 1]["text"] if i + 1 < len(sung) else "")
        pcm, _ = audioop.ratecv(pcm, 2, 1, 22050, VOCAL_SR, None)
        start = max(int(ln["t"] * VOCAL_SR), pos_free) * 2
        end = min(len(track), start + len(pcm))
        if start >= len(track):
            break
        seg = bytes(track[start:end])
        track[start:end] = audioop.add(seg, pcm[:end - start], 2)
        pos_free = end // 2
    tmp = os.path.join(genius_dl("music"), "ai_vocals_" + time.strftime("%H%M%S") + ".wav")
    with _wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(VOCAL_SR)
        w.writeframes(bytes(track[:pos_free * 2 + VOCAL_SR * 2]))
    out = os.path.splitext(beat_wav)[0][:60] + "_ai_my_voice_" + time.strftime("%H%M%S") + ".wav"
    mix_vocals(beat_wav, tmp, out, latency=0.0)
    return out


def eleven_music_song(desc):
    """112.2: a full song WITH a real singing voice from ElevenLabs Music, using Genius's own words.
    Returns (mp3 path, plan)."""
    key = eleven_key()
    if not key:
        raise RuntimeError("Add your ElevenLabs key first: type seteleven, a space, then the key.")
    plan = music_plan(desc)
    secs = plan.get("sections", {})
    beat = 60000.0 / max(60, plan.get("bpm", 100))
    line_ms = int(beat * 8)
    order = [("Intro", "intro", True), ("Verse 1", "verse1", False), ("Chorus", "chorus", False),
             ("Verse 2", "verse2", False), ("Chorus", "chorus", False), ("Bridge", "bridge", False),
             ("Chorus", "chorus", False), ("Outro", "outro", False)]
    lang = plan.get("request", {}).get("lang", "en")
    voice_lang = {"lg": "Luganda vocals", "mix": "Luganda and English vocals"}.get(lang, "English vocals")
    label = plan.get("label", plan.get("style", "afrobeat"))
    glob = [label, f"{plan.get('bpm')} bpm", voice_lang, "East African", "catchy melody", "clear lead vocals",
            "great production quality"]
    sections, timeline, t = [], [], 0
    for name, k, inst in order:
        lines = [] if inst else [str(x)[:190] for x in secs.get(k, []) if str(x).strip()][:12]
        dur = max(6000, min(110000, len(lines) * line_ms or int(beat * 16)))
        sections.append({"section_name": name, "positive_local_styles": ["instrumental"] if inst else [],
                         "negative_local_styles": [], "duration_ms": dur, "lines": lines})
        if lines:
            step = dur / float(len(lines))
            for i, ln in enumerate(lines):
                timeline.append({"t": round((t + i * step) / 1000.0, 2), "section": name, "text": ln})
        t += dur
    body = {"model_id": "music_v1", "composition_plan": {
        "positive_global_styles": glob, "negative_global_styles": ["low quality", "distorted"], "sections": sections}}
    req = urllib.request.Request(ELEVEN_API + "/music?output_format=mp3_44100_128", data=json.dumps(body).encode(),
                                 method="POST", headers={"xi-api-key": key, "Content-Type": "application/json"})
    try:
        audio = urllib.request.urlopen(req, timeout=420, context=ssl_context()).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(_eleven_err(e))
    if len(audio) < 20000:
        raise RuntimeError("ElevenLabs sent back an empty song. Try again.")
    out = os.path.join(genius_dl("music"), re.sub(r"[^A-Za-z0-9]+", "_", plan["title"]).strip("_")[:40]
                       + time.strftime("_%H%M%S") + "_sung.mp3")
    open(out, "wb").write(audio)
    dur = round(t / 1000.0, 2)
    for i, ln in enumerate(timeline):
        ln["end"] = timeline[i + 1]["t"] if i + 1 < len(timeline) else dur
    meta = dict(title=plan["title"], style=plan["style"], label=label, chosen=plan.get("chosen", "genius"),
                key=plan.get("key", ""), scale=plan.get("scale", ""), bpm=plan.get("bpm"),
                instruments=["ElevenLabs singer and band"], lyrics_by=plan.get("lyrics_by", ""), duration=dur,
                lines=timeline, made_by="ElevenLabs Music", version=VERSION)
    try:
        with open(song_meta_path(out), "w") as fh:
            json.dump(meta, fh, ensure_ascii=False, indent=1)
    except Exception as e:
        log(f"MUSIC meta: {e}")
    plan["duration"], plan["meta"] = dur, meta
    return out, plan


def newest_song():
    try:
        d = genius_dl("music")
        wavs = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".wav", ".mp3"))
                and not f.startswith(("vocals_", "ai_vocals_", "voice_sample"))]
        return max(wavs, key=os.path.getmtime) if wavs else None
    except Exception:
        return None


def ultra_process(im):
    """Genius Ultra engine: smart white balance, HDR tone mapping, clarity, fine detail,
    vibrance and noise clean-up. Never moves, crops or reshapes anything."""
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageStat, ImageChops
    im = im.convert("RGB")
    # 1. Smart white balance (gentle gray-world, so skin stays natural)
    r, g, b = ImageStat.Stat(im).mean
    avg = (r + g + b) / 3 or 1
    chans = []
    for c, m in zip(im.split(), (r, g, b)):
        f = 1 + ((avg / (m or 1)) - 1) * 0.6
        f = max(0.85, min(1.18, f))
        chans.append(c.point(lambda v, f=f: min(255, int(v * f))))
    im = Image.merge("RGB", chans)
    # 2. Noise clean-up in dark photos
    lum = ImageStat.Stat(im.convert("L")).mean[0]
    if lum < 90:
        im = Image.blend(im, im.filter(ImageFilter.MedianFilter(3)), 0.5)
    # 3. HDR tone mapping: lift shadows, protect highlights (local, via blurred luminance mask)
    L = im.convert("L")
    mask = L.filter(ImageFilter.GaussianBlur(max(4, im.size[0] // 60)))
    lift = 1.35 if lum < 110 else 1.2
    bright = im.point(lambda v: min(255, int(255 * ((v / 255) ** (1 / lift)))))
    shadow_mask = ImageOps.invert(mask).point(lambda v: int(v * 0.75))
    im = Image.composite(bright, im, shadow_mask)
    calm = im.point(lambda v: int(v if v < 200 else 200 + (v - 200) * 0.7))
    hi_mask = mask.point(lambda v: 0 if v < 170 else min(255, (v - 170) * 3))
    im = Image.composite(calm, im, hi_mask)
    # 4. Clarity (local contrast) + fine detail
    im = im.filter(ImageFilter.UnsharpMask(radius=max(8, im.size[0] // 120), percent=35, threshold=3))
    im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=90, threshold=2))
    # 5. Vibrance: boost muted colours more than strong ones, keep skin natural
    sat = ImageEnhance.Color(im).enhance(1.22)
    s_chan = im.convert("HSV").split()[1]
    v_mask = ImageOps.invert(s_chan).point(lambda v: int(v * 0.8))
    im = Image.composite(sat, im, v_mask)
    # 6. Final polish: depth contrast, true blacks
    im = ImageOps.autocontrast(im, cutoff=0.4)
    im = ImageEnhance.Contrast(im).enhance(1.06)
    return im


def ultra_hd(path):
    im = _open_rgb(path)
    out = fun_out("ultra")
    ultra_process(im).save(out, quality=97, subsampling=0)
    return out, "Genius Ultra done: HDR, true colour, clarity and fine detail - same photo, just better."


def super_zoom(path, zoom, cx=0.5, cy=0.5):
    """Digital zoom 1x-100x with smart sharpening: crop the centre, upscale cleanly, remove noise."""
    from PIL import Image, ImageFilter, ImageEnhance, ImageOps
    im = _open_rgb(path)
    zoom = max(1.0, min(100.0, float(zoom)))
    W, H = im.size
    cw, ch = max(8, int(W / zoom)), max(8, int(H / zoom))
    x0 = int(min(max(cx * W - cw / 2, 0), W - cw))
    y0 = int(min(max(cy * H - ch / 2, 0), H - ch))
    crop = im.crop((x0, y0, x0 + cw, y0 + ch))
    if zoom >= 4:
        crop = crop.filter(ImageFilter.MedianFilter(3))           # clean noise before enlarging
    tw = min(max(W, 1080), 3000)
    th = int(tw * ch / cw)
    big = crop
    while big.size[0] * 2 < tw:                                   # step up gently for cleaner edges
        big = big.resize((big.size[0] * 2, big.size[1] * 2), Image.LANCZOS)
        big = big.filter(ImageFilter.UnsharpMask(2, 60, 2))
    big = big.resize((tw, th), Image.LANCZOS)
    big = big.filter(ImageFilter.UnsharpMask(3, 110 if zoom < 10 else 150, 2))
    big = ultra_process(big)
    out = fun_out(f"zoom{int(zoom)}x")
    big.save(out, quality=97, subsampling=0)
    return out, f"{zoom:g}x zoom done."


def beautify(path):
    from PIL import ImageOps, ImageEnhance, ImageFilter
    im = _open_rgb(path)
    im.thumbnail((4096, 4096))
    im = ImageOps.autocontrast(im, cutoff=1)
    im = ImageEnhance.Color(im).enhance(1.18)
    im = ImageEnhance.Brightness(im).enhance(1.04)
    im = im.filter(ImageFilter.UnsharpMask(2, 90, 3))
    out = fun_out("beautiful")
    im.save(out, quality=94)
    return out, "Made it brighter, sharper and more colourful."


# ---------------- 111.3 Genius Eye: offline smart beauty camera ----------------
def face_boxes(path, max_faces=5):
    """Find faces with Android's built-in face finder. Returns [(cx, cy, r)] in the picture's pixels, or []."""
    try:
        from jnius import autoclass
        from PIL import Image
        im = _open_rgb(path)
        W, H = im.size
        sc = min(1.0, 640.0 / max(W, H))
        w, h = int(W * sc) // 2 * 2, int(H * sc)
        small = im.resize((w, h))
        tmp = os.path.join(genius_dl("fun"), "_face.png")
        small.save(tmp)
        BF = autoclass("android.graphics.BitmapFactory")
        Opt = autoclass("android.graphics.BitmapFactory$Options")
        Cfg = autoclass("android.graphics.Bitmap$Config")
        o = Opt()
        o.inPreferredConfig = Cfg.RGB_565
        bmp = BF.decodeFile(tmp, o)
        FD = autoclass("android.media.FaceDetector")
        Face = autoclass("android.media.FaceDetector$Face")
        det = FD(bmp.getWidth(), bmp.getHeight(), max_faces)
        faces = [None] * max_faces
        n = det.findFaces(bmp, faces)          # pyjnius copies the found faces back into the list
        PointF = autoclass("android.graphics.PointF")
        out = []
        for i in range(n):
            f = faces[i]
            if f is None or f.confidence() < 0.3:
                continue
            p = PointF()
            f.getMidPoint(p)
            d = f.eyesDistance()
            out.append((p.x / sc, p.y / sc, d * 1.6 / sc))
        try:
            os.remove(tmp)
        except Exception:
            pass
        return out
    except Exception as e:
        log(f"FACES: {type(e).__name__}: {e}")
        return []


def _skin_mask(im):
    """White where the colour looks like skin (any skin tone), soft edges."""
    from PIL import Image, ImageFilter
    y, cb, cr = im.convert("YCbCr").split()
    cbm = cb.point(lambda v: 255 if 77 <= v <= 130 else 0)
    crm = cr.point(lambda v: 255 if 133 <= v <= 178 else 0)
    ym = y.point(lambda v: 255 if v > 35 else 0)
    from PIL import ImageChops
    m = ImageChops.multiply(ImageChops.multiply(cbm, crm), ym)
    m = m.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(5))
    return m.filter(ImageFilter.GaussianBlur(max(2, im.width // 300)))


def genius_eye(path, mode="natural", faces=None):
    """Smart beauty: smooth skin but keep eyes, hair and edges sharp; even, glowing skin tone; HDR light;
    vivid but true colours. mode: natural | glam | portrait."""
    from PIL import Image, ImageOps, ImageEnhance, ImageFilter, ImageChops, ImageDraw
    im = _open_rgb(path)
    im.thumbnail((2000, 2000))
    W, H = im.size
    if faces is None:
        faces = face_boxes(path)
        if faces:
            sw, sh = _open_rgb(path).size
            k = W / float(sw)
            faces = [(x * k, y * k, r * k) for x, y, r in faces]
    glam = mode == "glam"
    # 1. light: lift shadows, protect highlights, gentle auto-contrast (HDR feel)
    im = ImageOps.autocontrast(im, cutoff=0.2, preserve_tone=True) if "preserve_tone" in \
        ImageOps.autocontrast.__code__.co_varnames else ImageOps.autocontrast(im, cutoff=0.2)
    lum = im.convert("L")
    shadows = lum.point(lambda v: int(max(0, 120 - v) * 1.4))
    lifted = ImageEnhance.Brightness(im).enhance(1.22)
    im = Image.composite(lifted, im, shadows.filter(ImageFilter.GaussianBlur(W // 60 or 2)))
    # 2. skin: edge-aware smoothing only on skin, details kept
    mask = _skin_mask(im)
    if faces:          # trust the face finder: always include the faces, soften skin elsewhere less
        fm = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(fm)
        for x, y, r in faces:
            d.ellipse((x - r, y - r * 1.25, x + r, y + r * 1.35), fill=255)
        fm = fm.filter(ImageFilter.GaussianBlur(max(4, W // 80)))
        mask = ImageChops.multiply(mask, ImageChops.add(fm, Image.new("L", (W, H), 90)))
    # 2a. spot remover: small dark dots on skin (pimples, spots) are filled from the skin around them
    L = im.convert("L")
    k = 9 if W > 1400 else 7 if W > 700 else 5
    around = L.filter(ImageFilter.MedianFilter(k))
    spots = ImageChops.subtract(around, L).point(lambda v: 255 if v > (7 if glam else 10) else 0) \
        .filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1))
    spots = ImageChops.multiply(spots, mask)
    im = Image.composite(im.filter(ImageFilter.MedianFilter(k)), im, spots)
    rad = max(2, W // (260 if glam else 340))
    med = 7 if W > 1400 else 5 if W > 700 else 3
    smooth = im.filter(ImageFilter.MedianFilter(med)).filter(ImageFilter.MedianFilter(med)) \
        .filter(ImageFilter.GaussianBlur(rad))                                  # spots and pimples melt away
    # keep only BIG lines sharp (eyes, brows, lips, nose, hair edge); small spots don't count as edges
    big = im.convert("L").filter(ImageFilter.GaussianBlur(max(1, W // 450)))
    edges = big.filter(ImageFilter.FIND_EDGES).point(lambda v: min(255, v * 6)).filter(ImageFilter.MaxFilter(5)) \
        .point(lambda v: 0 if v > 55 else 255).filter(ImageFilter.GaussianBlur(max(2, W // 400)))
    strength = 0.85 if glam else 0.70
    m = ImageChops.multiply(mask, edges).point(lambda v: int(v * strength))
    im = Image.composite(smooth, im, m)
    # 3. glowing, even skin tone (a touch brighter and warmer on skin only)
    glow = ImageEnhance.Brightness(im).enhance(1.10 if glam else 1.06)
    r, g, b = glow.split()
    glow = Image.merge("RGB", (r.point(lambda v: min(255, v + 6)), g.point(lambda v: min(255, v + 2)), b))
    im = Image.composite(glow, im, mask.point(lambda v: int(v * 0.7)))
    # 4. eyes and details: clarity + sharpen everything that is not smooth skin
    sharp = im.filter(ImageFilter.UnsharpMask(radius=max(2, W // 600), percent=60, threshold=4))
    im = Image.composite(im, sharp, mask)                 # sharpen eyes, hair, clothes - never the skin
    clar = im.filter(ImageFilter.UnsharpMask(radius=max(8, W // 60), percent=20, threshold=0))
    im = Image.blend(im, clar, 0.3)
    # 5. colour: vibrant but natural
    im = ImageEnhance.Color(im).enhance(1.14 if glam else 1.08)
    if glam:
        soft = im.filter(ImageFilter.GaussianBlur(max(3, W // 120)))
        im = ImageChops.screen(im, soft.point(lambda v: int(v * 0.22)))
    # 6. portrait: blur the background behind the faces (or the centre if no face was found)
    if mode == "portrait":
        pm = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(pm)
        spots = faces or [(W / 2, H * 0.42, min(W, H) * 0.22)]
        for x, y, rr in spots:
            d.ellipse((x - rr * 1.7, y - rr * 1.9, x + rr * 1.7, y + rr * 5), fill=255)
        pm = pm.filter(ImageFilter.GaussianBlur(max(10, W // 25)))
        bg = im.filter(ImageFilter.GaussianBlur(max(6, W // 70)))
        im = Image.composite(im, bg, pm)
    out = fun_out("genius_eye_" + mode)
    im.save(out, quality=95, subsampling=0)
    who = f"{len(faces)} face{'s' if len(faces) != 1 else ''} found. " if faces else ""
    msg = {"natural": "Genius Eye: smooth glowing skin, sharp eyes, better light.",
           "glam": "Genius Eye Glam: extra smooth skin and a soft glow.",
           "portrait": "Genius Eye Portrait: you sharp, background softly blurred."}.get(mode, "Genius Eye done.")
    return out, who + msg


# ---------------- 111.1 save to gallery / files, share a picture ----------------
_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif",
         ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".pdf": "application/pdf",
         ".txt": "text/plain"}


def save_media(path, where="gallery"):
    """Copy a Genius creation into the phone's Gallery (Pictures/Genius) or Files (Download/Genius).
    Returns (content_uri_or_path, message)."""
    import shutil
    if not path or not os.path.exists(path):
        return None, "I couldn't find that file. Make it again, then save."
    ext = os.path.splitext(path)[1].lower()
    mime = _MIME.get(ext, "application/octet-stream")
    name = "Genius_" + time.strftime("%Y%m%d_%H%M%S") + ext
    kind = mime.split("/")[0]
    try:
        from jnius import autoclass
        CV = autoclass("android.content.ContentValues")
        cr = autoclass("org.kivy.android.PythonActivity").mActivity.getContentResolver()
        if android_sdk() >= 29:
            if where == "files":
                coll, rel = autoclass("android.provider.MediaStore$Downloads").EXTERNAL_CONTENT_URI, "Download/Genius"
            elif kind == "video":
                coll, rel = autoclass("android.provider.MediaStore$Video$Media").EXTERNAL_CONTENT_URI, "Movies/Genius"
            elif kind == "audio":
                coll, rel = autoclass("android.provider.MediaStore$Audio$Media").EXTERNAL_CONTENT_URI, "Music/Genius"
            elif kind == "image":
                coll, rel = autoclass("android.provider.MediaStore$Images$Media").EXTERNAL_CONTENT_URI, "Pictures/Genius"
            else:
                coll, rel = autoclass("android.provider.MediaStore$Downloads").EXTERNAL_CONTENT_URI, "Download/Genius"
            cv = CV()
            cv.put("_display_name", name)
            cv.put("mime_type", mime)
            cv.put("relative_path", rel)
            uri = cr.insert(coll, cv)
            out = cr.openOutputStream(uri)
            try:
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        out.write(bytearray(chunk), 0, len(chunk))
            finally:
                out.close()
            place = "your Gallery (Genius album)" if where != "files" and kind in ("image", "video") else \
                    ("Music > Genius" if where != "files" and kind == "audio" else "Files > Download > Genius")
            return uri, f"Saved to {place}."
        # older Android: plain copy, then tell the gallery about it
        base = "/storage/emulated/0/" + ("Download/Genius" if where == "files" else
                                         {"video": "Movies/Genius", "audio": "Music/Genius"}.get(kind, "Pictures/Genius"))
        os.makedirs(base, exist_ok=True)
        dest = os.path.join(base, name)
        shutil.copyfile(path, dest)
        try:
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            File = autoclass("java.io.File")
            i = Intent(Intent.ACTION_MEDIA_SCANNER_SCAN_FILE, Uri.fromFile(File(dest)))
            autoclass("org.kivy.android.PythonActivity").mActivity.sendBroadcast(i)
        except Exception:
            pass
        return dest, f"Saved to {nice_where(dest)}."
    except Exception as e:
        log(f"SAVE media: {type(e).__name__}: {e}")
        return None, "I couldn't save it. Allow Genius to use storage, then try again."


def share_media(path):
    """Send a picture, song or video to WhatsApp, TikTok, Facebook... (saves it to the gallery first)."""
    uri, msg = save_media(path, "gallery")
    if uri is None:
        return False
    try:
        from jnius import autoclass, cast
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        Intent = autoclass("android.content.Intent")
        if isinstance(uri, str):
            uri = autoclass("android.net.Uri").fromFile(autoclass("java.io.File")(uri))
        i = Intent(Intent.ACTION_SEND)
        i.setType(_MIME.get(os.path.splitext(path)[1].lower(), "*/*"))
        i.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
        i.putExtra(Intent.EXTRA_TEXT, "Made with Genius")
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        ch = Intent.createChooser(i, "Share")
        ch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        act.startActivity(ch)
        return True
    except Exception as e:
        log(f"SHARE media: {type(e).__name__}: {e}")
        return False


def fun_out(prefix, ext=".jpg"):
    return os.path.join(genius_dl("fun"), f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}{ext}")


def _open_rgb(path):
    from PIL import Image, ImageOps
    im = Image.open(path)
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    return im.convert("RGB")


def make_collage(paths):
    """Put 2-12 pictures together in a neat grid and save it."""
    from PIL import Image, ImageOps
    paths = [p for p in paths if p and os.path.exists(p)][:12]
    if len(paths) < 2:
        return None, "Choose at least 2 pictures for a collage."
    n = len(paths)
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    tile, gap = 540, 12
    W, H = cols * tile + (cols + 1) * gap, rows * tile + (rows + 1) * gap
    canvas = Image.new("RGB", (W, H), (18, 20, 28))
    for i, p in enumerate(paths):
        try:
            im = ImageOps.fit(_open_rgb(p), (tile, tile))
        except Exception:
            continue
        r, c = divmod(i, cols)
        if r == rows - 1 and n % cols:            # centre the last short row
            c += (cols - n % cols) / 2.0
        canvas.paste(im, (int(gap + c * (tile + gap)), gap + r * (tile + gap)))
    out = fun_out("collage")
    canvas.save(out, quality=90)
    return out, f"Collage of {n} pictures made."


def transform_image(path, style):
    from PIL import Image, ImageOps, ImageFilter, ImageEnhance, ImageChops
    im = _open_rgb(path)
    im.thumbnail((4096, 4096))
    st = style.lower()
    if st == "hd clear":
        im = ImageEnhance.Contrast(im.filter(ImageFilter.UnsharpMask(2, 120, 2))).enhance(1.08)
        im = ImageEnhance.Color(im).enhance(1.12)
    elif st == "warm":
        r, g, b = im.split()
        im = Image.merge("RGB", (r.point(lambda x: min(255, int(x * 1.10 + 8))), g.point(lambda x: min(255, int(x * 1.03))),
                                 b.point(lambda x: int(x * 0.88))))
    elif st == "cool":
        r, g, b = im.split()
        im = Image.merge("RGB", (r.point(lambda x: int(x * 0.9)), g.point(lambda x: min(255, int(x * 1.02))),
                                 b.point(lambda x: min(255, int(x * 1.12 + 8)))))
    elif "teal" in st or st == "cinematic":
        g = ImageOps.grayscale(im)
        tone = ImageOps.colorize(g, (10, 60, 70), (255, 190, 120))      # teal shadows, orange highlights
        im = Image.blend(ImageEnhance.Contrast(im).enhance(1.12), tone, 0.35)
        if st == "cinematic":
            from PIL import ImageDraw
            w, h = im.size
            bar = int(h * 0.11)
            dr = ImageDraw.Draw(im)
            dr.rectangle([0, 0, w, bar], fill=(0, 0, 0))
            dr.rectangle([0, h - bar, w, h], fill=(0, 0, 0))
    elif st == "fade":
        im = im.point(lambda x: int(40 + x * 0.78))
        im = ImageEnhance.Color(im).enhance(0.8)
    elif st == "dreamy":
        soft = im.filter(ImageFilter.GaussianBlur(14))
        im = ImageChops.screen(im, soft)
        im = Image.blend(im, Image.new("RGB", im.size, (255, 200, 230)), 0.08)
    elif "grain" in st:
        import random as _rr
        w, h = im.size
        small = Image.new("L", (max(1, w // 2), max(1, h // 2)))
        small.putdata([_rr.randint(0, 255) for _ in range(small.size[0] * small.size[1])])
        noise = small.resize((w, h)).convert("RGB")
        im = Image.blend(ImageEnhance.Color(im).enhance(0.85), noise, 0.08)
        im = _vignette(im, 0.3)
    elif st == "glitch":
        r, g, b = im.split()
        sh = max(4, im.size[0] // 60)
        im = Image.merge("RGB", (ImageChops.offset(r, sh, 0), g, ImageChops.offset(b, -sh, 0)))
    elif st == "neon":
        edges = im.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
        edges = ImageEnhance.Brightness(ImageEnhance.Color(edges).enhance(3)).enhance(2.5)
        im = ImageChops.add(ImageEnhance.Brightness(im).enhance(0.35), edges.filter(ImageFilter.GaussianBlur(1)))
    elif st == "cartoon":
        base = ImageOps.posterize(im.filter(ImageFilter.SMOOTH_MORE).filter(ImageFilter.SMOOTH_MORE), 3)
        lines = ImageOps.grayscale(im).filter(ImageFilter.FIND_EDGES).point(lambda x: 0 if x > 40 else 255)
        im = ImageChops.multiply(ImageEnhance.Color(base).enhance(1.5), lines.convert("RGB"))
    elif "duotone" in st:
        im = ImageOps.colorize(ImageOps.grayscale(im), (40, 10, 90), (255, 120, 190))
    elif st == "polaroid":
        w, h = im.size
        side = min(w, h)
        im = ImageOps.fit(ImageEnhance.Color(im).enhance(0.9), (side, side))
        frame = Image.new("RGB", (side + side // 10, side + side // 4), (250, 248, 240))
        frame.paste(im, (side // 20, side // 20))
        im = frame
    elif st == "vignette":
        im = _vignette(im, 0.5)
    elif "black" in st:
        im = ImageOps.grayscale(im).convert("RGB")
    elif "vintage" in st:
        g = ImageOps.grayscale(im)
        im = ImageOps.colorize(g, (60, 35, 15), (245, 225, 180))
        im = ImageEnhance.Contrast(im).enhance(0.9)
    elif "sketch" in st:
        g = ImageOps.grayscale(im).filter(ImageFilter.SMOOTH_MORE)
        edges = ImageOps.invert(g.filter(ImageFilter.FIND_EDGES))
        edges = ImageEnhance.Contrast(edges).enhance(2.2)
        im = Image.blend(edges.convert("RGB"), ImageOps.autocontrast(g).convert("RGB").point(lambda x: 160 + x * 95 // 255), 0.25)
    elif "vivid" in st:
        im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.7)).enhance(1.15)
    elif "glow" in st:
        im = Image.blend(im, im.filter(ImageFilter.GaussianBlur(10)), 0.4)
        im = ImageEnhance.Brightness(im).enhance(1.08)
    elif "mirror" in st:
        im = ImageOps.mirror(im)
    elif "rotate" in st:
        im = im.rotate(-90, expand=True)
    elif "blur" in st:
        im = im.filter(ImageFilter.GaussianBlur(6))
    elif "sharpen" in st:
        im = im.filter(ImageFilter.UnsharpMask(3, 160, 2))
    elif "negative" in st:
        im = ImageOps.invert(im)
    elif "pixel" in st:
        w, h = im.size
        im = im.resize((max(1, w // 24), max(1, h // 24)), Image.NEAREST).resize((w, h), Image.NEAREST)
    elif "poster" in st:
        im = ImageOps.posterize(im, 3)
    elif "emboss" in st:
        im = im.filter(ImageFilter.EMBOSS)
    elif "bright" in st:
        im = ImageEnhance.Brightness(im).enhance(1.35)
    else:
        return None, "I don't know that effect."
    out = fun_out("fx_" + re.sub(r"\W+", "", st)[:10])
    im.save(out, quality=92)
    return out, f"{style} done."


def make_slideshow(paths, seconds=2, effect=""):
    """A little video: pictures fade into each other, saved as an animated GIF that plays anywhere."""
    from PIL import Image, ImageOps
    paths = [p for p in paths if p and os.path.exists(p)][:12]
    if len(paths) < 2:
        return None, "Choose at least 2 pictures for a video."
    size = (480, 480)
    imgs = []
    for p in paths:
        try:
            imgs.append(ImageOps.fit(_open_rgb(p), size))
        except Exception:
            pass
    if effect:
        tmp = []
        for im in imgs:
            f = os.path.join(genius_dl("fun"), ".tmp_fx.jpg")
            im.save(f)
            o, _ = transform_image(f, effect) if effect != "Beautify" else beautify(f)
            tmp.append(ImageOps.fit(_open_rgb(o), size) if o else im)
            try:
                os.remove(o)
            except Exception:
                pass
        imgs = tmp
    frames, durs = [], []
    for i, im in enumerate(imgs):
        frames.append(im)
        durs.append(int(seconds * 1000))
        nxt = imgs[(i + 1) % len(imgs)]
        for k in (0.2, 0.4, 0.6, 0.8):
            frames.append(Image.blend(im, nxt, k))
            durs.append(90)
    out = fun_out("video", ".gif")
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=200) for f in frames]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=durs, loop=0, optimize=False)
    return out, f"Video slideshow of {len(imgs)} pictures made. It loops forever."


def open_url(url):
    try:
        from jnius import autoclass
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PA = autoclass("org.kivy.android.PythonActivity")
        PA.mActivity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    except Exception:
        import webbrowser
        webbrowser.open(url)


# ---------------- 111.9: in-app player (videos and stories open INSIDE Genius) ----------------
_WEB = {"box": None, "view": None, "keep": []}


def web_is_open():
    return _WEB["box"] is not None


def close_web():
    def go():
        box, view = _WEB["box"], _WEB["view"]
        _WEB["box"] = _WEB["view"] = None
        try:
            if view is not None:
                view.loadUrl("about:blank")
                view.onPause()
            if box is not None and box.getParent() is not None:
                box.getParent().removeView(box)
            if view is not None:
                view.destroy()
        except Exception as e:
            log(f"WEB close failed: {e}")
    try:
        _ui(go)
    except Exception:
        pass


def open_in_genius(url, title="Genius"):
    """Play a video or open a story inside Genius (Android WebView). Falls back to the phone's browser."""
    if not url:
        return False
    if "youtube.com/watch" in url or "youtu.be/" in url:
        m = re.search(r"(?:v=|youtu\.be/)([\w-]{6,})", url)
        if m:
            url = "https://m.youtube.com/watch?v=" + m.group(1)
    try:
        from jnius import autoclass, PythonJavaClass, java_method
    except Exception:
        open_url(url)
        return False

    class _Click(PythonJavaClass):
        __javainterfaces__ = ["android/view/View$OnClickListener"]
        __javacontext__ = "app"

        @java_method("(Landroid/view/View;)V")
        def onClick(self, v):
            close_web()

    class _Key(PythonJavaClass):
        __javainterfaces__ = ["android/view/View$OnKeyListener"]
        __javacontext__ = "app"

        @java_method("(Landroid/view/View;ILandroid/view/KeyEvent;)Z")
        def onKey(self, v, code, ev):
            if code != 4:                          # only the Back key
                return False
            if ev.getAction() == 1:                # key up
                w = _WEB["view"]
                if w is not None and w.canGoBack():
                    w.goBack()
                else:
                    close_web()
            return True

    def go():
        if _WEB["box"] is not None:              # already open: just load the new link
            _WEB["view"].loadUrl(url)
            return
        PA = autoclass("org.kivy.android.PythonActivity")
        act = PA.mActivity
        LL = autoclass("android.widget.LinearLayout")
        LP = autoclass("android.widget.LinearLayout$LayoutParams")
        VGLP = autoclass("android.view.ViewGroup$LayoutParams")
        Button = autoclass("android.widget.Button")
        TextView = autoclass("android.widget.TextView")
        WebView = autoclass("android.webkit.WebView")
        Color = autoclass("android.graphics.Color")
        box = LL(act)
        box.setOrientation(1)
        box.setBackgroundColor(Color.parseColor("#0b0b14"))
        bar = LL(act)
        bar.setOrientation(0)
        bar.setBackgroundColor(Color.parseColor("#14122a"))
        bar.setPadding(16, 8, 16, 8)
        close = Button(act)
        close.setText("Close")
        close.setTextColor(Color.parseColor("#1a1a1a"))
        close.setBackgroundColor(Color.parseColor("#ffc84d"))
        click = _Click()
        close.setOnClickListener(click)
        head = TextView(act)
        head.setText(str(title)[:60])
        head.setTextColor(Color.parseColor("#ffc84d"))
        head.setTextSize(16.0)
        head.setPadding(24, 0, 0, 0)
        head.setSingleLine(True)
        bar.addView(close, LP(-2, -2))
        bar.addView(head, LP(0, -2, 1.0))
        web = WebView(act)
        st = web.getSettings()
        st.setJavaScriptEnabled(True)
        st.setDomStorageEnabled(True)
        st.setMediaPlaybackRequiresUserGesture(False)
        st.setLoadWithOverviewMode(True)
        st.setUseWideViewPort(True)
        st.setBuiltInZoomControls(True)
        st.setDisplayZoomControls(False)
        web.setWebViewClient(autoclass("android.webkit.WebViewClient")())     # links stay inside Genius
        web.setWebChromeClient(autoclass("android.webkit.WebChromeClient")())
        key = _Key()
        web.setOnKeyListener(key)
        web.setFocusable(True)
        web.setFocusableInTouchMode(True)
        box.addView(bar, LP(-1, -2))
        box.addView(web, LP(-1, 0, 1.0))
        act.addContentView(box, VGLP(-1, -1))
        web.requestFocus()
        web.loadUrl(url)
        _WEB.update(box=box, view=web)
        _WEB["keep"] = [click, key]
    try:
        _ui(go, on_fail=lambda m, c: open_url(url))
        return True
    except Exception as e:
        log(f"WEB open failed: {e}")
        open_url(url)
        return False


def newest_photos(n=6):
    found = []
    for d in ("/storage/emulated/0/DCIM/Camera", "/storage/emulated/0/Pictures",
              "/storage/emulated/0/Download", "/storage/emulated/0/Pictures/Screenshots", genius_dl("fun"), genius_dl("pictures"), "."):
        try:
            for x in os.listdir(d):
                if x.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    found.append(os.path.join(d, x))
        except Exception:
            pass
    def mt(f):
        try:
            return os.path.getmtime(f)
        except Exception:
            return 0
    found = sorted(set(found), key=mt, reverse=True)
    return found[:n]


def file_kind(path, mime=""):
    low = path.lower()
    if mime.startswith("image") or low.endswith(IMG_EXTS):
        return "image"
    if mime == "application/pdf" or low.endswith(".pdf"):
        return "pdf"
    if mime.startswith("text") or low.endswith(TEXT_EXTS) or "json" in mime:
        return "text"
    return "other"


def newest_file(images_only=False):
    """The newest photo or file on the phone (Download, Camera, Screenshots, Documents)."""
    best, bt = None, 0
    dirs = ["/storage/emulated/0/DCIM/Camera", "/storage/emulated/0/Pictures/Screenshots",
            "/storage/emulated/0/DCIM/Screenshots", "/storage/emulated/0/Pictures",
            "/storage/emulated/0/Download", "/storage/emulated/0/Documents"]
    for d in dirs:
        try:
            names = os.listdir(d)
        except Exception:
            continue
        for n in names:
            f = os.path.join(d, n)
            if not os.path.isfile(f) or n.startswith("."):
                continue
            k = file_kind(f)
            if (images_only and k != "image") or k == "other":
                continue
            t = os.path.getmtime(f)
            if t > bt:
                best, bt = f, t
    return best


def ask_about_file(path, kind, question):
    """Answer a question about an attached picture, PDF or text file."""
    q = question.strip() or "Explain what this is and the important information in it, simply."
    if kind == "text":
        try:
            content = open(path, encoding="utf8", errors="ignore").read()[:24000]
        except Exception:
            return "I couldn't open that file any more. Add it again with +."
        if not connected_ais():
            return NO_AI_MSG
        return ask_gemini("File " + os.path.basename(path) + ":\n" + content +
                          "\n\nQuestion: " + q, 900) or NET_AI_MSG
    if not os.path.exists(KEY_FILE):
        return ("To read pictures and PDFs I need a Gemini key. Type setkey and your free key from "
                "aistudio.google.com/apikey, then ask again.")
    if not os.path.exists(path):
        return "I can't find that file any more. Add it again with +."
    key = clean_key(open(KEY_FILE).read())
    mime = "application/pdf" if kind == "pdf" else (
        "image/png" if path.lower().endswith(".png") else "image/webp" if path.lower().endswith(".webp") else "image/jpeg")
    if os.path.getsize(path) > 15 * 1024 * 1024:
        return "That file is too big (over 15 MB). Try a smaller one."
    body = json.dumps({"contents": [{"role": "user", "parts": [
        {"inlineData": {"mimeType": mime, "data": base64.b64encode(open(path, "rb").read()).decode()}},
        {"text": q + " Answer in simple, clear English."}]}],
        "generationConfig": {"maxOutputTokens": 900, "temperature": 0.4}}).encode()
    last = "I couldn't read it. Try again."
    for model in FAST_MODELS + DEEP_MODELS[:1]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
        try:
            try:
                r = urllib.request.urlopen(req, timeout=90, context=ssl_context())
            except urllib.error.URLError as e:
                if "CERTIFICATE" not in str(e).upper():
                    raise
                r = urllib.request.urlopen(req, timeout=90, context=ssl._create_unverified_context())
            with r:
                parts = json.load(r)["candidates"][0]["content"]["parts"]
            t = "\n".join(x["text"] for x in parts if "text" in x and not x.get("thought")).strip()
            if t:
                return t
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf8", "ignore")
            if e.code in (401, 403) or (e.code == 400 and "API key" in detail):
                return key_reason(e.code, detail)
            last = "Free limit reached. Wait a minute." if e.code == 429 else "Google is busy. Try again shortly."
        except Exception as e:
            last = "Your internet is too slow right now. Move to better signal and ask again."
            if _is_net_error(e):
                break
    return last


def ask_gemini(prompt, max_tokens=600, json_mode=False, search=False, system=None):
    """Ask Gemini; if it has no key or fails, another connected AI answers instead."""
    r = _ask_gemini_only(prompt, max_tokens, json_mode, search, system)
    if r and not (search and r.startswith("Search failed")):
        return r
    for prov in ranked_providers():
        sys_txt = system or ("You help " + CURRENT["name"] + ", a young person in Uganda. Simple, clear English."
                             + (" Reply with only valid JSON." if json_mode else ""))
        t = other_ai(prov, prompt, system=sys_txt, max_tokens=max(max_tokens, 400))
        if t:
            if json_mode:
                t = t.strip().strip("`")
                t = t[t.find("{"):t.rfind("}") + 1] if "{" in t else t
            return t
    if r and not (search and r.startswith("Search failed")):
        return r
    return rescue_answer(prompt, max_tokens=max_tokens, system=system, json_mode=json_mode) or r


# ================= 112.3 Never-fail answers: many ways to answer, auto-reconnect =================
FREE_AI_URL = "https://text.pollinations.ai/openai"      # free backup AI, no key needed
_FAIL_RE = re.compile(r"^\s*(i couldn.t reach|genius mind couldn.t reach|search failed|something went wrong|"
                      r"i couldn.t mark|no ai could be reached|sorry, i couldn.t)", re.I)
AI_HEALTH = {"fails": 0, "last_ok": 0.0, "last_way": ""}


def is_fail_reply(r):
    return (not r) or r in (NET_AI_MSG, NO_AI_MSG) or bool(_FAIL_RE.match(str(r)))


def wait_for_net(sec=15):
    """Wait a little for signal to come back instead of giving up at once."""
    end = time.time() + sec
    while time.time() < end:
        for host in (("1.1.1.1", 443), ("8.8.8.8", 53)):
            try:
                socket.create_connection(host, timeout=3).close()
                NET_STATE.update(checked=time.time(), online=True)
                return True
            except Exception:
                pass
        time.sleep(1.5)
    return False


def free_ai(prompt, system=None, convo=None, max_tokens=700, _waited=False):
    """Backup AI that needs no key. Used only when every connected AI failed."""
    msgs = [{"role": "system", "content": system or (
        "You are Genius, a helpful AI made by Ssali Muto in Uganda, talking to " + CURRENT["name"] +
        ", a young person in Uganda. Answer clearly, accurately and simply.")}]
    for m in (convo or [])[-8:]:
        t = " ".join(p.get("text", "") for p in m.get("parts", []))
        if t:
            msgs.append({"role": "assistant" if m["role"] == "model" else "user", "content": t[:3000]})
    msgs.append({"role": "user", "content": prompt})
    for model in ("openai", "openai-fast", "mistral"):
        try:
            req = urllib.request.Request(FREE_AI_URL, data=json.dumps(
                {"model": model, "messages": msgs, "max_tokens": max_tokens + 600}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=40, context=ssl_context()) as r:
                d = json.load(r)
            t = (d["choices"][0]["message"].get("content") or "").strip()
            if t:
                LAST_AI["name"] = "genius-backup"
                return t
        except urllib.error.HTTPError as e:
            log(f"free AI {model}: HTTP {e.code}")
            if e.code in (402, 429):              # free limit: one reply every ~30 s; wait once, then retry
                if not _waited:
                    _waited = True
                    time.sleep(12)
                    return free_ai(prompt, system, convo, max_tokens, _waited=True)
                break
        except Exception as e:
            log(f"free AI {model}: {type(e).__name__}")
            if _is_net_error(e):
                break
    return None


def rescue_answer(prompt, convo=None, max_tokens=700, system=None, json_mode=False):
    """Last line of defence: every connected AI again, then the free backup AI; waits for signal between rounds."""
    for rnd in range(3):
        if rnd and not wait_for_net(12 if rnd == 1 else 20):
            continue
        tries = []
        if os.path.exists(KEY_FILE):
            tries.append(("gemini", lambda: _ask_gemini_only(prompt, max_tokens, json_mode, False, system)))
        for prov in ranked_providers():
            tries.append((prov, lambda prov=prov: other_ai(prov, prompt, system=system, convo=convo,
                                                          max_tokens=max(max_tokens, 400))))
        tries.append(("backup", lambda: free_ai(prompt, system=system, convo=convo, max_tokens=max_tokens)))
        for name, fn in tries:
            try:
                r = fn()
            except Exception as e:
                log(f"rescue {name}: {type(e).__name__}")
                r = None
            if r and not is_fail_reply(r):
                AI_HEALTH.update(fails=0, last_ok=time.time(), last_way=name)
                if json_mode and "{" in r:
                    r = r.strip().strip("`")
                    r = r[r.find("{"):r.rfind("}") + 1]
                return r
        AI_HEALTH["fails"] += 1
    return None


def ai_health_report():
    """'aicheck': tests every AI connection right now and says which ones work."""
    lines, ok = [], 0
    ways = [("Gemini", lambda: _ask_gemini_only("Reply with the word OK.", 20))] if os.path.exists(KEY_FILE) else []
    ways += [(AI_NAMES.get(p, p), lambda p=p: other_ai(p, "Reply with the word OK.", max_tokens=20))
             for p in ranked_providers()]
    ways.append(("Genius backup (no key)", lambda: free_ai("Reply with the word OK.", max_tokens=20)))
    for name, fn in ways:
        t0 = time.time()
        try:
            r = fn()
        except Exception:
            r = None
        ok += bool(r)
        lines.append(f"- {name}: " + (f"working ({time.time() - t0:.1f}s)" if r else "not answering"))
    head = (f"{ok} of {len(ways)} ways to answer are working." if ok else
            ("No AI answered. Your internet works, so the AI services may be busy: try again in a minute."
             if wait_for_net(3) else "No AI is answering because your phone has no internet: check data or Wi-Fi."))
    return head + "\n" + "\n".join(lines) + "\nIf one fails, Genius moves to the next one by itself."


def think_together(question):
    """Several AIs answer, then one AI checks them and writes the best combined answer."""
    have = connected_ais()
    if not have:
        return NO_AI_MSG
    drafts = ask_all(question)
    if len(have) < 2:
        return drafts
    judge = ("Here is a question and answers from different AIs.\nQuestion: " + question +
             "\n\n" + re.sub(r"\[/?b\]", "", drafts) +
             "\n\nCheck them against each other. Fix any mistakes, keep what is correct, and "
             "write ONE best answer in simple English (under 200 words). If they disagree on a "
             "fact and you are not sure, say so.")
    best = ask_gemini(judge, 900)
    return ("Best answer (checked by " + str(len(have)) + " AIs):\n" + (best or "Couldn't combine.")
            + "\n\nType askall to see each AI's own answer.")


# ================= PERSONAL AI: emotional support + safety =================
HELPLINES = """You don't have to go through this alone. Free help in Uganda:
- Emergency, police: 999 or 112
- Sauti 116: call or SMS 116, free, 24 hours
- Mental Health Uganda: 0800 21 21 21 (Mon-Fri, 8:30am-5pm), free
- CDFU counselling line: 0800 200 600, free
- Police family protection (violence at home): 0800 199 195, free
If you're in danger right now, call 999 or go to the nearest health centre.
Type sos to message your trusted people."""

CARE_RULES = ("[Care mode: the owner is hurting right now. Speak like a caring, steady friend: "
              "gentle, warm, unhurried. First name the feeling you hear and tell them it makes "
              "sense to feel that way. Remind them they are not alone and they matter. Don't "
              "lecture, don't rush to fix, no lists. Ask one soft question about what happened "
              "or what would help most right now. Keep it under 80 words. Be honest that you "
              "are an AI if asked, but care about their wellbeing in every word.]\n")

CRISIS_WORDS = ("kill myself", "suicide", "suicidal", "want to die", "wanna die", "end my life",
                "end it all", "hurt myself", "harm myself", "self harm", "cut myself",
                "no reason to live", "better off dead", "take my life", "njagala okufa",
                "beating me", "abusing me", "raped", "being abused", "threatening to kill")


def is_crisis(text):
    t = " " + text.lower() + " "
    return any(w in t for w in CRISIS_WORDS)


DISTRESS_WORDS = ("sad", "depressed", "lonely", "alone", "hopeless", "crying", "cry ",
                  "stressed", "anxious", "scared", "afraid", "hurt", "heartbroken", "broken",
                  "nobody cares", "no one cares", "hate myself", "worthless", "useless",
                  "tired of everything", "can't cope", "cant cope", "give up", "failed",
                  "miserable", "empty", "pain", "grief", "died", "death",
                  "nnakunyiga", "ennaku", "sirina ssanyu")


def is_distressed(text):
    t = " " + text.lower() + " "
    return is_crisis(text) or any(w in t for w in DISTRESS_WORDS)


def soft_voice(on):
    """Slower, gentler voice when someone is hurting."""
    eng = _android_tts.get("engine")
    if eng is not None and _android_tts.get("ready"):
        try:
            eng.setSpeechRate(0.85 if on else VOICE_SPEED)
            eng.setPitch(VOICE_PITCH * (0.95 if on else 1.0))
        except Exception:
            pass


def mood_add(score, note=""):
    d = life_load()
    d.setdefault("moods", []).append({"t": time.strftime("%Y-%m-%d %H:%M"),
                                      "s": int(score), "note": note})
    d["moods"] = d["moods"][-200:]
    life_save(d)


def mood_summary():
    m = life_load().get("moods", [])
    if not m:
        return "No mood check-ins yet. Type mood 1 to 5, e.g. mood 3 tired after school."
    last = m[-7:]
    avg = sum(x["s"] for x in last) / len(last)
    faces = {1: "very low", 2: "low", 3: "okay", 4: "good", 5: "great"}
    lines = [f"{x['t'][5:16]}  {x['s']}/5 {faces.get(x['s'], '')} {x['note']}" for x in last]
    trend = ""
    if len(m) >= 4:
        a = sum(x["s"] for x in m[-4:-2]) / 2
        b = sum(x["s"] for x in m[-2:]) / 2
        trend = " Getting better." if b > a else (" A bit lower lately." if b < a else "")
    return f"Your last {len(last)} check-ins average {avg:.1f}/5.{trend}\n" + "\n".join(lines)


def contacts_load():
    return life_load().get("contacts", {})


def sos_message(contacts):
    """Open the SMS app with a help message to trusted contacts. You press Send."""
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    nums = ";".join(contacts.values())
    i = Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + nums))
    me = life_load().get("my_phone")
    body = "I need help. Please call me as soon as you can" + (f" on {me}" if me else "") + ". - sent from Genius"
    i.putExtra("sms_body", body)
    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(i)
    return True


def dial(number):
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    i = Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + number))
    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(i)
    return True


CALM_STEPS = ["Let's slow down together. Sit comfortably.",
              "Breathe in slowly through your nose... 2... 3... 4.",
              "Hold it... 2... 3... 4.",
              "Breathe out slowly through your mouth... 2... 3... 4... 5... 6.",
              "Again. Breathe in... 2... 3... 4.",
              "Hold... 2... 3... 4.",
              "And out... 2... 3... 4... 5... 6.",
              "Now look around. Name 3 things you can see and 2 things you can hear.",
              "Well done. I'm here. Tell me how you feel now, or type mood and a number."]


def do_calc(expr):
    import ast, operator as op
    ops = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
           ast.Pow: op.pow, ast.Mod: op.mod, ast.USub: op.neg, ast.UAdd: op.pos, ast.FloorDiv: op.floordiv}

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return n.value
        if isinstance(n, ast.BinOp):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
                raise OverflowError                     # 9**9**9 would freeze the phone
            return ops[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp):
            return ops[type(n.op)](ev(n.operand))
        raise ValueError
    clean = (expr or "").strip().rstrip("=?").replace("\u00d7", "*").replace("\u00f7", "/").replace("^", "**")
    clean = re.sub(r"(?<=\d),(?=\d{3}\b)", "", clean)          # 12,000 -> 12000
    clean = re.sub(r"(?<=[\d)\s])[xX](?=[\d(\s])", "*", clean)   # 12 x 3 -> 12*3
    clean = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1/100)", clean)   # 15% -> 0.15
    clean = re.sub(r"\s+of\s+", "*", clean, flags=re.I)              # 15% of 40000
    try:
        val = ev(ast.parse(clean, mode="eval").body)
        if isinstance(val, float) and val.is_integer() and abs(val) < 1e15:
            val = int(val)
        return f"{expr.strip()} = {val:,}" if isinstance(val, int) else f"{expr.strip()} = {val:,.6g}"
    except ZeroDivisionError:
        return "You can't divide by zero. Try another sum."
    except OverflowError:
        return "That number is too big for me. Try a smaller sum."
    except Exception:
        return "I can do sums like: calc 12*8+5, calc 2^10 or calc 15% of 40000"


_WEATHER_CACHE = {}
WEATHER_CODES = {0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy",
                 45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
                 56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain",
                 65: "heavy rain", 66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow",
                 75: "heavy snow", 77: "snow grains", 80: "rain showers", 81: "rain showers",
                 82: "heavy rain showers", 85: "snow showers", 86: "snow showers", 95: "a thunderstorm",
                 96: "a thunderstorm with hail", 99: "a strong thunderstorm with hail"}


def weather_report(city):
    city = (city or "Kampala").strip(" .?!") or "Kampala"
    ck = city.lower()
    hit = _WEATHER_CACHE.get(ck)
    if hit and time.time() - hit[1] < 600:                 # same city within 10 minutes: instant
        return hit[0]
    try:
        g = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1"
        with urllib.request.urlopen(g, timeout=12, context=ssl_context()) as r:
            res = json.load(r).get("results") or []
        if not res:
            return f"I couldn't find a place called '{city}'. Check the spelling, e.g. weather Mityana."
        loc = res[0]
        w = (f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}"
             f"&longitude={loc['longitude']}&current=temperature_2m,relative_humidity_2m,"
             f"wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min,"
             f"precipitation_probability_max&timezone=auto")
        with urllib.request.urlopen(w, timeout=12, context=ssl_context()) as r:
            d = json.load(r)
        c = d["current"]
        hi = d["daily"]["temperature_2m_max"][0]
        lo = d["daily"]["temperature_2m_min"][0]
        rain = (d["daily"].get("precipitation_probability_max") or [None])[0]
        sky = WEATHER_CODES.get(c.get("weather_code"), "mixed weather")
        place = loc["name"] + (f", {loc['country']}" if loc.get("country") and loc["country"] != "Uganda" else "")
        out = (f"{place}: {c['temperature_2m']:.0f} degrees now and {sky}, "
               f"humidity {c['relative_humidity_2m']:.0f} percent, wind "
               f"{c['wind_speed_10m']:.0f} km/h. Today {lo:.0f} to {hi:.0f} degrees"
               + (f", {rain:.0f} percent chance of rain." if rain is not None else "."))
        _WEATHER_CACHE[ck] = (out, time.time())
        return out
    except Exception as e:
        log(f"WEATHER failed: {e}")
        if hit:
            return hit[0] + " (from a little earlier: I couldn't refresh it)"
        return "I couldn't get the weather right now. Check your internet and try again."


def _vault_key():
    return hashlib.sha256((OWNER_HASH + "vault").encode()).digest()


def _vault_xor(data):
    k = _vault_key()
    return bytes(b ^ k[i % len(k)] for i, b in enumerate(data))


def vault_load():
    try:
        return json.load(open(VAULT_FILE))
    except Exception:
        return {}


def vault_save(label, value):
    v = vault_load()
    v[label.lower()] = base64.b64encode(_vault_xor(value.encode())).decode()
    json.dump(v, open(VAULT_FILE, "w"))


def vault_get(label):
    v = vault_load()
    enc = v.get(label.lower())
    if not enc:
        return None
    try:
        return _vault_xor(base64.b64decode(enc)).decode()
    except Exception:
        return None


LUGANDA_CMDS = {
    "yogera": "speak", "kifaananyi": "draw", "kuba": "draw", "ebyama": "secrets",
    "tereka": "save", "ggulawo": "open", "wandiika": "note", "ebiwandiiko": "notes",
    "obudde": "weather", "lowooza": "deep", "sangula": "clear", "essaawa": "time",
    "obuyambi": "help", "bbatule": "battery", "jjukiza": "remind", "bala": "calc",
    "yimirira": "stop", "ekisumuluzo": "key",
}


# ---------------- colours for words (per theme), suggestions, karaoke, sound control ----------------
def _hx(c, a=None):
    h = "".join("%02x" % int(max(0.0, min(1.0, v)) * 255 + 0.5) for v in c[:3])
    return h + ("%02x" % int(max(0.0, min(1.0, a)) * 255 + 0.5) if a is not None else "")


def theme_palette(name=None):
    """Text colours for chat and lyrics. All are bright on the dark backgrounds of every theme."""
    name = name or THEME
    if name == "gold":
        p = dict(accent=(1.00, 0.82, 0.30), accent2=(1.00, 0.58, 0.22), user=(1.00, 0.91, 0.72),
                 num=(1.00, 0.87, 0.56), link=(1.00, 0.74, 0.46), cmd=(1.00, 0.80, 0.34),
                 text=(1.0, 0.97, 0.88), hint=(0.80, 0.70, 0.48), chip=((1.00, 0.80, 0.26, 1), (0.86, 0.62, 0.16, 1),
                                                                         (0.55, 0.34, 0.05, 1), (1.0, 0.85, 0.45, 0.18)))
    elif name == "diamond":
        p = dict(accent=(0.72, 0.93, 1.00), accent2=(0.76, 0.62, 1.00), user=(0.62, 0.82, 1.00),
                 num=(0.58, 0.90, 1.00), link=(0.80, 0.72, 1.00), cmd=(0.72, 0.93, 1.00),
                 text=(0.95, 0.99, 1.0), hint=(0.64, 0.78, 0.92), chip=((0.72, 0.93, 1.00, 1), (0.45, 0.72, 1.00, 1),
                                                                          (0.68, 0.52, 1.00, 1), (0.75, 0.92, 1.0, 0.18)))
    else:
        p = dict(accent=(1.00, 0.78, 0.30), accent2=(0.78, 0.60, 1.00), user=(0.62, 0.71, 1.00),
                 num=(0.45, 0.92, 0.68), link=(0.56, 0.80, 1.00), cmd=(1.00, 0.78, 0.30),
                 text=(0.96, 0.96, 1.00), hint=(0.62, 0.64, 0.78), chip=((1.00, 0.78, 0.30, 1), (0.33, 0.42, 1.00, 1),
                                                                          (0.62, 0.30, 0.98, 1), (1, 1, 1, 0.14)))
    p["name"] = name
    return p


PAL = theme_palette()


def _lum(c):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _esc(t):
    return str(t).replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")


def gradient_word(word, c1, c2):
    n = max(1, len(word) - 1)
    return "".join(f"[color={_hx([a + (b - a) * i / n for a, b in zip(c1, c2)])}]{ch}[/color]"
                   for i, ch in enumerate(word))


_MARKUP_TAG = re.compile(r"(\[/?(?:b|i|u|s|sub|sup|color|size|font|ref|anchor|font_context|font_family|"
                         r"font_features|text_language)(?:=[^\]]*)?\])")
_HILITE = re.compile(
    r"(?P<url>(?:https?://|www\.)[^\s\]]*[^\s\].,!?;:)'\"])"
    r"|(?P<q>(?<![A-Za-z])'[^'\n]{2,40}'(?![A-Za-z]))"
    r"|(?P<num>(?<![\w#.])(?:UGX\s?)?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|BPM|MB|GB|UGX|sh)|k\b|K\b)?)"
    r"|(?P<kw>\b(?:Tip|Important|Warning|Done|Saved|Ready|Note|Remember|Playing now)\b)")
_CMD_WORDS = None


def _cmd_words():
    global _CMD_WORDS
    if _CMD_WORDS is None:
        _CMD_WORDS = {c.split()[0] for c, _ in _suggest_pool()} | set(LUGANDA_CMDS)
    return _CMD_WORDS


def md_to_markup(text, pal=None):
    """Turn the AI's simple markdown (**bold**, # headings, - bullets) into tidy Kivy markup."""
    if not text or "[" in text and "[/" in text:
        return text
    pal = pal or PAL
    acc = _hx(pal["accent"])
    out = []
    for ln in text.split("\n"):
        h = re.match(r"^\s{0,3}#{1,4}\s+(.*)$", ln)
        if h:
            out.append(f"[b][size=17sp][color={acc}]{h.group(1).strip(' *')}[/color][/size][/b]")
            continue
        b = re.match(r"^(\s*)[-*\u2022]\s+(.*)$", ln)
        if b:
            ln = ("    " if len(b.group(1)) >= 2 else "") + f"[color={acc}]\u2022[/color] " + b.group(2)
        ln = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", ln)
        ln = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)\*(?![*\w])", r"[i]\1[/i]", ln)
        if ln.startswith("Sources: "):
            ln = f"[size=12sp][color={_hx(pal['hint'])}]{ln}[/color][/size]"
        out.append(ln)
    return "\n".join(out)


def split_follow_ups(text):
    """('answer without the Ask next line', ['question 1', 'question 2'])."""
    if not text or "Ask next:" not in text:
        return text, []
    lines = text.rstrip().split("\n")
    for i in range(len(lines) - 1, max(-1, len(lines) - 4), -1):
        m = re.match(r"^\W*Ask next:\s*(.+)$", lines[i].strip(), re.I)
        if m:
            qs = [q.strip(" ?*_.\"'") + "?" for q in m.group(1).split("|") if len(q.strip()) > 3][:3]
            return "\n".join(lines[:i] + lines[i + 1:]).rstrip(), qs
    return text, []


def colorize(text, pal=None):
    """Kivy markup highlights for Genius's words: links, 'commands', numbers and a few key words.
    Existing markup tags are left exactly as they are."""
    if not text:
        return text
    pal = pal or PAL
    link, num, cmd, kw = _hx(pal["link"]), _hx(pal["num"]), _hx(pal["cmd"]), _hx(pal["accent2"])

    def rep(m):
        g = m.lastgroup
        s = m.group(0)
        if g == "url":
            return f"[color={link}][u]{s}[/u][/color]"
        if g == "q":
            first = s[1:-1].strip().split(" ")[0].lower() if s[1:-1].strip() else ""
            return f"[b][color={cmd}]{s}[/color][/b]" if first in _cmd_words() else s
        if g == "num":
            return f"[color={num}]{s}[/color]"
        return f"[b][color={kw}]{s}[/color][/b]"
    parts = _MARKUP_TAG.split(text)
    return "".join(p if i % 2 else _HILITE.sub(rep, p) for i, p in enumerate(parts))


# ---- word / command suggestions while typing ----
_SUGGEST_EXTRA = (
    "play song", "stop music", "pause music", "lyrics", "music", "theme gold", "theme diamond", "theme classic",
    "mic test", "help", "make song amapiano about ", "make song afrobeat about ", "make song gospel about ",
    "make song kadongo kamu about ", "make song dancehall about ", "make song hip hop about ",
    "make song rnb about ", "make song love ballad about ", "make song kids song about ",
    "make song luganda praise about ", "make song pop about ", "draw ", "edit ", "studio", "camera", "home",
    "premium", "everywhere", "share", "quick ", "mind ", "better: ", "teach skill ", "wealth", "market ",
)
_NO_SUGGEST = ("save ", "seteleven", "setkey", "setgroq", "setrouter", "setpolli", "setvoice", "setsunbird", "open ", "tereka ", "ggulawo ")
_POOL = []


def _suggest_pool():
    if not _POOL:
        seen = set()

        def add(cmd, hint):
            c = cmd.strip().lower()
            if c and c != "+" and c not in seen:
                seen.add(c)
                _POOL.append((cmd.lower() if not cmd.endswith(" ") else cmd.lower(), hint))
        for k, v in ALLOWED.items():
            add(k + (" " if "e.g." in v or "YOURKEY" in v else ""), v)
        for k, v in HELP_EXTRA.items():
            for piece in k.split("/"):
                piece = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", piece)).strip()
                if piece:
                    add(piece + (" " if "<" in k else ""), v)
        for k, v in LUGANDA_CMDS.items():
            add(k, "Luganda for " + v)
        for k in _SUGGEST_EXTRA:
            add(k, "")
    return _POOL


def suggest_commands(text, limit=6):
    """Commands that match what is being typed: [(text to fill in, hint), ...]. Fast enough for every key press."""
    t = (text or "").lower().lstrip()
    if not t or len(t) > 40 or t.startswith(_NO_SUGGEST) or len(t.split()) > 4:
        return []
    pool = _suggest_pool()
    starts = [(c, h) for c, h in pool if c.startswith(t) and c.strip() != t.strip()]
    starts.sort(key=lambda x: (len(x[0]), x[0]))
    inner = [(c, h) for c, h in pool if (" " + t) in (" " + c) and not c.startswith(t)] if len(t) >= 3 else []
    fuzzy = []
    if len(starts) < 2 and " " not in t.strip() and len(t) >= 3:
        import difflib
        heads = {c.split()[0]: (c, h) for c, h in pool}
        fuzzy = [heads[w] for w in difflib.get_close_matches(t.strip(), list(heads), n=3, cutoff=0.72)]
    out, seen = [], set()
    for c, h in starts + inner + fuzzy:
        if c not in seen:
            seen.add(c)
            out.append((c, h))
        if len(out) >= limit:
            break
    return out


# ---- word prediction (like a phone keyboard): completes words, guesses the next word, fixes typos ----
WORDS_FILE = os.path.join(ROOT, "typing_words.json")
_SEED_EN = ("the to and you i a is it what how in of for my can me do are this that have with please "
            "help tell about make write explain what's time today tomorrow weather song picture photo "
            "money school study exam question answer story english luganda uganda kampala thank thanks "
            "hello good morning evening night love friend family mother father brother sister work "
            "phone app business learn read find show give send call need want know think like where when "
            "why who which because will would should could more best new news price buy sell farm maize "
            "beans coffee matooke rain biology chemistry physics mathematics history geography computer")
_SEED_LG = ("oli otya gyendi bulungi webale nnyo ssebo nnyabo kale nedda yee nkwagala mukwano ggwe nze "
            "ffe mmwe bo ani ki wa ddi lwaki meka olunaku leero jjo enkya ekiro emmere amazzi ssente "
            "omulimu essomero omusomesa omuyizi maama taata muganda mwannyinaze ennyimba yimba "
            "nnyamba ndaga mpandiikira tereka ggulawo wulira genius")
_SEED_NEXT = {"how": "are to do", "what": "is are time", "thank": "you", "good": "morning evening night",
              "i": "am want need love", "can": "you i", "tell": "me", "write": "a me", "make": "a me",
              "oli": "otya", "webale": "nnyo", "nkwagala": "nnyo", "where": "is are", "please": "help tell"}
_AUTOCORRECT = {"teh": "the", "adn": "and", "waht": "what", "wat": "what", "hw": "how", "becuase": "because",
                "becouse": "because", "recieve": "receive", "beleive": "believe", "wierd": "weird",
                "untill": "until", "tommorow": "tomorrow", "tomorow": "tomorrow", "wether": "weather",
                "freind": "friend", "thier": "their", "definately": "definitely", "seperate": "separate",
                "goverment": "government", "acheive": "achieve", "occured": "occurred", "plz": "please",
                "pls": "please", "u": "you", "ur": "your", "thx": "thanks", "im": "I'm", "dont": "don't",
                "cant": "can't", "wont": "won't", "didnt": "didn't", "isnt": "isn't", "doesnt": "doesn't",
                "whats": "what's", "lets": "let's", "ugnda": "uganda", "kampla": "kampala", "biolgy": "biology",
                "chemestry": "chemistry", "mathematic": "mathematics", "maths": "maths", "i": "I"}
COMMON_WORDS = {"make", "makes", "maker", "create", "about", "where", "there", "their", "which", "would", "could",
                "should", "please", "write", "tell", "show", "explain", "think", "thing", "things", "music", "notes",
                "story", "draw", "photo", "image", "money", "price", "today", "hello", "thanks", "again", "start"}

_EMOJI = {"love": "❤️", "happy": "😊", "sad": "😢", "laugh": "😂", "lol": "😂", "fire": "🔥", "thanks": "🙏",
          "thank": "🙏", "ok": "👍", "good": "👍", "music": "🎵", "song": "🎶", "money": "💰", "school": "📚",
          "food": "🍲", "rain": "🌧️", "sun": "☀️", "party": "🎉", "birthday": "🎂", "phone": "📱", "cool": "😎",
          "wow": "😮", "sleep": "😴", "angry": "😠", "football": "⚽", "pray": "🙏", "congratulations": "🎉"}
_WORDS = {"uni": None, "bi": None, "dirty": 0}


def _words_load():
    if _WORDS["uni"] is None:
        uni, bi = {}, {}
        for i, w in enumerate((_SEED_EN + " " + _SEED_LG).split()):
            uni[w] = max(uni.get(w, 0), 3 if i < 40 else 2)
        for a, nxt in _SEED_NEXT.items():
            bi[a] = {b: 2 for b in nxt.split()}
        try:
            d = json.load(open(WORDS_FILE))
            for w, n in d.get("uni", {}).items():
                uni[w] = uni.get(w, 0) + int(n)
            for a, m in d.get("bi", {}).items():
                bi.setdefault(a, {}).update({b: bi.get(a, {}).get(b, 0) + int(n) for b, n in m.items()})
        except Exception:
            pass
        _WORDS["uni"], _WORDS["bi"] = uni, bi
    return _WORDS["uni"], _WORDS["bi"]


_WORD_RE = re.compile(r"[A-Za-z\u00C0-\u024F']+")


def learn_words(text):
    """Remember the words this person really uses (only on this phone), so predictions get personal."""
    if not text or text.lower().startswith(_NO_SUGGEST) or len(text) > 600:
        return
    uni, bi = _words_load()
    ws = [w.lower() for w in _WORD_RE.findall(text) if 0 < len(w) < 24]
    for i, w in enumerate(ws):
        uni[w] = uni.get(w, 0) + 1
        if i:
            m = bi.setdefault(ws[i - 1], {})
            m[w] = m.get(w, 0) + 1
    if len(uni) > 6000:                      # keep the file small on low-memory phones
        for w, _ in sorted(uni.items(), key=lambda x: x[1])[:1000]:
            uni.pop(w, None)
            bi.pop(w, None)
    try:
        tmp = WORDS_FILE + ".tmp"
        json.dump({"uni": uni, "bi": {a: dict(sorted(m.items(), key=lambda x: -x[1])[:12]) for a, m in bi.items()}},
                  open(tmp, "w"))
        os.replace(tmp, WORDS_FILE)
    except Exception as e:
        log(f"WORDS save failed: {e}")


def _keep_case(src, word):
    if src[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def suggest_words(text, limit=3):
    """[(new full text, 'word:<label>')] for the chip row: finish the word being typed, fix a typo,
    or guess the next word after a space. Plus an emoji when one fits."""
    if not text or text.lower().lstrip().startswith(_NO_SUGGEST) or len(text) > 400:
        return []
    uni, bi = _words_load()
    out, seen = [], set()

    def add(new_text, label):
        if label.lower() not in seen and len(out) < limit + 1:
            seen.add(label.lower())
            out.append((new_text, "word:" + label))
    m = re.search(r"([A-Za-z\u00C0-\u024F']+)$", text)
    if m and not text.endswith(" "):
        part, head = m.group(1), text[:m.start(1)]
        low = part.lower()
        prev = _WORD_RE.findall(head)
        prev = prev[-1].lower() if prev else ""
        if low in _AUTOCORRECT and _AUTOCORRECT[low] != part:
            add(head + _keep_case(part, _AUTOCORRECT[low]) + " ", _keep_case(part, _AUTOCORRECT[low]))
        cands = [w for w in uni if w.startswith(low) and w != low]
        nb = bi.get(prev, {})
        cands.sort(key=lambda w: (-(nb.get(w, 0) * 5 + uni[w]), len(w)))
        for w in cands[:limit]:
            add(head + _keep_case(part, w) + " ", _keep_case(part, w))
        if len(out) < 2 and len(low) >= 3 and low not in uni:
            import difflib
            for w in difflib.get_close_matches(low, list(uni), n=2, cutoff=0.78):
                add(head + _keep_case(part, w) + " ", _keep_case(part, w))
    else:
        prev = _WORD_RE.findall(text)
        if not prev:
            return []
        nb = bi.get(prev[-1].lower(), {})
        base = text if text.endswith(" ") else text + " "
        for w, _ in sorted(nb.items(), key=lambda x: -x[1])[:limit]:
            add(base + w + " ", w)
    return out[:limit + 1]


# ---- karaoke ----
_SECTION_NAME = {"intro": "Intro", "verse1": "Verse 1", "verse2": "Verse 2", "chorus": "Chorus",
                 "bridge": "Bridge", "outro": "Outro"}


def karaoke_markup(lines, idx, pal=None):
    """Current line big and bright in the theme accent, sung lines dimmed, coming lines soft."""
    pal = pal or PAL
    acc, acc2 = _hx(pal["accent"]), _hx(pal["accent2"])
    past, soft, nxt, hint = _hx(pal["hint"], 0.62), _hx(pal["text"], 0.72), _hx(pal["text"], 0.92), _hx(pal["hint"])
    out, last_sec = [], None
    for i, ln in enumerate(lines):
        sec = ln.get("section") or ""
        if sec and sec != last_sec:
            out.append(f"[size=12sp][b][color={hint}]{_SECTION_NAME.get(sec, sec.title()).upper()}[/color][/b][/size]")
        last_sec = sec
        t = _esc(ln.get("text", ""))
        if i == idx:
            out.append(f"[size=25sp][b][color={acc}]{t}[/color][/b][/size]")
        elif i < idx:
            out.append(f"[size=17sp][color={past}]{t}[/color][/size]")
        elif i == idx + 1:
            out.append(f"[size=19sp][color={nxt}]{t}[/color][/size]")
        else:
            out.append(f"[size=18sp][color={soft}]{t}[/color][/size]")
    if idx >= len(lines) - 1 and lines:
        out.append(f"[size=13sp][color={acc2}]\u2022 Genius[/color][/size]")
    return "\n".join(out)


def _fmt_time(s):
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


# ---- what's playing (Kivy sound, or Android's MediaPlayer fallback) ----
def sound_pos():
    snd = _luganda.get("sound")
    if snd is None:
        return None
    try:
        if hasattr(snd, "getCurrentPosition"):
            return snd.getCurrentPosition() / 1000.0
        return float(snd.get_pos() or 0.0)
    except Exception:
        return None


def sound_playing():
    snd = _luganda.get("sound")
    if snd is None:
        return False
    try:
        if hasattr(snd, "isPlaying"):
            return bool(snd.isPlaying())
        return snd.state == "play"
    except Exception:
        return False


def sound_pause():
    snd = _luganda.get("sound")
    if snd is None:
        return None
    pos = sound_pos() or 0.0
    try:
        if hasattr(snd, "isPlaying"):
            snd.pause()
        else:
            snd.stop()
    except Exception:
        pass
    _luganda["paused_at"] = pos
    return pos


def sound_resume():
    """Returns the position playback restarted from (0 if the player can't seek)."""
    snd = _luganda.get("sound")
    if snd is None:
        return None
    at = _luganda.get("paused_at") or 0.0
    try:
        if hasattr(snd, "isPlaying"):
            snd.start()
            return at
        snd.play()
        if at:
            snd.seek(at)
        return at
    except Exception:
        return 0.0


def sound_stop():
    snd = _luganda.get("sound")
    _luganda["paused_at"] = 0.0
    try:
        if snd is not None:
            snd.stop()
    except Exception:
        pass


# ---------------- native listening (works inside Pydroid, no extra modules) ----------------
SPEECH_ERRORS = {
    1: "The internet timed out.", 2: "No internet for speech.", 3: "The microphone had a problem.",
    4: "Google's speech server had a problem.", 5: "Speech stopped early.",
    6: "I heard nothing.", 7: "I couldn't make out the words.", 8: "The microphone is busy.",
    9: "Pydroid doesn't have microphone permission. Open phone Settings, Apps, Pydroid 3, "
       "Permissions, and allow Microphone.",
}
_mic = {"rec": None, "listener": None, "runs": []}
MIC_STATE = {"last": "nothing yet", "ready": False, "token": 0}


def _ui(fn, on_fail=None):
    """Run fn on Android's main thread (speech must start there)."""
    from jnius import autoclass, PythonJavaClass, java_method

    class _Run(PythonJavaClass):
        __javainterfaces__ = ["java/lang/Runnable"]

        @java_method("()V")
        def run(self):
            try:
                fn()
            except Exception as e:
                msg = f"start failed: {e}"          # bind now: 'e' is cleared when the except block ends
                log(f"UI RUN error: {e}")
                MIC_STATE["last"] = msg
                if on_fail:
                    Clock.schedule_once(lambda *_, m=msg: on_fail(m, -1), 0)
    r = _Run()
    _mic["runs"] = (_mic["runs"] + [r])[-5:]      # keep alive
    autoclass("org.kivy.android.PythonActivity").mActivity.runOnUiThread(r)


def mic_permission_ok():
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    perm = "android.permission.RECORD_AUDIO"
    if act.checkSelfPermission(perm) == 0:
        return True
    act.requestPermissions([perm], 4242)
    return False


def open_app_settings():
    """Open this app's Android settings page (Permissions are there)."""
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    i = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
               Uri.parse("package:" + act.getPackageName()))
    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(i)
    return True


def native_listen(on_text, on_error):
    """Listen once with Android's SpeechRecognizer. Calls on_text(words) or on_error(msg)."""
    from jnius import autoclass, PythonJavaClass, java_method
    SR = autoclass("android.speech.SpeechRecognizer")
    RI = autoclass("android.speech.RecognizerIntent")
    Intent = autoclass("android.content.Intent")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    if not SR.isRecognitionAvailable(act):
        raise RuntimeError("no recogniser")

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["android/speech/RecognitionListener"]

        @java_method("(Landroid/os/Bundle;)V")
        def onReadyForSpeech(self, b):
            MIC_STATE["ready"] = True
            MIC_STATE["last"] = "microphone open"

        @java_method("()V")
        def onBeginningOfSpeech(self):
            MIC_STATE["last"] = "hearing your voice"

        @java_method("(F)V")
        def onRmsChanged(self, v): pass

        @java_method("([B)V")
        def onBufferReceived(self, b): pass

        @java_method("()V")
        def onEndOfSpeech(self): pass

        @java_method("(I)V")
        def onError(self, code):
            msg = SPEECH_ERRORS.get(code, f"Speech error {code}.")
            MIC_STATE["last"] = f"error {code}: {msg}"
            Clock.schedule_once(lambda *_: on_error(msg, code), 0)

        @java_method("(Landroid/os/Bundle;)V")
        def onResults(self, bundle):
            words = ""
            try:
                lst = bundle.getStringArrayList(SR.RESULTS_RECOGNITION)
                if lst is not None and lst.size() > 0:
                    words = lst.get(0)
            except Exception:
                pass
            MIC_STATE["last"] = f"heard: {words!r}"
            Clock.schedule_once(lambda *_: on_text(words), 0)

        @java_method("(Landroid/os/Bundle;)V")
        def onPartialResults(self, b): pass

        @java_method("(ILandroid/os/Bundle;)V")
        def onEvent(self, t, b): pass

    MIC_STATE["ready"] = False
    MIC_STATE["last"] = "starting"

    def start():
        if _mic["rec"] is not None:
            try:
                _mic["rec"].cancel()
            except Exception:
                pass
        if _mic["rec"] is None:
            _mic["rec"] = SR.createSpeechRecognizer(act)
            _mic["listener"] = _Listener()
            _mic["rec"].setRecognitionListener(_mic["listener"])
        i = Intent(RI.ACTION_RECOGNIZE_SPEECH)
        i.putExtra(RI.EXTRA_LANGUAGE_MODEL, RI.LANGUAGE_MODEL_FREE_FORM)
        i.putExtra(RI.EXTRA_LANGUAGE, "en-US")
        i.putExtra(RI.EXTRA_MAX_RESULTS, 1)
        _mic["rec"].startListening(i)
    _ui(start, on_error)
    return True


def native_stop():
    def stop():
        if _mic["rec"] is not None:
            _mic["rec"].cancel()
    safe(lambda: _ui(stop))


# ================= Genius everywhere: bubble, home-screen shortcuts, "Hey Genius" =================
EVERYWHERE = {"bubble": None, "bubble_on": True, "pending": None, "keep": []}
_SET_FILE = os.path.join(ROOT, "everywhere.json")


def everywhere_load():
    try:
        EVERYWHERE.update(json.load(open(_SET_FILE)))
    except Exception:
        pass


def everywhere_save():
    try:
        json.dump({"bubble_on": EVERYWHERE["bubble_on"]}, open(_SET_FILE, "w"))
    except Exception:
        pass


def can_draw_overlay():
    from jnius import autoclass
    Settings = autoclass("android.provider.Settings")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    return bool(Settings.canDrawOverlays(act))


def ask_overlay_permission():
    from jnius import autoclass
    Intent = autoclass("android.content.Intent")
    Settings = autoclass("android.provider.Settings")
    Uri = autoclass("android.net.Uri")
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    i = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + act.getPackageName()))
    i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(i)


def _bring_genius_front(action=None):
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    Intent = autoclass("android.content.Intent")
    i = Intent(act, act.getClass())
    i.addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT | Intent.FLAG_ACTIVITY_NEW_TASK)
    if action:
        i.putExtra("genius_action", action)
    act.startActivity(i)


def bubble_show():
    """A round gold 'G' that floats over every other app. Tap = open Genius, drag = move it."""
    if EVERYWHERE["bubble"] is not None or not EVERYWHERE["bubble_on"]:
        return
    try:
        if not can_draw_overlay():
            return
    except Exception:
        return
    from jnius import autoclass, PythonJavaClass, java_method

    def make():
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        Context = autoclass("android.content.Context")
        WM = autoclass("android.view.WindowManager")
        LP = autoclass("android.view.WindowManager$LayoutParams")
        TextView = autoclass("android.widget.TextView")
        GD = autoclass("android.graphics.drawable.GradientDrawable")
        GDO = autoclass("android.graphics.drawable.GradientDrawable$Orientation")
        Gravity = autoclass("android.view.Gravity")
        PixelFormat = autoclass("android.graphics.PixelFormat")
        Color_ = autoclass("android.graphics.Color")
        MotionEvent = autoclass("android.view.MotionEvent")
        wm = act.getSystemService(Context.WINDOW_SERVICE)
        dens = act.getResources().getDisplayMetrics().density
        size = int(58 * dens)
        tv = TextView(act)
        tv.setText("G")
        tv.setTextSize(24.0)
        tv.setTextColor(Color_.parseColor("#1A1300"))
        tv.setGravity(Gravity.CENTER)
        safe(lambda: tv.getPaint().setFakeBoldText(True))
        bg = GD(GDO.TL_BR, [Color_.parseColor("#FFD36B"), Color_.parseColor("#F08A2E")])
        bg.setShape(GD.OVAL)
        bg.setStroke(int(2 * dens), Color_.parseColor("#B07BFF"))
        tv.setBackground(bg)
        tv.setElevation(12 * dens)
        lp = LP(size, size, LP.TYPE_APPLICATION_OVERLAY,
                LP.FLAG_NOT_FOCUSABLE | LP.FLAG_LAYOUT_NO_LIMITS, PixelFormat.TRANSLUCENT)
        lp.gravity = Gravity.TOP | Gravity.LEFT
        lp.x, lp.y = int(12 * dens), int(220 * dens)
        st = {"x": 0, "y": 0, "rx": 0.0, "ry": 0.0, "moved": False}

        class _Touch(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnTouchListener"]

            @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
            def onTouch(self, v, ev):
                a = ev.getAction()
                if a == MotionEvent.ACTION_DOWN:
                    st.update(x=lp.x, y=lp.y, rx=ev.getRawX(), ry=ev.getRawY(), moved=False)
                elif a == MotionEvent.ACTION_MOVE:
                    dx, dy = ev.getRawX() - st["rx"], ev.getRawY() - st["ry"]
                    if abs(dx) + abs(dy) > 12:
                        st["moved"] = True
                    lp.x, lp.y = int(st["x"] + dx), int(st["y"] + dy)
                    wm.updateViewLayout(v, lp)
                elif a == MotionEvent.ACTION_UP and not st["moved"]:
                    _bring_genius_front("talk")
                return True
        t = _Touch()
        tv.setOnTouchListener(t)
        wm.addView(tv, lp)
        EVERYWHERE["bubble"] = (wm, tv)
        EVERYWHERE["keep"] = [t, lp, bg]
    _ui(make)


def bubble_hide():
    b = EVERYWHERE.get("bubble")
    if not b:
        return
    EVERYWHERE["bubble"] = None

    def rm():
        try:
            b[0].removeView(b[1])
        except Exception:
            pass
    _ui(rm)


def pin_shortcut(action, label):
    """Put a Genius button on the phone's home screen that opens straight into an action."""
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    Intent = autoclass("android.content.Intent")
    SM = autoclass("android.content.pm.ShortcutManager")
    SI = autoclass("android.content.pm.ShortcutInfo$Builder")
    Icon = autoclass("android.graphics.drawable.Icon")
    Context = autoclass("android.content.Context")
    sm = act.getSystemService(autoclass("java.lang.Class").forName("android.content.pm.ShortcutManager"))
    if not sm.isRequestPinShortcutSupported():
        return False
    i = Intent(act, act.getClass())
    i.setAction(Intent.ACTION_MAIN)
    i.putExtra("genius_action", action)
    icon = Icon.createWithResource(act, act.getApplicationInfo().icon)
    info = SI(act, "genius_" + action).setShortLabel(label).setIcon(icon).setIntent(i).build()
    sm.requestPinShortcut(info, None)
    return True


GENIUS_APK_FALLBACK = "https://github.com/ssalimuto/Genius-app/releases/download/android/Genius.apk"   # always the newest app
GENIUS_LINK = GENIUS_APK_FALLBACK
_APK_LINK = {}


def newest_apk_link():
    """Direct download of the newest Genius app (the newest release that has an APK). Opens straight to the
    download on any Android phone; after install, Genius updates itself to the latest version."""
    return GENIUS_APK_FALLBACK          # 112.2: one fixed link that every new build refreshes
    hit = _APK_LINK.get("u")
    if hit and time.time() - hit[1] < 6 * 3600:
        return hit[0]
    try:
        req = urllib.request.Request("https://api.github.com/repos/ssalimuto/Genius-app/releases?per_page=40",
                                     headers={"User-Agent": "Genius", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=12, context=ssl_context()) as r:
            rels = json.load(r)
        for rel in rels:
            if rel.get("draft") or rel.get("prerelease"):
                continue
            for a in rel.get("assets", []):
                if a.get("name", "").endswith(".apk") and a.get("browser_download_url", "").startswith(
                        "https://github.com/ssalimuto/Genius-app/"):
                    _APK_LINK["u"] = (a["browser_download_url"], time.time())
                    return a["browser_download_url"]
    except Exception as e:
        log(f"APK link: {type(e).__name__}")
    return GENIUS_APK_FALLBACK


def share_text():
    return SHARE_TEXT.replace(GENIUS_APK_FALLBACK, (_APK_LINK.get("u") or (GENIUS_APK_FALLBACK,))[0])


SHARE_TEXT = ("Meet Genius - a smart AI app made in Uganda. It answers like Google with sources, makes realistic "
              "pictures, edits photos without changing your face, makes songs, helps you type in English and Luganda, "
              "and more. Free 7-day trial. Download for Android: " + GENIUS_LINK)


def share_genius(target=None):
    """Open Android's share sheet (WhatsApp, TikTok, Facebook, X, Instagram, SMS...) with the download link."""
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    Intent = autoclass("android.content.Intent")
    i = Intent(Intent.ACTION_SEND)
    i.setType("text/plain")
    i.putExtra(Intent.EXTRA_TEXT, share_text())
    if target:
        i.setPackage(target)
        try:
            act.startActivity(i)
            return True
        except Exception:
            i.setPackage(None)
    ch = Intent.createChooser(i, "Share Genius")
    ch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(ch)
    return True


# ---------------- Genius Wealth bot: live prices, chart reading, wealth guide ----------------
CRYPTO_IDS = {"btc": "bitcoin", "bitcoin": "bitcoin", "eth": "ethereum", "ethereum": "ethereum",
              "bnb": "binancecoin", "sol": "solana", "solana": "solana", "xrp": "ripple", "usdt": "tether",
              "doge": "dogecoin", "ada": "cardano", "trx": "tron", "ton": "the-open-network", "ltc": "litecoin"}
FX_CODES = ("usd", "ugx", "kes", "tzs", "rwf", "eur", "gbp", "zar", "ngn", "cny", "aed", "inr")
WEALTH_SYSTEM = ("TOP PRIORITY: protect the person's money from losses first, profits second. Before any trade idea, check: is there a stop-loss, is risk 1-2% or less, is it money they can afford to lose, is the broker regulated, is it a scam (guaranteed returns, account managers, pressure, send-money-to-double)? If any check fails, say STOP clearly and why. "
                 "You are Genius Wealth, a free trading coach for people in Uganda and East Africa who want to build "
                 "wealth through trading (forex, stocks, crypto). Explain simply, with UGX where useful. Teach: reading "
                 "charts (trend, support/resistance, candles, RSI, MACD, moving averages), building a written trading plan, "
                 "entries and exits, stop-loss and take-profit, risking at most 1-2% of the account per trade, position "
                 "size math, a trading journal, demo practice before real money, regulated brokers only, and avoiding "
                 "signal-sellers, 'account managers' and scams. Use the live prices given. Be honest that most traders "
                 "lose money and growth comes from discipline over time. Never promise profits or say 'guaranteed'. "
                 "Never ask for PINs or passwords. End with one clear next step. Education, not financial advice.")
CHART_PROMPT = ("Your first job is to protect the person's money: start with a one-line MONEY SAFETY verdict (SAFE / CAREFUL / DANGER) and the biggest risk of loss. You are a careful technical analyst. Read this trading chart picture. Report, in simple English: "
                "1) the asset and timeframe if visible, 2) the trend (up, down, sideways) and why, 3) key support and "
                "resistance levels with prices read from the axis, 4) any patterns or candles (e.g. double top, "
                "flag, engulfing) and indicators shown (RSI, MACD, moving averages, volume), 5) a bullish scenario "
                "and a bearish scenario with the price that would confirm each, 6) a sensible risk plan: where a "
                "stop-loss could go and why to risk only 1-2% of the account. Say clearly if the picture is too "
                "blurry or not a chart. End with: 'This is education, not financial advice. Charts can't predict "
                "the future.' Never say a trade is guaranteed. "
                "IF the screenshot shows an open or closed TRADE or position (broker app such as MT4/MT5, Exness, "
                "Binance, a positions/history screen, or entry/stop/target lines on a chart): read the asset, buy or "
                "sell, lot/amount, entry price, current or exit price, stop-loss, take-profit and the profit/loss "
                "shown. Then explain: whether it is in profit or loss and by how much (in money, pips/points and % of "
                "the account if visible); the risk-to-reward ratio; how much it would lose at the stop and gain at "
                "the target; mistakes (no stop-loss, lot too big, risking over 2%, trading against the trend); and "
                "calm options, e.g. keep the stop, move it to break-even, take partial profit, or close, with the "
                "reason for each. Help the person learn from wins and losses like a coach.")


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Genius/102", "Accept": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl_context())
    except urllib.error.URLError as e:
        if "CERTIFICATE" not in str(e).upper():
            raise
        r = urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())
    with r:
        return json.loads(r.read().decode("utf8", "ignore"))


def usd_rates():
    return _get_json("https://open.er-api.com/v6/latest/USD").get("rates", {})


def _yahoo(symbol):
    d = _get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d")
    m = d["chart"]["result"][0]["meta"]
    p, prev = m.get("regularMarketPrice"), m.get("chartPreviousClose") or m.get("previousClose")
    if p is None:
        return None
    return {"symbol": m.get("symbol", symbol), "price": float(p), "currency": m.get("currency", "USD"),
            "chg": ((p - prev) / prev * 100) if prev else None}


def crypto_price(sym):
    """Live coin price: CoinGecko, then Yahoo, then Coinbase."""
    cid = CRYPTO_IDS.get(sym.lower(), sym.lower())
    try:
        d = _get_json(f"https://api.coingecko.com/api/v3/simple/price?ids={cid}&vs_currencies=usd,ugx"
                      f"&include_24hr_change=true")
        if cid in d:
            x = d[cid]
            return {"name": cid, "usd": x.get("usd"), "ugx": x.get("ugx"), "chg": x.get("usd_24h_change")}
    except Exception:
        pass
    tick = {v: k for k, v in CRYPTO_IDS.items() if len(k) <= 4}.get(cid, sym).upper()
    ugx = None
    try:
        ugx = usd_rates().get("UGX")
    except Exception:
        pass
    try:
        y = _yahoo(f"{tick}-USD")
        if y:
            return {"name": cid, "usd": y["price"], "ugx": y["price"] * ugx if ugx else None, "chg": y["chg"]}
    except Exception:
        pass
    try:
        amt = float(_get_json(f"https://api.coinbase.com/v2/prices/{tick}-USD/spot")["data"]["amount"])
        return {"name": cid, "usd": amt, "ugx": amt * ugx if ugx else None, "chg": None}
    except Exception:
        return None


def stock_price(sym):
    try:
        y = _yahoo(sym.upper())
    except Exception:
        return None
    return y


def market_quote(q):
    """Real, live numbers. 'btc', 'aapl', 'usd ugx', '100 usd to ugx'."""
    q = q.lower().replace(" to ", " ").replace("/", " ").strip()
    words = q.split()
    if not words:
        return "Say market and a name, e.g. market btc, market aapl, or market 100 usd ugx."
    amt = 1.0
    if re.match(r"^[\d.,]+$", words[0]):
        amt = float(words[0].replace(",", ""))
        words = words[1:]
    if len(words) >= 2 and words[0] in FX_CODES and words[1] in FX_CODES:
        rates = usd_rates()
        a, b = words[0].upper(), words[1].upper()
        if a not in rates or b not in rates:
            return "I couldn't get that exchange rate right now."
        val = amt / rates[a] * rates[b]
        return f"{amt:,.2f} {a} = {val:,.2f} {b} (live rate)."
    sym = words[0]
    try:
        c = crypto_price(sym) if sym in CRYPTO_IDS else None
        if c:
            chg = f", {c['chg']:+.2f}% in 24h" if c.get("chg") is not None else ""
            ugx = f" = UGX {c['ugx']:,.0f}" if c.get("ugx") else ""
            return f"{c['name'].title()}: ${c['usd']:,.2f}{ugx}{chg} (live)."
        s_ = stock_price(sym)
        if s_:
            chg = f", {s_['chg']:+.2f}% today" if s_.get("chg") is not None else ""
            return f"{s_['symbol']}: {s_['price']:,.2f} {s_['currency']}{chg} (live)."
        c = crypto_price(sym)
        if c:
            return f"{c['name'].title()}: ${c['usd']:,.2f} (live)."
    except Exception as e:
        return f"Market data didn't load: {e}. Check your internet."
    return f"I couldn't find a price for {sym.upper()}. Try a stock symbol like aapl or a coin like btc."


def wealth_answer(question, profile=""):
    live = ""
    for w in re.findall(r"[a-zA-Z]{2,6}", question):
        if w.lower() in CRYPTO_IDS:
            try:
                live += market_quote(w) + "\n"
            except Exception:
                pass
    if re.search(r"\b(usd|dollar|ugx|shilling|rate)\b", question.lower()):
        try:
            live += market_quote("usd ugx") + "\n"
        except Exception:
            pass
    prompt = (("Live data:\n" + live + "\n") if live else "") + \
             (("About me: " + profile + "\n") if profile else "") + "Question: " + question
    return ask_gemini(prompt, 900, search=True, system=WEALTH_SYSTEM) or "No AI answered. Check your internet."


_APPS_CACHE = {}


def phone_apps(refresh=False):
    """Every app on this phone that can be opened: {label: package}. Owner only."""
    if _APPS_CACHE and not refresh:
        return _APPS_CACHE
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    Intent = autoclass("android.content.Intent")
    pm = act.getPackageManager()
    i = Intent(Intent.ACTION_MAIN)
    i.addCategory(Intent.CATEGORY_LAUNCHER)
    lst = pm.queryIntentActivities(i, 0)
    _APPS_CACHE.clear()
    for k in range(lst.size()):
        info = lst.get(k).activityInfo
        try:
            label = str(lst.get(k).loadLabel(pm))
        except Exception:
            label = info.packageName
        _APPS_CACHE[label] = info.packageName
    return _APPS_CACHE


def find_phone_app(name):
    name = name.lower().strip()
    apps = phone_apps()
    for label, pkg in apps.items():
        if label.lower() == name:
            return label, pkg
    for label, pkg in apps.items():
        if label.lower().startswith(name) or name in label.lower() or name in pkg.lower():
            return label, pkg
    return None, None


def open_phone_app(pkg):
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    it = act.getPackageManager().getLaunchIntentForPackage(pkg)
    if it is None:
        return False
    it.addFlags(autoclass("android.content.Intent").FLAG_ACTIVITY_NEW_TASK)
    act.startActivity(it)
    return True


def intent_action(intent=None):
    try:
        from jnius import autoclass
        if intent is None:
            intent = autoclass("org.kivy.android.PythonActivity").mActivity.getIntent()
        a = intent.getStringExtra("genius_action")
        if a:
            intent.removeExtra("genius_action")
        return a
    except Exception:
        return None

# ---------------- screens ----------------
class ProfileChip(Button):
    """Round profile picture (or initial) for the left of the header."""
    def __init__(self, **kw):
        sz = kw.pop("size", ("42dp", "42dp"))
        kw.setdefault("width", sz[0])
        kw.setdefault("height", sz[1])
        kw.setdefault("font_size", "18sp")
        super().__init__(background_normal="", background_down="", background_color=(0, 0, 0, 0),
                         size_hint=(None, None), bold=True, color=(1, 1, 1, 1), **kw)
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_once(self.redraw, 0)

    def redraw(self, *_):
        from kivy.graphics import Ellipse
        self.canvas.before.clear()
        photo = profile_photo()
        name = str(CURRENT.get("name") or "G")
        with self.canvas.before:
            Color(*GOLD)
            Ellipse(pos=(self.x - 2, self.y - 2), size=(self.width + 4, self.height + 4))
            if photo:
                try:
                    tex = KivyImage(source=photo, nocache=True).texture
                    Color(1, 1, 1, 1)
                    Ellipse(pos=self.pos, size=self.size, texture=tex)
                    self.text = ""
                    return
                except Exception:
                    pass
            Color(0.55, 0.38, 0.95, 1)
            Ellipse(pos=self.pos, size=self.size)
        self.color = (1, 1, 1, 1)
        self.text = name[:1].upper()


class RoundButton(Button):
    """A glossy rounded button: gradient fill, soft shadow, shine, press animation."""
    def __init__(self, bg=GREY, fg=TEXTCOL, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=fg, **kw)
        self._bg = bg
        with self.canvas.before:
            self._shadow_col = Color(0, 0, 0, 0.35)
            self._shadow = RoundedRectangle(radius=[20])
            self._col = Color(1, 1, 1, 1)
            self._rect = RoundedRectangle(radius=[20])
            self._shine_col = Color(1, 1, 1, 0.10)
            self._shine = RoundedRectangle(radius=[20, 20, 6, 6])
            self._edge_col = Color(1, 1, 1, 0.14)
            self._edge = Line(width=1.0)
        self._paint(bg)
        self.bind(pos=self._sync, size=self._sync)

    def _paint(self, bg):
        pair = _PAIRS.get(tuple(bg))
        if pair:
            self._rect.texture = gradient_texture(bg, pair, horizontal=True)
            self._col.rgba = (1, 1, 1, 1)
            self._shadow_col.rgba = (bg[0], bg[1], bg[2], 0.28)   # coloured glow
        else:
            self._rect.texture = None
            self._col.rgba = bg
            self._shadow_col.rgba = (0, 0, 0, 0.30)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._shadow.pos = (self.x + 1, self.y - 3)
        self._shadow.size = self.size
        self._shine.pos = (self.x + 2, self.y + self.height * 0.52)
        self._shine.size = (max(0, self.width - 4), self.height * 0.46)
        self._edge.rounded_rectangle = (self.x, self.y, self.width, self.height, 20)

    def on_press(self):
        self._shine_col.a = 0.30
        self._shadow_col.a = 0.10

        def fade(dt, c=self._shine_col, sh=self._shadow_col):
            c.a = max(0.10, c.a - 0.04)
            sh.a = min(0.30, sh.a + 0.04)
            return c.a > 0.10 or sh.a < 0.30
        Clock.schedule_interval(fade, 1 / 30)

    def set_bg(self, bg):
        self._bg = bg
        self._paint(bg)


class MenuBars(RoundButton):
    """The three-bar menu button. Shows its bars, or a word (like Stop) when it has one."""
    def __init__(self, **kw):
        super().__init__(text="", **kw)
        with self.canvas.after:
            self._bar_col = Color(*TEXTCOL)
            self._bars = [Rectangle() for _ in range(3)]
        self.bind(pos=self._place, size=self._place, text=self._place)

    def _place(self, *_):
        show = not self.text
        self._bar_col.a = 1 if show else 0
        w = min(self.width * 0.5, dp(22))
        h = dp(2.6)
        gap = dp(6)
        x = self.center_x - w / 2
        for i, r in enumerate(self._bars):
            r.size = (w, h)
            r.pos = (x, self.center_y - h / 2 + (1 - i) * gap)


class Panel(BoxLayout):
    """A frosted-glass card: translucent fill, light edge, soft shadow."""
    def __init__(self, bg=PANEL, radius=22, **kw):
        super().__init__(**kw)
        self._radius = radius
        with self.canvas.before:
            Color(0, 0, 0, 0.25 if radius else 0)
            self._shadow = RoundedRectangle(radius=[radius])
            self._col = Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
            Color(1, 1, 1, 0.10 if radius else 0)
            self._edge = Line(width=1.0)
            Color(*(GOLD[:3] + (0.55 if not radius else 0,)))
            self._gold_line = Rectangle()
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        self._shadow.pos = (self.x, self.y - 4)
        self._shadow.size = self.size
        self._edge.rounded_rectangle = (self.x, self.y, self.width, self.height, max(1, self._radius))
        self._gold_line.pos = self.pos                      # thin gold underline on header bars
        self._gold_line.size = (self.width, 1.5)


def _popup_kb_mode(ti, focused):
    """Boxes in popups and other screens still slide into view above the keyboard; the chat box handles itself."""
    if isinstance(ti, ChatInput):
        return
    Window.softinput_mode = "below_target" if focused else ""


def style_input(ti):
    ti.bind(focus=_popup_kb_mode)
    ti.background_normal = ""
    ti.background_active = ""
    ti.background_color = (0, 0, 0, 0)
    ti.foreground_color = TEXTCOL
    ti.cursor_color = GOLD
    ti.cursor_width = "2dp"
    ti.selection_color = (1.0, 0.78, 0.30, 0.35)
    ti.hint_text_color = HINT
    ti.padding = [18, 14, 18, 14]
    with ti.canvas.before:
        Color(BG[0], BG[1], BG[2], 0.86)        # solid dark base: typed words stay readable over the wallpaper
        base = RoundedRectangle(radius=[18])
        Color(1, 1, 1, 0.07)
        bgr = RoundedRectangle(radius=[18])
        edge_col = Color(1, 1, 1, 0.16)
        edge = Line(width=1.1)

    def sync(*_):
        bgr.pos, bgr.size = ti.pos, ti.size
        base.pos, base.size = ti.pos, ti.size
        edge.rounded_rectangle = (ti.x, ti.y, ti.width, ti.height, 18)

    def glow(_, focused):
        edge_col.rgba = (1.0, 0.78, 0.30, 0.85) if focused else (1, 1, 1, 0.16)
    ti.bind(pos=sync, size=sync, focus=glow)
    return ti


class ChatInput(TextInput):
    """Chat box that wraps and grows to 4 lines; Enter sends instead of adding a new line."""
    def insert_text(self, substring, from_undo=False):
        if "\n" in substring and not from_undo:
            rest = substring.replace("\r", "").split("\n")[0]
            if rest:
                super().insert_text(rest, from_undo=from_undo)
            Clock.schedule_once(lambda *_: self.dispatch("on_text_validate"), 0)
            return
        return super().insert_text(substring, from_undo=from_undo)


def code_setup_popup(on_done=None, first=False):
    """Create or change the hidden secret code (4-8 digits, typed twice, never shown)."""
    box = BoxLayout(orientation="vertical", spacing=10, padding=14)
    pop = Popup(title="Create your secret code" if first else "Change secret code", content=box,
                size_hint=(0.92, 0.66), separator_color=GOLD, title_color=GOLD, auto_dismiss=False)
    box.add_widget(Label(text="4 to 8 digits. You'll need it with your password every time.",
                         color=HINT, font_size="14sp", size_hint_y=None, height="40dp",
                         halign="center", text_size=(Window.width * 0.8, None)))
    fields = []
    hints = (["Old code"] if pin_is_set() and not first else []) + ["New code", "Type it again"]
    for h in hints:
        t = style_input(TextInput(hint_text=h, password=True, password_mask="*", input_filter="int",
                                  multiline=False, size_hint_y=None, height="52dp", font_size="19sp"))
        fields.append(t)
        box.add_widget(t)
    msg = Label(text="", color=(1, 0.45, 0.45, 1), size_hint_y=None, height="26dp")
    box.add_widget(msg)
    row = BoxLayout(size_hint_y=None, height="52dp", spacing=8)
    save = RoundButton(text="Save code", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), bold=True)

    def do(*_):
        vals = [f.text.strip() for f in fields]
        for f in fields:
            f.text = ""
        if len(vals) == 3 and not pin_ok(vals[0]):
            msg.text = "Old code is wrong."
            intruder_log("wrong old secret code")
            return
        new, again = vals[-2], vals[-1]
        if not (4 <= len(new) <= 8):
            msg.text = "Use 4 to 8 digits."
            return
        if new != again:
            msg.text = "The two codes don't match."
            return
        if len(set(new)) == 1 or new in "0123456789" or new in "9876543210":
            msg.text = "Too easy to guess. Try another."
            return
        set_pin(new)
        pop.dismiss()
        if on_done:
            on_done()
    save.bind(on_press=do)
    row.add_widget(save)
    if not first:
        cancel = RoundButton(text="Cancel", bg=GREY, fg=TEXTCOL, bold=True)
        cancel.bind(on_press=pop.dismiss)
        row.add_widget(cancel)
    box.add_widget(row)
    pop.open()


def signup_popup(login_screen):
    """Anyone can make their own account: name, hidden password, hidden secret code."""
    box = BoxLayout(orientation="vertical", spacing=8, padding=14)
    pop = Popup(title="Create your Genius account", content=box, size_hint=(0.95, 0.94),
                separator_color=GOLD, title_color=GOLD)

    def field(h, pw=False, digits=False):
        t = style_input(TextInput(hint_text=h, password=pw, password_mask="*", multiline=False,
                                  input_filter="int" if digits else None,
                                  size_hint_y=None, height="50dp", font_size="18sp"))
        box.add_widget(t)
        return t
    name = field("Choose a name (letters, numbers, _)")
    email = field("Email address")
    email.input_type = "mail"
    pw1 = field("Password (6+ characters)", pw=True)
    pw2 = field("Password again", pw=True)
    c1 = field("Secret code (4-8 digits)", pw=True, digits=True)
    c2 = field("Secret code again", pw=True, digits=True)
    msg = Label(text="Your chats, notes and files stay private to you.", color=HINT,
                font_size="14sp", size_hint_y=None, height="30dp")
    box.add_widget(msg)
    row = BoxLayout(size_hint_y=None, height="52dp", spacing=8)
    ok = RoundButton(text="Create", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), bold=True)
    cancel = RoundButton(text="Cancel", bg=GREY, fg=TEXTCOL, bold=True)

    def do(*_):
        msg.color = (1, 0.45, 0.45, 1)
        if pw1.text != pw2.text:
            msg.text = "The passwords don't match."
        elif c1.text != c2.text:
            msg.text = "The secret codes don't match."
        else:
            err = create_account(name.text, pw1.text, c1.text, email.text)
            if err:
                msg.text = err
            else:
                n = name.text.strip().lower()
                pop.dismiss()
                login_screen.name_in.text = n
                login_screen.msg.color = (0.5, 0.9, 0.6, 1)
                login_screen.msg.text = "Account made. Sign in with your password and code."
                return
        for t in (pw1, pw2, c1, c2):
            t.text = ""
    ok.bind(on_press=do)
    cancel.bind(on_press=pop.dismiss)
    row.add_widget(cancel)
    row.add_widget(ok)
    box.add_widget(row)
    pop.open()


def check_code(code):
    """Owner unlock with the secret code only. Same firewall as before:
    this phone only, wrong tries escalate the lock and end in the decoy."""
    data = load_state()
    data.setdefault("strikes", 0)
    data.setdefault("fails", 0)
    if time.time() < data.get("locked_until", 0):
        intruder_log("code while locked -> decoy")
        return False, "DECOY"
    if data.get("device") and data["device"] != this_device():
        intruder_log("other device -> decoy")
        return False, "DECOY"
    ok = pin_is_set() and len(code.strip()) >= 4 and pin_ok(code)
    log(f"CODE UNLOCK {'OK' if ok else 'FAILED'}")
    if ok:
        data["fails"] = 0
        data["strikes"] = 0
        switch_user(OWNER)
        msg = "Welcome."
    else:
        data["fails"] += 1
        intruder_log("wrong secret code")
        if data["fails"] >= MAX_TRIES:
            wait = LOCKOUT_STEPS[min(data["strikes"], len(LOCKOUT_STEPS) - 1)]
            data["strikes"] += 1
            data["locked_until"] = time.time() + wait
            data["fails"] = 0
            msg = "DECOY"
        else:
            msg = f"Wrong code. {MAX_TRIES - data['fails']} tries left."
    json.dump(data, open(STATE_FILE, "w"))
    return ok, msg


class CodeScreen(BoxLayout):
    """Opening screen: create a secret code the first time, then unlock with it."""
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=28, spacing=0, **kw)
        self.app = app
        add_gradient_bg(self)
        self.add_widget(Widget(size_hint_y=0.22))
        self.first = not pin_is_set()
        card = Panel(orientation="vertical", padding=26, spacing=16,
                     size_hint=(1, None), height="470dp" if self.first else "400dp")
        card.add_widget(Label(text="[b][color=ffc84d]Gen[/color][color=c79bff]ius[/color][/b]", markup=True,
                              font_size="40sp", size_hint_y=None, height="56dp"))
        card.add_widget(Label(text="Create your secret code (4 to 8 digits)" if self.first
                              else "Enter your secret code", font_size="16sp",
                              color=HINT, size_hint_y=None, height="26dp"))
        def box(h):
            return style_input(TextInput(hint_text=h, password=True, password_mask="*", input_filter="int",
                                         multiline=False, size_hint_y=None, height="58dp", font_size="24sp",
                                         halign="center"))
        self.code_in = box("New secret code" if self.first else "Secret code")
        card.add_widget(self.code_in)
        self.again_in = None
        if self.first:
            self.again_in = box("Type it again")
            self.code_in.bind(on_text_validate=lambda *_: setattr(self.again_in, "focus", True))
            self.again_in.bind(on_text_validate=self.go)
            card.add_widget(self.again_in)
        else:
            self.code_in.bind(on_text_validate=self.go)
        self.msg = Label(text="", font_size="16sp", color=(1, 0.45, 0.45, 1),
                         size_hint_y=None, height="30dp")
        card.add_widget(self.msg)
        btn = RoundButton(text="Create code" if self.first else "Unlock", bg=GOLD, fg=(0.1, 0.1, 0.1, 1),
                          size_hint_y=None, height="58dp", font_size="22sp", bold=True)
        btn.bind(on_press=self.go)
        card.add_widget(btn)
        other = RoundButton(text="Other account", bg=GREY, fg=TEXTCOL,
                            size_hint_y=None, height="46dp", font_size="16sp")
        other.bind(on_press=lambda *_: self.app.open_account_login())
        card.add_widget(other)
        self.add_widget(card)
        self.add_widget(Widget())
        Clock.schedule_once(lambda *_: setattr(self.code_in, "focus", True), 0.4)

    def go(self, *_):
        code = self.code_in.text.strip()
        if self.first:
            again = self.again_in.text.strip()
            self.code_in.text = self.again_in.text = ""
            if not (4 <= len(code) <= 8):
                self.msg.text = "Use 4 to 8 digits."
                return
            if code != again:
                self.msg.text = "The two codes don't match."
                return
            if len(set(code)) == 1 or code in "0123456789" or code in "9876543210":
                self.msg.text = "Too easy to guess. Try another."
                return
            data = load_state()
            if not data.get("device"):
                data["device"] = this_device()
                json.dump(data, open(STATE_FILE, "w"))
            set_pin(code)
            switch_user(OWNER)
            self.app.open_home()
            return
        self.code_in.text = ""
        ok, msg = check_code(code)
        if ok:
            self.app.open_home()
        elif msg == "DECOY":
            self.app.open_decoy("code")
        else:
            self.msg.text = msg
            tts(msg)


class LoginScreen(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=28, spacing=0, **kw)
        self.app = app
        add_gradient_bg(self)
        self.add_widget(Widget(size_hint_y=0.2))

        card = Panel(orientation="vertical", padding=26, spacing=18,
                     size_hint=(1, None), height="520dp")
        card.add_widget(Label(text="[b][color=ffc84d]Gen[/color][color=c79bff]ius[/color][/b]", markup=True,
                              font_size="40sp", size_hint_y=None, height="56dp"))
        card.add_widget(Label(text="Sign in to your own Genius", font_size="16sp",
                              color=HINT, size_hint_y=None, height="26dp"))
        self.name_in = style_input(TextInput(hint_text="Name or email", multiline=False,
                                   size_hint_y=None, height="54dp", font_size="19sp"))
        self.pw_in = style_input(TextInput(hint_text="Password", password=True,
                                 multiline=False, size_hint_y=None, height="54dp",
                                 font_size="19sp"))
        self.code_in = style_input(TextInput(hint_text="Secret code" if pin_is_set() else "Secret code (set after unlock)",
                                   password=True, password_mask="*", input_filter="int",
                                   multiline=False, size_hint_y=None, height="54dp",
                                   font_size="19sp"))
        self.pw_in.password_mask = "*"
        self.pw_in.bind(on_text_validate=lambda *_: setattr(self.code_in, "focus", True))
        self.code_in.bind(on_text_validate=self.try_login)
        self.msg = Label(text="", font_size="16sp", color=(1, 0.45, 0.45, 1),
                         size_hint_y=None, height="30dp")
        btn = RoundButton(text="Unlock", bg=GOLD, fg=(0.1, 0.1, 0.1, 1),
                          size_hint_y=None, height="58dp", font_size="22sp", bold=True)
        btn.bind(on_press=self.try_login)
        new_btn = RoundButton(text="Create an account", bg=GREY, fg=TEXTCOL,
                              size_hint_y=None, height="48dp", font_size="17sp")
        new_btn.bind(on_press=lambda *_: signup_popup(self))
        for w in (self.name_in, self.pw_in, self.code_in, self.msg, btn, new_btn):
            card.add_widget(w)
        self.add_widget(card)
        self.add_widget(Widget())

    def try_login(self, *_):
        tried = self.name_in.text
        ok, msg = check_login(self.name_in.text, self.pw_in.text, self.code_in.text)
        self.pw_in.text = ""
        self.code_in.text = ""
        if ok:
            if pin_is_set() or not CURRENT["owner"]:
                self.app.open_home()
            else:
                code_setup_popup(lambda: self.app.open_home(), first=True)
        elif msg == "DECOY":
            self.app.open_decoy(tried)
        else:
            self.msg.text = msg
            tts(msg)




# =====================================================================================
# ================= GENIUS 110: offline, UNEB study, Luganda, money, safety ===========
# Everything here is plain Python (stdlib only). Big tables are built the first time
# they are needed, so opening Genius stays fast on small phones.
# =====================================================================================
_V110_LOCK = threading.Lock()


def _v110_load(name, default):
    """Read a small JSON file from the signed-in person's own folder."""
    try:
        with open(name, encoding="utf8") as f:
            d = json.load(f)
        return d if isinstance(d, type(default)) else default
    except Exception:
        return default


def _v110_save(name, data):
    try:
        with _V110_LOCK:
            tmp = name + ".tmp"
            with open(tmp, "w", encoding="utf8") as f:
                json.dump(data, f)
            os.replace(tmp, name)
        return True
    except Exception as e:
        log(f"V110 save {name} failed: {type(e).__name__}")
        return False


SETTINGS_V110 = "genius110_settings.json"


def v110_settings():
    d = _v110_load(SETTINGS_V110, {})
    d.setdefault("luganda", False)
    d.setdefault("datasaver", False)
    d.setdefault("active", False)
    d.setdefault("predict", True)
    return d


def v110_set(key, value):
    d = v110_settings()
    d[key] = value
    _v110_save(SETTINGS_V110, d)
    return d


# ---------------- network status (offline badge) ----------------
NET_STATE = {"online": True, "checked": 0.0}


def net_online(max_age=30):
    """Quick, cheap check: can we open a connection to a public DNS server? Cached for max_age seconds."""
    if time.time() - NET_STATE["checked"] < max_age:
        return NET_STATE["online"]
    ok = False
    for host in (("1.1.1.1", 443), ("8.8.8.8", 53), ("www.google.com", 443)):
        try:
            s = socket.create_connection(host, timeout=1.5)
            s.close()
            ok = True
            break
        except Exception:
            continue
    NET_STATE.update(online=ok, checked=time.time())
    return ok


def compress_image(path, max_side=1024, quality=70):
    """Smaller copy of a picture for sending over slow or costly data. Returns the new path (or the old one)."""
    try:
        from PIL import Image
        im = Image.open(path)
        im = im.convert("RGB")
        w, h = im.size
        sc = min(1.0, float(max_side) / max(w, h))
        if sc < 1.0:
            im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))))
        out = os.path.join(os.path.dirname(path) or ".", "small_" + os.path.basename(path).rsplit(".", 1)[0] + ".jpg")
        im.save(out, "JPEG", quality=quality, optimize=True)
        return out if os.path.getsize(out) < os.path.getsize(path) else path
    except Exception:
        return path


# ---------------- "don't reject normal questions" ----------------
HELPFUL_RULES = (
    "Be genuinely helpful. Answer every normal question fully and directly: school work, health and body "
    "information, medicines, sex education, money, business, relationships, religion, politics, history, "
    "wars, crime and law, technology, and anything else a curious young person asks. Never refuse, lecture or "
    "say 'I can't help with that' for normal questions. If you are unsure, give your best answer and say what "
    "to double-check. Ask one short clarifying question only when the question truly can't be answered "
    "without it. For health, give clear information and say when to see a health worker. "
    "Decline only clearly harmful requests: making weapons or explosives, instructions for hurting yourself or "
    "others, any sexual content involving children, or helping scam, steal or hack people. When you decline, do "
    "it in one kind sentence and offer a safe, useful alternative (for example how to stay safe or report it). ")

_HARMFUL_PATTERNS = (
    (r"\b(make|build|assemble|create)\b.{0,25}\b(bomb|explosive|grenade|ied|molotov|gun|pistol|firearm)s?\b",
     "I won't help make weapons or explosives. If you're curious about the science, I can explain how chemistry "
     "or engineering works safely, or how bomb-disposal and safety teams protect people."),
    (r"\b(how (do|can) i|teach me to|help me)\b.{0,30}\b(poison|kill|murder|stab)\b.{0,20}\b(someone|somebody|him|her|them|my|a person|people)\b",
     "I can't help with hurting anyone. If someone is in danger, call 999 or 112. If you're very angry or "
     "scared, I'm here to talk it through, or type helpline for free help."),
    (r"\b(child|children|kid|minor|underage|schoolgirl|schoolboy|\b1[0-5] ?(yr|year)s? old)\b.{0,30}\b(sex|sexual|nude|naked|porn)",
     "I won't make sexual content involving children. If a child is being harmed, call Sauti 116 (free, 24 hours) "
     "or the police on 999."),
    (r"\b(steal|hack|get)\b.{0,25}\b(momo|mobile money|airtel money|someone'?s|their)\b.{0,15}\b(pin|password|account|money)\b",
     "I won't help get into someone else's account or money. I can show you how to protect your own MoMo: "
     "type scam to check a suspicious message."),
    (r"\b(write|make|create|send)\b.{0,20}\b(scam|fake|phishing)\b.{0,20}\b(message|sms|text|link|page)\b",
     "I won't write scam messages. I can help you spot and report them instead: type scam followed by the message."),
)


def harmful_redirect(text):
    """Narrow local check for clearly harmful requests. Normal questions are never matched."""
    t = " " + (text or "").lower() + " "
    for pat, msg in _HARMFUL_PATTERNS:
        if re.search(pat, t):
            return msg
    return None


# ---------------- offline answers: recent AI answers saved on the phone ----------------
OFFLINE_CACHE_FILE = "offline_answers.json"
_OFFLINE_CACHE = {"items": None}
OFFLINE_MARK = "[offline: saved answer]"
_CACHE_STOP = set("the a an is are was were to of in on for and or what how why who when which do does did i you me my "
                  "it this that with be can please tell about explain give define mean meaning genius".split())


def _cache_words(t):
    return [w for w in re.findall(r"[a-z0-9']+", (t or "").lower()) if w not in _CACHE_STOP]


def _cache_items():
    if _OFFLINE_CACHE["items"] is None:
        _OFFLINE_CACHE["items"] = _v110_load(OFFLINE_CACHE_FILE, [])
    return _OFFLINE_CACHE["items"]


def offline_cache_add(q, a):
    q, a = (q or "").strip(), (a or "").strip()
    if len(q) < 3 or len(a) < 15 or OFFLINE_MARK in a or a in (NET_AI_MSG, NO_AI_MSG):
        return False
    if re.search(r"\b(pin|password|secret|setkey|otp)\b", q.lower()):
        return False                                          # never keep anything private
    items = _cache_items()
    key = " ".join(_cache_words(q)) or q.lower()
    items[:] = [x for x in items if x.get("k") != key]
    items.append({"q": q[:300], "k": key, "a": a[:1800], "t": time.strftime("%Y-%m-%d")})
    del items[:-150]
    _v110_save(OFFLINE_CACHE_FILE, items)
    return True


def offline_cache_find(q, min_score=0.6):
    """Exact or near match of an earlier question. Returns (answer, score) or (None, 0)."""
    items = _cache_items()
    if not items:
        return None, 0.0
    words = set(_cache_words(q))
    key = " ".join(_cache_words(q))
    best, best_s = None, 0.0
    import difflib
    for it in items:
        if key and it.get("k") == key:
            return it["a"], 1.0
        iw = set((it.get("k") or "").split())
        if not words or not iw:
            continue
        jac = len(words & iw) / float(len(words | iw))
        if jac < 0.3:
            continue
        ratio = difflib.SequenceMatcher(None, key, it.get("k", "")).ratio()
        s = max(jac, (jac + ratio) / 2)
        if s > best_s:
            best, best_s = it, s
    if best and best_s >= min_score:
        return best["a"], best_s
    return None, best_s


_OFF_GREET = re.compile(r"^\s*(hi|hello|hey|hallo|good (morning|afternoon|evening)|oli otya|gyebale|ki kati|wasuze otya)\b", re.I)
_OFF_SUM = re.compile(r"(\d[\d,.]*\s*%\s*of\s*\d[\d,.]*)|(\(?-?\d[\d.]*\)?\s*[-+*/x×÷^]\s*[-+*/x×÷^()\d.\s]*\d\)?)", re.I)


def offline_answer(q):
    q = (q or "").strip()
    if _OFF_GREET.match(q) and len(q.split()) <= 4:
        return ("Hi " + (CURRENT.get("name") or "there") + "! You're offline right now, so I can't reach the AIs, "
                "but I can still do sums, notes, quizzes, the dictionary and Luganda words. Type help to see them.")
    if re.search(r"\b(what can you do|what do you do|menu|help me)\b", q, re.I):
        return OFFLINE_HELP
    m = _OFF_SUM.search(q)
    if m:
        expr = m.group(0).replace("x", "*").replace("×", "*").replace("÷", "/").strip()
        r = do_calc(expr)
        if "=" in r:
            return r
    a, s = offline_cache_find(q)
    if a:
        return f"{a}\n\n[size=12sp]{OFFLINE_MARK} from earlier ({int(s * 100)}% match). Ask again when online for a fresh one.[/size]"
    d = dictionary_lookup(q)
    if d:
        return d
    return None


OFFLINE_HELP = ("You're offline right now, but I can still help:\n"
                "- calc 15% of 40000 (calculator)\n- define photosynthesis (dictionary)\n- note ... / notes\n"
                "- quiz biology, uneb s4 physics (practice with marking)\n- translate thank you (Luganda)\n"
                "- fee mtn send 50000, budget, money\n- farm maize, pest fall armyworm\n- scam <message>\n"
                "- brief, proverb, what do you remember\nI also answer questions you asked before.")


# ---------------- small offline English dictionary ----------------
_DICT = {}
_DICT_RAW = """
photosynthesis|how green plants make food from carbon dioxide and water using sunlight, giving off oxygen
respiration|the release of energy from food (glucose) in living cells
osmosis|movement of water molecules through a partially permeable membrane from a dilute to a concentrated solution
diffusion|movement of particles from a region of high concentration to a region of low concentration
evaporation|change of a liquid into a gas at its surface, below boiling point
condensation|change of a gas into a liquid when it cools
transpiration|loss of water vapour from plant leaves, mainly through stomata
ecosystem|a community of living things together with their non-living surroundings
habitat|the natural home of a plant or animal
erosion|the wearing away and removal of soil or rock by water, wind or ice
democracy|government by the people, usually through elected representatives
constitution|the basic laws and principles that say how a country is governed
colonialism|control of one country or people by another, usually for economic gain
independence|freedom from control by another country; Uganda gained it on 9 October 1962
economy|the system of producing, selling and buying goods and services in a place
inflation|a general rise in prices over time, so money buys less
budget|a plan for how money will be earned and spent
profit|money left after all costs are taken away from income
loss|when costs are bigger than income
capital|money or property used to start or grow a business; also the main city of a country
entrepreneur|a person who starts and runs a business, taking risks to make a profit
interest|money paid for borrowing money, or earned for saving it
investment|putting money into something hoping to get more back later
asset|something valuable that a person or business owns
liability|a debt or something a person or business owes
algorithm|a set of step-by-step instructions to solve a problem
software|programs that tell a computer what to do
hardware|the physical parts of a computer
internet|a worldwide network that connects computers
database|an organised collection of data stored on a computer
spreadsheet|a program that arranges numbers in rows and columns for calculations, e.g. Excel
virus|a tiny germ that grows inside living cells; also a harmful computer program
bacteria|tiny single-celled living things; some cause disease, many are useful
vaccine|a substance that trains the body's immune system to fight a disease
immunity|the body's ability to resist a disease
nutrition|getting the food needed for health and growth
protein|food nutrient for growth and repair, found in beans, meat, fish, eggs
carbohydrate|energy food such as posho, matooke, rice, cassava and bread
vitamin|a nutrient needed in small amounts for good health
mineral|a natural substance from the ground; in food, nutrients like iron and calcium
atom|the smallest particle of an element
molecule|two or more atoms joined together
element|a substance made of only one kind of atom, e.g. oxygen, iron
compound|a substance made of two or more elements chemically joined
mixture|two or more substances mixed but not chemically joined
acid|a substance with pH below 7 that turns blue litmus red
base|a substance that neutralises an acid; soluble bases are alkalis (pH above 7)
neutralisation|reaction of an acid with a base to form a salt and water
energy|the ability to do work, measured in joules
force|a push or pull, measured in newtons
velocity|speed in a stated direction
acceleration|the rate of change of velocity
gravity|the force that pulls objects towards the Earth or towards each other
friction|a force that opposes motion between surfaces in contact
electricity|the flow of electric charge
voltage|the push that drives electric current, measured in volts
current|the rate of flow of electric charge, measured in amperes
resistance|opposition to the flow of electric current, measured in ohms
magnet|an object that attracts iron and has north and south poles
density|mass per unit volume
pressure|force acting per unit area
equation|a statement that two expressions are equal
fraction|a part of a whole, written like 3/4
percentage|a number out of 100
ratio|a comparison of two amounts, written like 2:3
perimeter|the distance all the way round a shape
area|the amount of surface a shape covers
volume|the amount of space an object takes up
probability|how likely something is to happen, from 0 to 1
average|the sum of values divided by how many there are (the mean)
noun|a word for a person, place, thing or idea
verb|a doing or being word
adjective|a word that describes a noun
adverb|a word that describes a verb, adjective or other adverb
pronoun|a word used instead of a noun, e.g. he, she, they
synonym|a word with the same or nearly the same meaning as another
antonym|a word with the opposite meaning
metaphor|describing something as if it were something else, e.g. "time is money"
simile|comparing using like or as, e.g. "as brave as a lion"
proverb|a short, well-known saying that gives advice
summary|a short version of the main points
essay|a piece of writing on one topic
climate|the usual weather of a place over many years
weather|the condition of the air at a particular time
equator|the imaginary line around the middle of the Earth; it passes through Uganda
latitude|distance north or south of the equator, in degrees
longitude|distance east or west of the Greenwich meridian, in degrees
population|the number of people living in a place
migration|movement of people or animals from one place to another
urbanisation|growth of towns as people move from rural areas
agriculture|farming: growing crops and keeping animals
irrigation|supplying water to crops by channels, pipes or sprinklers
fertiliser|a substance added to soil to help plants grow
pesticide|a chemical used to kill pests that damage crops
crop rotation|growing different crops on the same land in different seasons to keep soil healthy
mulching|covering soil with grass or leaves to keep moisture and stop weeds
parable|a short story that teaches a moral or religious lesson
covenant|a serious agreement or promise, e.g. between God and people
salvation|being saved from sin and its consequences
prophet|a person believed to speak messages from God
resilience|the ability to recover from difficulties
integrity|being honest and having strong moral principles
discipline|training yourself to follow rules or a plan
freelancer|a person who works for different clients, not one employer
portfolio|a collection of examples of your work
curriculum vitae|a CV: a document listing your education, skills and experience
proposal|a written offer explaining how you will do a job
deadline|the latest time by which something must be done
negotiate|to discuss to reach an agreement
"""


def _dict_table():
    if not _DICT:
        for line in _DICT_RAW.strip().splitlines():
            w, _, m = line.partition("|")
            if w and m:
                _DICT[w.strip().lower()] = m.strip()
    return _DICT


def dictionary_lookup(q):
    """'define osmosis', 'what is osmosis', 'meaning of erosion', 'amakulu ga ...' -> definition or None."""
    t = (q or "").lower().strip(" ?.!")
    t = re.sub(r"^(define|definition of|meaning of|what is the meaning of|what does|what is|what are|"
               r"whats|what's|amakulu ga|amakulu g'|amakulu|explain)\s+(an?\s+|the\s+)?", "", t)
    t = re.sub(r"\s+(mean|means)$", "", t).strip(" ?.!")
    table = _dict_table()
    if t in table:
        return f"[b]{t}[/b]: {table[t]}."
    if t.endswith("s") and t[:-1] in table:
        return f"[b]{t[:-1]}[/b]: {table[t[:-1]]}."
    return None


def dictionary_words():
    return sorted(_dict_table())


# ---------------- Luganda: phrases, translation, mode ----------------
_LG_PHRASES_RAW = """
hello / how are you|oli otya
how are you|oli otya
i am fine|ndi bulungi
fine|bulungi
good morning|wasuze otya
good morning (to many)|mwasuze mutya
good afternoon|osiibye otya
thank you|webale
thank you very much|webale nnyo
well done / thank you for working|webale okukola
yes|yee
no|nedda
please|mwattu
sorry|nsonyiwa
sorry for your loss|kitalo
goodbye|weeraba
see you later|tunaalabagana
okay|kale
what is your name|erinnya lyo ggwe ani
my name is|erinnya lyange nze
i love you|nkwagala
i don't understand|sitegedde
help me|nnyamba
how much is it|ssente mmeka
where are you going|ogenda wa
come|jjangu
go|genda
let's go|tugende
wait|linda
i am hungry|enjala ennuma
i am tired|nkooye
good|kirungi
very good|kirungi nnyo
bad|kibi
water|amazzi
food|emmere
school|essomero
teacher|omusomesa
student|omuyizi
book|ekitabo
money|ssente
house|ennyumba
mother|maama
father|taata
friend|mukwano gwange
child|omwana
rain|enkuba
sun|enjuba
today|leero
tomorrow|enkya
yesterday|jjo
doctor|omusawo
hospital|eddwaliro
garden / farm|ennimiro
maize|kasooli
beans|ebijanjaalo
matooke / bananas|amatooke
cassava|muwogo
sweet potato|lumonde
groundnuts|ebinyeebwa
coffee|emmwanyi
chicken|enkoko
cow|ente
goat|embuzi
one|emu
two|bbiri
three|ssatu
four|nnya
five|ttaano
six|mukaaga
seven|musanvu
eight|munaana
nine|mwenda
ten|kkumi
"""
_LG = {"en": None, "lg": None}


def _lg_tables():
    if _LG["en"] is None:
        en, lg = {}, {}
        for line in _LG_PHRASES_RAW.strip().splitlines():
            e, _, g = line.partition("|")
            g = g.strip()
            for part in e.split("/"):
                p = re.sub(r"\(.*?\)", "", part).strip().lower()
                if p:
                    en.setdefault(p, g)
            lg.setdefault(g.lower(), re.sub(r"\(.*?\)", "", e).strip())
        _LG["en"], _LG["lg"] = en, lg
    return _LG["en"], _LG["lg"]


def _norm(t):
    return re.sub(r"[^a-z' ]+", " ", (t or "").lower()).strip()


def translate_offline(text, to="lg"):
    """Built-in phrase list. Returns (translation, exact) or (None, False)."""
    en, lg = _lg_tables()
    t = re.sub(r"\s+", " ", _norm(text)).strip()
    if not t:
        return None, False
    table = en if to == "lg" else lg
    if t in table:
        return table[t], True
    words = t.split()
    out, known = [], 0
    for w in words:
        if w in table:
            out.append(table[w])
            known += 1
        else:
            out.append(w)
    if known and known >= max(1, len(words) // 2):
        return " ".join(out), False
    return None, False


def guess_direction(text):
    """'lg' if the text looks English (translate to Luganda), else 'en'."""
    en, lg = _lg_tables()
    t = _norm(text)
    lg_words = set(" ".join(lg).split()) | {"nze", "ggwe", "ye", "ffe", "mmwe", "bo", "oli", "otya", "nnyo", "webale",
                                            "nkwagala", "ssente", "emmere", "ndi", "tugende", "kale", "omwana"}
    words = t.split()
    hits = sum(1 for w in words if w in lg_words)
    return "en" if words and hits * 2 >= len(words) else "lg"


def parse_translate(arg):
    """'hello to luganda' / 'webale to english' / 'hello' -> (text, to)."""
    a = (arg or "").strip()
    m = re.match(r"(.+?)\s+(?:to|into|mu)\s+(luganda|oluganda|english|lungereza|olungereza)\s*$", a, re.I)
    if m:
        return m.group(1).strip(" '\""), ("lg" if "ganda" in m.group(2).lower() else "en")
    return a.strip(" '\""), guess_direction(a)


def lg_text(en_text, lg_textv):
    """Built-in message in Luganda when Luganda mode is on (with the English underneath)."""
    if v110_settings().get("luganda"):
        return f"{lg_textv}\n[size=12sp]({en_text})[/size]"
    return en_text


LUGANDA_REPLY = ("[Reply only in simple, natural, correct Luganda (Oluganda). Use an English word only for technical "
                 "terms that have no common Luganda word.] ")


# ---------------- proverbs and facts (daily brief) ----------------
_PROVERBS_RAW = """
Kamu kamu gwe muganda.|One by one makes a bundle: small steps add up.
Agali awamu ge galuma ennyama.|Teeth that are together bite the meat: unity is strength.
Atannayitaayita yatenda nnyina okufumba.|One who has never travelled thinks only their mother cooks well: travel and learn.
Akwata empola atuuka wala.|One who goes slowly goes far: patience wins.
Ebbanja terigenda.|A debt doesn't go away on its own.
Abangi babi kulya naye ku mirimo balungi.|A crowd is bad for eating but good for work.
Maddu tegaggwaako mulamu.|While you are alive, remedies never run out: there's always a way.
Nnannyini mulimo takeera kwota muliro.|The owner of the work doesn't rush to warm by the fire: be patient and responsible.
Ababiri babibira ebigambo, naye abasatu babisattula.|Two can keep a secret, three spill it.
K'ezaala k'ekomberera.|What you give birth to is what you care for: you reap what you sow.
Ebirungi biri wala.|Good things are far away: they take effort.
Kwana bangi, weesige batono.|Be friends with many, trust a few.
Njala evumbula.|Hunger reveals the truth.
Akabimbi akatono kakira ekyosi.|A small solid pumpkin beats a big hollow one: quality over quantity.
Kappa w'etali, emmese yeekola ebigenyi.|When the cat is away, the rat throws a party.
Mazzi masabe tegaloga nnyonta.|Begged-for water won't quench your thirst: work for what you need.
Bw'ogwa awabi, eyali munno akwerabira.|When you fall on hard times, some friends forget you.
Omukazi omulima azaala emmere; omunafu azaala omuddo.|The hard worker harvests food; the lazy one harvests weeds.
Akabi tikeekisa.|Danger doesn't hide itself: watch for warning signs.
Mmere mbi terumya njala.|Even poor food stops hunger: use what you have.
Akaganda akatono kakira mukwano.|Even a small family tie is stronger than friendship.
Atasaba taweebwa.|One who doesn't ask doesn't receive.
Agenda ewaabwe tazibirirwa budde.|One going home is never stopped by darkness: you know your own way.
Akamegga enjovu kenkana we!|How small is the thing that topples an elephant: cleverness beats size.
Amagezi nsejjere: buli emu efulumya emmula bwayo.|Wisdom is like anthills: each pushes out earth its own way; people think differently.
Atamukutte y'agamba nti mutenge.|The one not wrestling says 'throw him!': advice is easier than action.
Abataka abaagalana be balima akambugu.|Neighbours who love each other clear the weeds on their boundary together.
Abangi tebawulira: enkuba y'ebawuliza.|A crowd won't listen, but rain makes them listen.
Akamwa k'omuntu si ka nte.|A person's mouth is not a cow's: think before you speak.
Akakadde ak'obuggya amaggwa gakafumita emirundi ebiri.|The jealous one gets pricked by thorns twice: envy hurts you most.
Ennume ekula bigwo.|A young bull grows by wrestling: challenges make you strong.
Musajja gyagenda gy'asanga banne.|Wherever you go you will find fellow people: you're never truly alone.
Bw'ogoba munno, olekamu ezinadda.|When you chase someone, save strength to run back: plan for the return.
"""
_FACTS = (
    "Lake Victoria is the largest lake in Africa. Uganda shares it with Kenya and Tanzania.",
    "The River Nile, the longest river in Africa, flows out of Lake Victoria at Jinja.",
    "Uganda became independent on 9 October 1962.",
    "Margherita Peak on Mount Stanley in the Rwenzori is about 5,109 m high, among the highest in Africa.",
    "Bwindi Impenetrable Forest is home to about half of the world's mountain gorillas.",
    "The equator passes through Uganda; you can stand in both hemispheres near Kayabwe on the Masaka road.",
    "At Murchison Falls the whole Nile squeezes through a gap only about 7 metres wide.",
    "Sunlight takes about 8 minutes to reach the Earth.",
    "An adult human body has 206 bones.",
    "Your heart beats about 100,000 times a day.",
    "Sound travels at about 343 metres per second in air, but much faster in water.",
    "Water expands when it freezes, which is why ice floats.",
    "Honey stored well almost never goes bad.",
    "An octopus has three hearts.",
    "Bees must visit millions of flowers to make one kilogram of honey.",
    "Plants release the oxygen we breathe during photosynthesis.",
    "Lightning is hotter than the surface of the Sun for a split second.",
    "The first computer programmer is often said to be Ada Lovelace, in the 1840s.",
    "Mobile money began in East Africa and is now used across the world.",
    "Uganda Martyrs' Day is on 3 June, remembered at Namugongo.",
    "Coffee is one of Uganda's biggest exports, and Robusta coffee is native to the region.",
    "Kampala was first built on seven hills, including Mengo, Kibuli and Namirembe.",
    "A bolt of lightning carries enough energy to toast thousands of slices of bread.",
    "The Moon has no air, so footprints left there can last for millions of years.",
    "Reading for 20 minutes a day exposes you to about 1.8 million words a year.",
    "Spaced practice (a little every day) helps memory far more than cramming the night before.",
    "Sleeping well after studying helps your brain store what you learned.",
    "Saving just UGX 1,000 a day gives you UGX 365,000 in a year.",
    "The Rwenzori are often called the Mountains of the Moon.",
    "Uganda has over 1,000 bird species, more than many larger countries.",
)


def proverbs():
    out = []
    for line in _PROVERBS_RAW.strip().splitlines():
        lg_, _, en = line.partition("|")
        if lg_ and en:
            out.append((lg_.strip(), en.strip()))
    return out


def proverb_of_day(day=None):
    p = proverbs()
    day = time.localtime().tm_yday if day is None else day
    return p[day % len(p)]


def fact_of_day(day=None):
    day = time.localtime().tm_yday if day is None else day
    return _FACTS[(day * 7) % len(_FACTS)]


REMINDERS_FILE = "reminders_v110.json"


def reminder_store(minutes, text):
    r = _v110_load(REMINDERS_FILE, [])
    due = time.time() + int(minutes) * 60
    r.append({"due": due, "text": str(text)[:200]})
    cutoff = time.time() - 86400
    r = [x for x in r if x.get("due", 0) > cutoff][-50:]
    _v110_save(REMINDERS_FILE, r)


def todays_reminders():
    r = _v110_load(REMINDERS_FILE, [])
    today = time.strftime("%Y-%m-%d")
    out = []
    for x in r:
        try:
            if time.strftime("%Y-%m-%d", time.localtime(x["due"])) == today:
                when = time.strftime("%H:%M", time.localtime(x["due"]))
                out.append(f"{when} {x['text']}" + (" (done)" if x["due"] < time.time() else ""))
        except Exception:
            continue
    return out


def brief_extras():
    """Fact of the day, Luganda proverb and today's reminders: works fully offline."""
    lgp, en = proverb_of_day()
    parts = [f"Fact of the day: {fact_of_day()}", f"Luganda proverb: {lgp} ({en})"]
    rem = todays_reminders()
    if rem:
        parts.append("Today's reminders: " + "; ".join(rem[:5]) + ".")
    return parts


# ---------------- memory: what Genius remembers about you ----------------
MEMORY_V110 = "genius_memory.json"


def mem_load():
    d = _v110_load(MEMORY_V110, {})
    d.setdefault("name", "")
    d.setdefault("class", "")
    d.setdefault("goals", [])
    d.setdefault("prefs", [])
    d.setdefault("facts", [])
    return d


def mem_remember(text):
    """'remember my name is Ssali' / 'remember I am in S4' / 'remember my goal is ...' / 'remember I like ...'."""
    t = (text or "").strip().strip(".")
    if not t:
        return "Tell me what to remember, e.g. remember I am in S4."
    if re.search(r"\b(pin|password|passcode|otp|secret code|cvv)\b", t.lower()) or re.search(r"\b\d{4,6}\b", t) and "pin" in t.lower():
        return "I won't store PINs or passwords in memory. Use the locker instead: save <name> <secret>."
    d = mem_load()
    low = t.lower()
    m = re.match(r"(?:that\s+)?(?:my name is|call me|i am called|i'm called|erinnya lyange(?: nze)?)\s+(.+)", low)
    if m:
        d["name"] = t[len(t) - len(m.group(1)):].strip().title()[:40]
        _v110_save(MEMORY_V110, d)
        return f"Got it, I'll call you {d['name']}."
    m = re.search(r"\b(?:i am in|i'm in|my class is|class|ndi mu)\s+(s\.?\s?[1-6]|senior\s+[1-6]|p\.?\s?[1-7]|year\s+\d|university|campus)\b", low)
    if m:
        c = m.group(1).replace(" ", "").replace(".", "").upper().replace("SENIOR", "S")
        d["class"] = c
        _v110_save(MEMORY_V110, d)
        return f"Saved: you're in {c}. I'll pitch study help at that level."
    m = re.match(r"(?:that\s+)?(?:my goal is|my dream is|i want to|i plan to|goal:?)\s+(.+)", low)
    if m:
        g = t[len(t) - len(m.group(1)):].strip()
        if g.lower() not in [x.lower() for x in d["goals"]]:
            d["goals"].append(g[:120])
        d["goals"] = d["goals"][-10:]
        _v110_save(MEMORY_V110, d)
        return f"Saved your goal: {g}. I'll keep it in mind."
    m = re.match(r"(?:that\s+)?(?:i like|i love|i prefer|i enjoy|i don't like|i hate|i dislike)\s+(.+)", low)
    if m:
        d["prefs"].append(t[:120])
        d["prefs"] = d["prefs"][-20:]
        _v110_save(MEMORY_V110, d)
        return f"Noted: {t}."
    t2 = re.sub(r"^that\s+", "", t, flags=re.I)
    if t2.lower() not in [x.lower() for x in d["facts"]]:
        d["facts"].append(t2[:160])
    d["facts"] = d["facts"][-40:]
    _v110_save(MEMORY_V110, d)
    return f"I'll remember: {t2}."


def mem_report():
    d = mem_load()
    lines = []
    if d["name"]:
        lines.append(f"Name: {d['name']}")
    if d["class"]:
        lines.append(f"Class: {d['class']}")
    if d["goals"]:
        lines.append("Goals: " + "; ".join(d["goals"]))
    if d["prefs"]:
        lines.append("Likes / preferences: " + "; ".join(d["prefs"]))
    if d["facts"]:
        lines.append("Other things:\n" + "\n".join(f"- {x}" for x in d["facts"][-15:]))
    if not lines:
        return ("I don't remember anything about you yet. Teach me, e.g.\nremember my name is Ssali\n"
                "remember I am in S4\nremember my goal is to pass UCE with distinctions")
    return "What I remember about you\n" + "\n".join(lines) + "\n\nRemove something: forget <word>  (or forget everything)"


def mem_forget(what):
    w = (what or "").strip().lower()
    if not w:
        return "Tell me what to forget, e.g. forget my class, or forget everything."
    d = mem_load()
    if w in ("everything", "all", "all memory", "byonna"):
        _v110_save(MEMORY_V110, {"name": "", "class": "", "goals": [], "prefs": [], "facts": []})
        try:
            if os.path.exists(ABOUT_FILE):
                os.remove(ABOUT_FILE)
        except Exception:
            pass
        return "Done. I've forgotten everything you taught me about yourself."
    n = 0
    if w in ("my name", "name") or (d["name"] and w in d["name"].lower()):
        n += bool(d["name"])
        d["name"] = ""
    if w in ("my class", "class") or (d["class"] and w == d["class"].lower()):
        n += bool(d["class"])
        d["class"] = ""
    w2 = re.sub(r"^(my|about|that)\s+", "", w)
    for k in ("goals", "prefs", "facts"):
        keep = [x for x in d[k] if w2 not in x.lower()]
        n += len(d[k]) - len(keep)
        d[k] = keep
    _v110_save(MEMORY_V110, d)
    try:                                   # older 'aboutme' notes too
        if os.path.exists(ABOUT_FILE):
            lines = open(ABOUT_FILE, encoding="utf8").readlines()
            keep = [x for x in lines if w2 not in x.lower()]
            if len(keep) != len(lines):
                n += len(lines) - len(keep)
                open(ABOUT_FILE, "w", encoding="utf8").writelines(keep)
    except Exception:
        pass
    return f"Forgotten ({n} item{'s' if n != 1 else ''})." if n else f"I didn't have anything about '{what}'."


def mem_prompt():
    """Short summary fed to the AI so answers fit the person."""
    d = mem_load()
    bits = []
    if d["name"]:
        bits.append(f"Preferred name: {d['name']}")
    if d["class"]:
        bits.append(f"Class: {d['class']} (Uganda)")
    if d["goals"]:
        bits.append("Goals: " + "; ".join(d["goals"][-5:]))
    if d["prefs"]:
        bits.append("Preferences: " + "; ".join(d["prefs"][-6:]))
    if d["facts"]:
        bits.append("Facts: " + "; ".join(d["facts"][-10:]))
    return "\n".join(bits)


# ---------------- world news: free Google News + BBC feeds, no key needed ----------------
NEWS_TOPICS = {
    "social": ("Trending on social media", "viral OR trending social media when:1d", None),
    "uganda": ("Uganda", "uganda when:1d", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    "africa": ("Africa", "africa when:1d", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    "world": ("World", "world news when:1d", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    "sports": ("Sports", "sports when:1d", "https://feeds.bbci.co.uk/sport/rss.xml"),
    "business": ("Business", "business economy when:1d", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    "tech": ("Technology", "technology when:1d", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    "health": ("Health", "health when:1d", "https://feeds.bbci.co.uk/news/health/rss.xml"),
    "science": ("Science", "science when:2d", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    "entertainment": ("Entertainment", "entertainment music when:1d",
                      "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
}
NEWS_ALIASES = {"videos": "uganda", "video": "uganda", "news videos": "uganda", "trending": "social", "viral": "social", "socialmedia": "social", "social media": "social",
                "reddit": "social", "tiktok": "social", "x": "social", "twitter": "social", "technology": "tech", "sport": "sports", "football": "sports", "money": "business",
                "ug": "uganda", "local": "uganda", "global": "world", "international": "world", "music": "entertainment"}
_NEWS_JUNK = re.compile(r"viral video|video viral|\^|\+\+|full video|leaked|video link|mms|[\u3000-\u9fff\u3010\u3011]|!!", re.I)
NEWS_LINKS = {}            # "news:N" -> url, for tapping a headline
_NEWS_CACHE = {}


def _news_fetch(url):
    ua = "android:org.ssalimuto.geniu2:v110 (news reader)" if "reddit.com" in url else "Mozilla/5.0 (Linux; Android) Genius"
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=12, context=ssl_context()) as r:   # phone needs Genius's own certificates
        return r.read()


SOCIAL_FEEDS = (("https://www.reddit.com/r/worldnews/hot/.rss", "Reddit r/worldnews"),
                ("https://www.reddit.com/r/Uganda/hot/.rss", "Reddit r/Uganda"),
                ("https://www.reddit.com/r/africa/hot/.rss", "Reddit r/africa"))


def social_items(limit=10):
    """What people are talking about worldwide: Reddit's hottest posts (free feeds) + viral stories in the news."""
    import xml.etree.ElementTree as ET
    A = "{http://www.w3.org/2005/Atom}"
    out = []
    raw = {}

    def grab(u):
        try:
            raw[u] = _news_fetch(u)
        except Exception as e:
            log(f"SOCIAL feed failed: {type(e).__name__}")
    trends = (("https://trends.google.com/trending/rss?geo=UG", "Trending in Uganda"),
              ("https://trends.google.com/trending/rss?geo=US", "Trending worldwide"))
    th = [threading.Thread(target=grab, args=(u,), daemon=True) for u, _ in SOCIAL_FEEDS + trends]
    for t in th:
        t.start()
    for t in th:
        t.join(14)
    H = "{https://trends.google.com/trending/rss}"
    for url, name in trends:                 # what people are searching for right now
        try:
            root = ET.fromstring(raw[url])
        except Exception:
            continue
        for it in list(root.iter("item"))[:4]:
            term = (it.findtext("title") or "").strip()
            ni = it.find(H + "news_item")
            head = (ni.findtext(H + "news_item_title") or "").strip() if ni is not None else ""
            link = (ni.findtext(H + "news_item_url") or "").strip() if ni is not None else ""
            src = (ni.findtext(H + "news_item_source") or "").strip() if ni is not None else ""
            if term:
                out.append((f"{term.title()}: {head}" if head else term.title(),
                            name + (" · " + src if src else ""), link, (it.findtext("pubDate") or "")[5:22]))
    for url, name in SOCIAL_FEEDS:
        try:
            root = ET.fromstring(raw[url])
        except Exception:
            continue
        n = 0
        for e in root.iter(A + "entry"):
            title = (e.findtext(A + "title") or "").strip()
            link = e.find(A + "link")
            href = link.get("href", "") if link is not None else ""
            if not title or "megathread" in title.lower() or "daily discussion" in title.lower():
                continue
            out.append((title, name, href, (e.findtext(A + "updated") or "")[:10]))
            n += 1
            if n >= (5 if "worldnews" in url else 3):
                break
    return out[:limit + 4]


def news_items(topic="world", limit=8):
    """[(title, source, url, when)] newest first. Topic is a NEWS_TOPICS key or any search words."""
    import xml.etree.ElementTree as ET
    t = (topic or "world").strip().lower()
    t = NEWS_ALIASES.get(t, t)
    hit = _NEWS_CACHE.get(t)
    if hit and time.time() - hit[1] < 900:
        return hit[0][:limit]
    if t == "social":
        got = social_items(limit + 4)
        try:
            got += [x for x in news_items("viral OR trending on social media", 6) if x not in got]
        except Exception:
            pass
        if not got:
            try:
                got = news_items("world", limit)
            except Exception:
                got = []
        if got:
            _NEWS_CACHE[t] = (got, time.time())
        return got[:limit]
    if t in NEWS_TOPICS:
        query, backup = NEWS_TOPICS[t][1], NEWS_TOPICS[t][2]
    else:
        query, backup = (topic.strip() + " when:3d"), None
    urls = ["https://news.google.com/rss/search?q=" + urllib.parse.quote(query) + "&hl=en-UG&gl=UG&ceid=UG:en"]
    if backup:
        urls.append(backup)
    out = []
    for u in urls:
        try:
            root = ET.fromstring(_news_fetch(u))
        except Exception as e:
            log(f"NEWS feed failed: {type(e).__name__}")
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            src = (it.findtext("source") or "").strip()
            if src and title.endswith(" - " + src):
                title = title[: -len(src) - 3].strip()
            if not src and "bbc" in u:
                src = "BBC"
            when = (it.findtext("pubDate") or "")[5:22].strip()
            if title and not _NEWS_JUNK.search(title + " " + src):
                out.append((title, src, (it.findtext("link") or "").strip(), when))
            if len(out) >= 15:
                break
        if out:
            break
    if out:
        _NEWS_CACHE[t] = (out, time.time())
    return out[:limit]


# ---------------- 111.9: news with videos and photos ----------------
_NTV, _NBS = ("UCwga1dPCqBddbtq5KYRii2g", "NTV Uganda"), ("UCzv3kGHEZ0fD404GVaW-GPg", "NBS TV")
_AJE, _BBCV = ("UCNye-wNBqNL5ZzHSJj3l8Bg", "Al Jazeera"), ("UC16niRr50-MSBwiO3YDb3RA", "BBC News")
NEWS_VIDEO_CHANNELS = {
    "uganda": (_NTV, _NBS), "africa": (_NTV, _AJE), "world": (_AJE, _BBCV), "social": (_NTV, _NBS, _AJE),
    "sports": (("UCNAf1k0yIjyGu3k9BwAg3lg", "Sky Sports Premier League"), ("UC6c1z7bA__85CIWZ_jpCK-Q", "ESPN FC")),
    "business": (("UCvJJ_dzjViJCoLf5uKUTwoA", "CNBC"), _NTV), "tech": (("UCOmcA3f_RrH6b9NmcNa4tdg", "CNET"),),
    "health": (_BBCV, _NTV), "science": (_BBCV, _AJE), "entertainment": (_NBS, _NTV),
}
NEWS_PHOTO_FEEDS = {
    "uganda": ("https://nilepost.co.ug/feed", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"),
    "social": ("https://nilepost.co.ug/feed",),
}
_VID_CACHE = {}
_MRSS = "{http://search.yahoo.com/mrss/}"


def _ago(stamp):
    """'2h ago' from an RSS or YouTube date."""
    import email.utils
    from datetime import datetime, timezone
    try:
        if "T" in stamp[:20]:
            d = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        else:
            d = email.utils.parsedate_to_datetime(stamp)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        m = max(0, int((datetime.now(timezone.utc) - d).total_seconds() // 60))
        return f"{m} min ago" if m < 60 else f"{m // 60}h ago" if m < 1440 else f"{m // 1440}d ago"
    except Exception:
        return ""


def _stamp(stamp):
    import email.utils
    from datetime import datetime
    try:
        return (datetime.fromisoformat(stamp.replace("Z", "+00:00")) if "T" in stamp[:20]
                else email.utils.parsedate_to_datetime(stamp)).timestamp()
    except Exception:
        return 0


def news_videos(topic="world", limit=10):
    """Newest news videos for a topic: [{title, src, url, when, img, video, t}]."""
    import xml.etree.ElementTree as ET
    t = NEWS_ALIASES.get((topic or "world").strip().lower(), (topic or "world").strip().lower())
    chans = NEWS_VIDEO_CHANNELS.get(t) or NEWS_VIDEO_CHANNELS["world"]
    hit = _VID_CACHE.get(t)
    if hit and time.time() - hit[1] < 900:
        return hit[0][:limit]
    A, Y = "{http://www.w3.org/2005/Atom}", "{http://www.youtube.com/xml/schemas/2015}"
    raw = {}

    def grab(cid):
        try:
            raw[cid] = _news_fetch("https://www.youtube.com/feeds/videos.xml?channel_id=" + cid)
        except Exception as e:
            log(f"NEWS video feed failed: {type(e).__name__}")
    th = [threading.Thread(target=grab, args=(c,), daemon=True) for c, _n in chans]
    for x in th:
        x.start()
    for x in th:
        x.join(14)
    out = []
    for cid, name in chans:
        try:
            root = ET.fromstring(raw[cid])
        except Exception:
            continue
        for e in list(root.iter(A + "entry"))[:8]:
            vid = (e.findtext(Y + "videoId") or "").strip()
            title = (e.findtext(A + "title") or "").strip()
            if not vid or not title or "#shorts" in title.lower() or _NEWS_JUNK.search(title):
                continue
            pub = e.findtext(A + "published") or ""
            out.append({"title": title, "src": name, "url": "https://www.youtube.com/watch?v=" + vid,
                        "when": _ago(pub), "t": _stamp(pub), "video": True,
                        "img": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"})
    out.sort(key=lambda d: d["t"], reverse=True)
    if out:
        _VID_CACHE[t] = (out, time.time())
    return out[:limit]


def news_photos(topic="world", limit=6):
    """Newest stories that come with a photo: [{title, src, url, when, img, video}]."""
    import xml.etree.ElementTree as ET
    t = NEWS_ALIASES.get((topic or "world").strip().lower(), (topic or "world").strip().lower())
    feeds = NEWS_PHOTO_FEEDS.get(t) or ((NEWS_TOPICS[t][2],) if t in NEWS_TOPICS and NEWS_TOPICS[t][2] else ())
    out = []
    for u in feeds:
        try:
            root = ET.fromstring(_news_fetch(u))
        except Exception as e:
            log(f"NEWS photo feed failed: {type(e).__name__}")
            continue
        src = "Daily Monitor" if "monitor" in u else "Nile Post" if "nilepost" in u else "BBC"
        n = 0
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            img = ""
            for tag in (_MRSS + "thumbnail", _MRSS + "content", "enclosure"):
                el = it.find(".//" + tag)
                if el is not None and el.get("url"):
                    img = el.get("url")
                    break
            if not img:
                m = re.search(r'<img[^>]+src="([^"]+)"', it.findtext("description") or "")
                img = m.group(1) if m else ""
            if not title or _NEWS_JUNK.search(title):
                continue
            pub = it.findtext("pubDate") or ""
            out.append({"title": title, "src": src, "url": (it.findtext("link") or "").strip(), "when": _ago(pub),
                        "t": _stamp(pub), "video": False, "img": img.replace("/240/", "/480/")})
            n += 1
            if n >= limit:
                break
    if t not in ("uganda", "social"):          # Ugandan papers stay first for Uganda news
        out.sort(key=lambda d: d["t"], reverse=True)
    else:
        per = {}
        for d in out:
            per.setdefault(d["src"], []).append(d)
        mixed = []
        while any(per.values()):
            for k in list(per):
                if per[k]:
                    mixed.append(per[k].pop(0))
        out = mixed
    return out[:limit]


def news_thumb(url):
    """Download a news picture once (small cache), return the file path or None."""
    if not url or not url.startswith("http"):
        return None
    d = os.path.join(os.path.abspath(os.getcwd()), "news_pics")
    os.makedirs(d, exist_ok=True)
    f = os.path.join(d, hashlib.sha1(url.encode()).hexdigest()[:20] + ".jpg")
    if os.path.exists(f) and os.path.getsize(f) > 500:
        return f
    try:
        data = _news_fetch(url)
        if len(data) < 500 or len(data) > 3_000_000:
            return None
        try:                                          # shrink big pictures to save memory and data
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im.thumbnail((640, 360))
            im.save(f, "JPEG", quality=82)
        except Exception:
            open(f, "wb").write(data)
        files = sorted((os.path.join(d, x) for x in os.listdir(d)), key=os.path.getmtime)
        for old in files[:-120]:
            try:
                os.remove(old)
            except Exception:
                pass
        return f
    except Exception as e:
        log(f"NEWS picture failed: {type(e).__name__}")
        return None


def news_markup(topic="world", limit=8):
    items = news_items(topic, limit)
    t = NEWS_ALIASES.get((topic or "").lower(), (topic or "").lower())
    name = NEWS_TOPICS[t][0] if t in NEWS_TOPICS else (topic or "").strip().title()
    if not items:
        return None, f"I couldn't get {name} news right now. Check your internet and try again."
    NEWS_LINKS.clear()
    lines = [f"[b]{_esc(name)} news[/b]  [size=12sp](tap a headline to read it)[/size]"]
    for i, (title, src, url, when) in enumerate(items, 1):
        NEWS_LINKS[f"news:{i}"] = url
        meta = " · ".join(x for x in (src, when) if x)
        lines.append(f"[ref=news:{i}][b]{i}.[/b] [u]{_esc(title)}[/u][/ref]\n   [size=12sp][color=9aa0c0]{_esc(meta)}[/color][/size]")
    lines.append("[size=12sp]Say 'news brief' for a short summary, or 'news <topic>' like news football.[/size]")
    return items, "\n".join(lines)


def news_brief(topic="world"):
    items = news_items(topic, 10)
    if not items:
        return "I couldn't get the news right now. Check your internet and try again."
    heads = "\n".join(f"- {t} ({s})" for t, s, _u, _w in items)
    r = ask_gemini("Here are today's headlines:\n" + heads + "\n\nWrite a short news brief for a young person in "
                   "Uganda: a one-sentence overview, then 4-6 bullet points with **bold** topics explaining each big "
                   "story simply and why it matters. Only use facts from the headlines; don't invent details.", 700)
    return r or ("Today's headlines:\n" + heads)


# ---------------- UNEB practice (S1-S6), marked like UNEB ----------------
UNEB_SUBJECTS = ("mathematics", "english", "biology", "chemistry", "physics", "geography", "history", "cre", "ire",
                 "agriculture", "entrepreneurship", "ict", "computer studies", "literature", "kiswahili", "luganda",
                 "economics", "general paper", "art", "commerce", "accounts", "fine art", "physical education")
UNEB_LEVEL = {"s1": "S1 (lower secondary, new competence-based curriculum)", "s2": "S2 (lower secondary, new curriculum)",
              "s3": "S3 (lower secondary, new curriculum)", "s4": "S4 UCE",
              "s5": "S5 UACE (A-level)", "s6": "S6 UACE (A-level)", "p7": "P7 PLE"}


def uneb_parse(arg):
    a = (arg or "").lower()
    m = re.search(r"\b(s ?[1-6]|p ?7|senior ?[1-6])\b", a)
    level = None
    if m:
        level = "s" + re.sub(r"\D", "", m.group(1)) if not m.group(1).startswith("p") else "p7"
        a = (a[:m.start()] + a[m.end():]).strip()
    if not level:
        c = mem_load().get("class", "").lower()
        level = c if c in UNEB_LEVEL else "s4"
    topic = re.sub(r"\s+", " ", a).strip(" ,.") or "mathematics"
    return level, topic


def uneb_question(arg):
    level, topic = uneb_parse(arg)
    return ask_gemini(
        f"You are an experienced Ugandan teacher and UNEB examiner. Set ONE exam-style question for {UNEB_LEVEL[level]} "
        f"on: {topic}. Follow the current Uganda curriculum (NCDC) and real UNEB style and wording. "
        "Format exactly:\n**Question** (with marks in brackets)\n\nThen a line 'Answer below, then type: mark <your answer>'. "
        "Do not give the answer.", 500) or "I couldn't reach the AI for a question. Check your internet and try again."


def uneb_mark(question, answer):
    return ask_gemini(
        "You are a strict but kind UNEB examiner. Mark the student's answer to this question using a UNEB-style "
        "marking guide.\n\nQuestion:\n" + question + "\n\nStudent's answer:\n" + answer +
        "\n\nReply with:\n**Score:** x / total\n**What you got right:** bullets\n**What was missing:** bullets\n"
        "**Model answer:** the full marking-guide answer\n**Tip for the exam:** one line", 900) \
        or "I couldn't mark it right now. Check your internet and type mark again."


# ---------------- homework from a photo ----------------
HOMEWORK_PROMPT = ("This photo shows a student's homework or exam question. Read every question in it carefully. "
                   "For each question: restate it, then solve it step by step like a patient Ugandan teacher, showing "
                   "the working, and give the final answer in **bold**. Explain the method so the student can do the "
                   "next one alone. If part of the photo is blurry, say which part. ")


# ---------------- money: mobile money charges and a simple budget ----------------
def momo_fees(arg):
    a = arg or "mtn send 50000"
    return ask_gemini(
        "Search for the CURRENT official mobile money charges in Uganda (MTN MoMo and Airtel Money tariff, including the "
        "0.5% withdrawal tax where it applies) and answer this: " + a + ". Give the amount in UGX, show the fee for "
        "sending to the same network, another network/unregistered, and withdrawing at an agent. Say which date the tariff "
        "is from, and that the person can confirm on *165# (MTN) or *185# (Airtel). Keep it short with bullets.",
        700, search=True) or ("I couldn't get today's charges. Dial *165# (MTN) or *185# (Airtel) to see them.")


def budget_plan(arg):
    n = parse_amount(arg or "")
    if not n:
        return ("Tell me how much money you have, e.g. budget 200000, or budget 50k weekly.\n"
                "I'll split it into needs, wants and savings.")
    per = "week" if "week" in (arg or "").lower() else ("day" if "day" in (arg or "").lower() else "month")
    needs, wants, save = int(n * 0.5), int(n * 0.3), n - int(n * 0.5) - int(n * 0.3)
    yearly = save * {"day": 365, "week": 52, "month": 12}[per]
    return (f"**Your budget for {ugx(n)} a {per}**\n"
            f"- **Needs (50%):** {ugx(needs)} - food, transport, school things, rent, data you must have\n"
            f"- **Wants (30%):** {ugx(wants)} - snacks, outings, airtime for fun\n"
            f"- **Savings (20%):** {ugx(save)} - pay this first, the day money comes in\n\n"
            f"Saving {ugx(save)} every {per} grows to about **{ugx(yearly)} in a year**.\n"
            "Tips: write down every spend (spent 2000 airtime), set a goal (goal phone 300k), "
            "and keep savings on a separate wallet or SACCO.")


# ---------------- scam checker ----------------
_SCAM_SIGNS = (
    (r"\b(won|winner|prize|lottery|promotion|selected|congratulations)\b", "says you won a prize you never entered"),
    (r"\b(pin|password|otp|secret code|verification code)\b", "asks for a PIN, password or code (real companies never do)"),
    (r"\b(send|deposit|pay)\b.{0,30}\b(first|fee|charge|registration|processing|to receive|to claim)\b", "asks you to pay first to receive money"),
    (r"\b(urgent|immediately|within \d+ ?(min|hour)|act now|today only|blocked|suspended)\b", "rushes or scares you"),
    (r"\b(wrong(ly)? sent|sent by mistake|mistakenly|reverse|refund me)\b", "classic 'money sent by mistake, send it back' trick"),
    (r"https?://|bit\.ly|tinyurl|wa\.me", "contains a link (check it before tapping)"),
    (r"\b(double|guaranteed|100% profit|invest .{0,15} get|returns? daily)\b", "promises easy or guaranteed money"),
    (r"\b(job|visa|scholarship)\b.{0,40}\b(fee|pay|deposit)\b", "a job, visa or scholarship that wants a fee"),
    (r"\b(customer care|mtn staff|airtel staff|agent number|bank official)\b", "pretends to be company staff"),
)


def scam_check(text):
    t = (text or "").lower()
    signs = [why for pat, why in _SCAM_SIGNS if re.search(pat, t)]
    local = ("**Red flags I see:**\n" + "\n".join(f"- {s}" for s in signs)) if signs else "I see no obvious red flags in the words."
    verdict = "DANGER: very likely a scam" if len(signs) >= 2 else ("CAREFUL: possible scam" if signs else "Looks okay, but stay careful")
    ai = None
    if connected_ais():
        ai = ask_gemini("A person in Uganda received this message. Is it a scam? Give a one-line verdict (SCAM / "
                        "SUSPICIOUS / LOOKS SAFE), the reasons in 2-4 bullets, and exactly what to do next. Message:\n"
                        + text[:1500], 400)
    return (f"**{verdict}**\n{local}\n\n" + (ai + "\n\n" if ai else "") +
            "Never share your PIN. Check money really arrived with *165# or *185#, not by SMS. "
            "Report scams to your network (MTN 100, Airtel 100) and Police 999.")


# ---------------- farming help (Uganda) ----------------
def farm_help(arg):
    a = (arg or "").strip() or "what to plant this season"
    place = ""
    m = re.search(r"\b(?:in|at)\s+([A-Za-z][A-Za-z ]{2,30})$", a)
    if m:
        place = m.group(1).strip()
    try:
        wx = weather_report(place or "Kampala")
    except Exception:
        wx = ""
    r = ask_gemini(
        "You are an agricultural extension officer in Uganda (NARO/MAAIF advice). The farmer asks: " + a +
        ". Today's weather: " + (wx or "unknown") + ". Give practical, low-cost advice for a small farm: what to do now "
        "this season, spacing/seed/fertiliser or manure, pests and diseases to watch (with cheap control), harvest and "
        "storage, and where to sell. Use **bold** labels and short bullets. Mention a local agro-dealer or extension "
        "officer for chemicals.", 900, search=True)
    return r or "I couldn't reach the AI right now. Check your internet and try again."


V110_HELP = """[b]New in Genius 110[/b]
- [b]news[/b] - trending on social media, world, Uganda, Africa, sports, business, tech news (tap a headline). news brief = short summary
- [b]uneb s4 biology[/b] - UNEB-style question, then [b]mark <your answer>[/b] for a score and model answer
- [b]homework[/b] - add a photo with + then type homework: step-by-step solutions
- [b]luganda on / luganda off[/b] - Genius answers in Luganda
- [b]translate thank you[/b] - English to Luganda (or Luganda to English)
- [b]define osmosis[/b] - dictionary, works offline
- [b]fee mtn send 50000[/b] - today's mobile money charges
- [b]budget 200000[/b] - needs, wants and savings plan
- [b]scam <message>[/b] - check a suspicious SMS or WhatsApp message
- [b]farm maize in Mityana[/b] - farming advice with the weather
- [b]remember I am in S4[/b] / [b]memory[/b] / [b]forget ...[/b] - what Genius knows about you
- [b]datasaver on[/b] - shorter answers to save data
- [b]proverb[/b] - a Luganda proverb
- Offline: Genius answers questions you asked before, the dictionary, calc and notes"""


def v110_prompt_prefix(text):
    """Extra instructions for the AI: Luganda mode, data saver and what Genius remembers."""
    pre = ""
    s = v110_settings()
    if s.get("luganda"):
        pre += LUGANDA_REPLY
    if s.get("datasaver"):
        pre += "[Data saver: answer in under 120 words.] "
    try:
        m = mem_prompt()
        if m:
            pre += m + " "
    except Exception:
        pass
    return pre


# ---------------- 110.8 privacy shield ----------------
def set_private_screen(on):
    """Private screen: other apps, screen recorders and on-screen AI readers can't capture Genius."""
    try:
        from jnius import autoclass
        from android.runnable import run_on_ui_thread
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        WM = autoclass("android.view.WindowManager$LayoutParams")

        @run_on_ui_thread
        def apply():
            if on:
                act.getWindow().addFlags(WM.FLAG_SECURE)
            else:
                act.getWindow().clearFlags(WM.FLAG_SECURE)
        apply()
        return True
    except Exception as e:
        log(f"PRIVATE screen: {type(e).__name__}")
        return False


def lock_private_files():
    """Genius's memory, notes, keys and chats are readable by Genius alone (owner-only file rights)."""
    n = 0
    for base in (ROOT,):
        for dp_, dirs, files in os.walk(base):
            if "/.kivy" in dp_ or "__pycache__" in dp_:
                continue
            for f in files:
                if f.endswith((".json", ".txt", ".dat", ".db")):
                    try:
                        os.chmod(os.path.join(dp_, f), 0o600)
                        n += 1
                    except Exception:
                        pass
    return n


PRIVACY_TEXT = ("[b]Genius privacy shield[/b]\n"
                "- Your chats, memory, notes and keys live inside Genius's own locked space on this phone. "
                "Other apps can't open them, and Genius never sends them to other devices.\n"
                "- Sharing Genius sends only the download link, never your chats or what Genius knows about you.\n"
                "- [b]private on[/b] blocks screenshots, screen recording and on-screen AI from seeing Genius. "
                "[b]private off[/b] allows them again.\n"
                "- Genius still learns from the internet and other AIs. It sends them only your question, "
                "never your saved memory files.")


SAVE_PHRASES = ("save it", "save picture", "save photo", "save to gallery", "save to files", "save to file",
                "save this", "save image")


def v110_handle(screen, line, action, arg, low):
    """Genius 110 commands. Returns True when handled."""
    lw = low.strip(" .!?")
    try:
        if minerals_handle(screen, line, action, arg, low):
            return True
    except Exception as e:
        log(f"MINERALS: command failed {type(e).__name__}: {e}")
    try:
        if metal_handle(screen, line, action, arg, low):
            return True
    except Exception as e:
        log(f"METAL: command failed {type(e).__name__}: {e}")
    if lw in ("save", "save it", "save picture", "save photo", "save to gallery", "download", "download it",
              "download picture", "save to files", "save to file", "download to files", "share picture", "share photo"):
        src = LAST_IMAGE.get("path")
        if not src or not os.path.exists(src):
            screen.say("Make or add a picture first, then say " + ("share." if lw.startswith("share") else "save."))
            return True
        if lw.startswith("share"):
            if not share_media(src):
                screen.say("Sharing didn't open. Say save, then share it from your gallery.")
            return True
        _u, msg = save_media(src, "files" if "file" in lw else "gallery")
        screen.say(msg)
        return True
    if action in ("private", "privacy") or lw in ("privacy shield", "private screen"):
        a = arg.lower().strip()
        if a in ("on", "yes", "1"):
            d = life_load(); d["private_screen"] = True; life_save(d)
            ok = set_private_screen(True)
            screen.say("Private screen is on. Other apps, screen recorders and AI can't capture Genius now. "
                       "Screenshots of Genius are blocked too. Say private off to allow them." if ok else
                       "Private screen works on the phone app only.")
        elif a in ("off", "no", "0"):
            d = life_load(); d["private_screen"] = False; life_save(d)
            set_private_screen(False)
            screen.say("Private screen is off. You can take screenshots of Genius again.")
        else:
            n = lock_private_files()
            log(f"PRIVACY: locked {n} files")
            screen.say(PRIVACY_TEXT, plain=False)
        return True
    if action == "news" or lw in ("world news", "headlines", "amawulire", "show news", "latest news"):
        if arg.lower().startswith(("brief", "summary", "summarise", "summarize")):
            topic = arg.split(None, 1)[1] if len(arg.split()) > 1 else "world"
            screen._bg(lambda: news_brief(topic), "Reading today's headlines...", speak=False)
            return True
        if not arg:
            screen.news_menu()
            return True
        screen.show_news(arg)
        return True
    if action in ("aicheck", "ai check", "check ai", "connections", "ai status"):
        screen._bg(ai_health_report, "Testing every AI connection...", speak=False)
        return True
    if action in ("uneb", "past paper", "paper"):
        def job():
            q = uneb_question(arg)
            screen._uneb_q = q
            return q
        screen._bg(job, "Setting a UNEB-style question...", speak=False)
        return True
    if action == "mark":
        q = getattr(screen, "_uneb_q", None)
        if not q:
            screen.say("Get a question first, e.g. uneb s4 chemistry. Then type mark and your answer.")
            return True
        if not arg:
            screen.say("Type mark, then your answer.")
            return True
        screen._bg(lambda: uneb_mark(q, arg), "Marking your answer like UNEB...", speak=False)
        return True
    if action in ("homework", "solve photo", "hw") or lw in ("solve this homework", "do my homework", "solve this photo"):
        att = getattr(screen, "attached", None)
        if not att or att.get("kind") != "image":
            screen.say("Tap + and add a clear photo of your homework, then type homework.")
            return True
        screen.file_question(HOMEWORK_PROMPT + (("Student note: " + arg) if arg else ""))
        return True
    if action == "luganda" and arg.lower() in ("on", "off", "mode", ""):
        on = arg.lower() != "off"
        v110_set("luganda", on)
        screen.say("Luganda mode on. Nja kuddamu mu Luganda. (Type luganda off to stop.)" if on
                   else "Luganda mode off. I'll answer in English.")
        return True
    if action in ("translate", "vvuunula", "vunula"):
        if not arg:
            screen.say("Say it like: translate thank you very much, or translate webale nnyo to english")
            return True
        text, to = parse_translate(arg)
        got, exact = translate_offline(text, to)
        if got and exact:
            screen.say(f"{text} = **{got}**")
            return True
        lang = "Luganda" if to == "lg" else "English"
        screen._bg(lambda: ask_gemini(f"Translate into natural, correct {lang}. Reply with only the translation, then "
                                      f"one short line on pronunciation or usage.\n\n{text}", 300)
                   or (f"{text} = {got} (rough, offline)" if got else "I couldn't translate that right now."),
                   "Translating...", speak=False)
        return True
    if action in ("define", "meaning", "dictionary"):
        d = dictionary_lookup("define " + arg) if arg else None
        if d:
            screen.say(d)
        elif not arg:
            screen.say("Say it like: define photosynthesis")
        else:
            screen._bg(lambda: ask_gemini(f"Define '{arg}' simply for a Ugandan secondary student: meaning, one example "
                                          "sentence, and the subject it belongs to.", 250) or
                       f"I don't have '{arg}' offline and couldn't reach the AI.", "Looking it up...", speak=False)
        return True
    if action in ("fee", "fees", "charges") and ("mtn" in low or "airtel" in low or "momo" in low or parse_amount(arg)):
        screen._bg(lambda: momo_fees(arg), "Checking today's mobile money charges...", speak=False)
        return True
    if action == "budget":
        screen.say(budget_plan(arg))
        return True
    if action in ("scam", "fraud", "isthisscam"):
        if not arg:
            screen.say("Paste the message after the word scam, e.g. scam Congratulations you have won 5M, send 20k to claim")
            return True
        screen._bg(lambda: scam_check(arg), "Checking that message for scam signs...", speak=False)
        return True
    if action in ("farm", "farming", "crop", "pest", "ennimiro"):
        screen._bg(lambda: farm_help((action + " " + arg) if action == "pest" else arg),
                   "Asking the farming expert...", speak=False)
        return True
    if action == "remember" and arg:
        screen.say(mem_remember(arg))
        return True
    if lw in ("remember", "forget"):
        screen.say("Say it like: " + ("remember I am in S4" if lw == "remember" else "forget my class")
                   + ". Type memory to see what I remember.")
        return True
    if lw in ("fee", "fees", "charges"):
        screen.say("Say it like: fee mtn send 50000, or fee airtel withdraw 20000")
        return True
    if lw in ("memory", "what do you remember", "what do you know about me", "my memory"):
        screen.say(mem_report())
        return True
    if action == "forget" and arg and arg.lower() not in ("lessons", "file", "picture", "this file"):
        screen.say(mem_forget(arg))
        return True
    if action == "datasaver" or lw in ("data saver on", "data saver off", "data saver"):
        on = "off" not in low
        v110_set("datasaver", on)
        screen.say("Data saver on: shorter answers to save your data." if on else "Data saver off.")
        return True
    if action in ("proverb", "olugero", "engero"):
        lgp, en = proverb_of_day(random.randint(0, 400))
        screen.say(f"**{lgp}**\n{en}")
        return True
    if lw in ("new", "new features", "genius 110", "what's new in 110", "v110"):
        screen.show("AI", V110_HELP)
        return True
    return False


class NewsCard(ButtonBehavior, BoxLayout):
    """One news video or story: big picture on top, headline under it. Tap to play inside Genius."""

    def __init__(self, item, **kw):
        big = item.get("video") or item.get("img")
        super().__init__(orientation="vertical", size_hint_y=None, padding=[dp(8), dp(8)], spacing=dp(6),
                         height=dp(300) if big else dp(110), **kw)
        self.item = item
        with self.canvas.before:
            Color(1, 1, 1, 0.07)
            self._bg = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self._paint, size=self._paint)
        self.pic = None
        if big:
            self.pic = KivyImage(allow_stretch=True, keep_ratio=True, size_hint_y=None, height=dp(190),
                                 color=(1, 1, 1, 0.15))
            self.add_widget(self.pic)
        badge = "[b][color=ff4d5e]VIDEO[/color][/b]  " if item.get("video") else ""
        meta = " · ".join(x for x in (item.get("src"), item.get("when")) if x)
        lb = Label(text=f"[b]{_esc(item['title'] if len(item['title']) <= 110 else item['title'][:107] + '...')}[/b]\n[size=13sp]{badge}[color=9aa0c0]{_esc(meta)}[/color][/size]",
                   markup=True, font_size="16sp", color=TEXTCOL, halign="left", valign="top")
        lb.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, w.height)))
        self.add_widget(lb)

    def _paint(self, *_):
        self._bg.pos, self._bg.size = self.pos, self.size

    def set_pic(self, path):
        if self.pic is not None and path:
            self.pic.source = path
            self.pic.color = (1, 1, 1, 1)


class ChatScreen(BoxLayout):
    attached = None
    busy = False                 # one slow job at a time (set before any worker starts)
    _to_storage = False

    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=0, spacing=0, **kw)
        self.app = app
        self.deep = False
        add_gradient_bg(self)

        # header bar: profile on the left
        header = Panel(bg=HEADER, radius=0, orientation="horizontal",
                       size_hint_y=None, height="60dp", padding=[18, 0, 12, 0], spacing=10)
        self.profile_chip = ProfileChip()          # not shown; Profile is inside the menu
        self.profile_chip.bind(on_press=self.profile_drawer)
        title = Label(text="[b][color=ffc84d]Gen[/color][color=c79bff]ius[/color][/b]  [size=12sp][size=18sp][color=5ee6a0]\u2022[/color][/size] [color=9aa0c0]online[/color][/size]",
                      markup=True, font_size="25sp", halign="left", valign="middle")
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        title.shorten = True
        title.shorten_from = "right"
        header.add_widget(title)
        self.mode_lbl = Label(text="Fast", font_size="15sp", color=HINT,
                              halign="right", size_hint_x=None, width="60dp")
        # Share sits right on the top bar (in place of the Fast/Deep word) so anyone can spread Genius in one tap
        sb = BoxLayout(size_hint_x=None, width="64dp", padding=[0, 9, 0, 9])
        share_btn = RoundButton(text="Share", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), font_size="13sp", bold=True)
        share_btn.bind(on_press=self.share_menu)
        sb.add_widget(share_btn)
        header.add_widget(sb)
        hb = BoxLayout(size_hint_x=None, width="70dp", padding=[0, 9, 0, 9])
        find_btn = RoundButton(text="Search", bg=BLUE, fg=TEXTCOL, font_size="13sp", bold=True)
        find_btn.bind(on_press=self.search_box)
        hb.add_widget(find_btn)
        header.add_widget(hb)
        # only two buttons on top: Share and Search. Every tool is found from Search.
        self.speak_btn = find_btn      # shows "Stop" while Genius hears you; tap to stop
        self.add_widget(header)
        self.header = header

        # chat area
        body = Panel(orientation="vertical", padding=[10, 8, 10, 8], spacing=8,
                     bg=(1, 1, 1, 0.045), radius=26)
        outer = BoxLayout(padding=[10, 10, 10, 8])
        self.scroll = ScrollView(bar_color=(1.0, 0.78, 0.30, 0.7), bar_width="3dp")
        self.out = Label(text="", markup=True, font_size="18sp", size_hint_y=None,
                         halign="left", valign="top", color=TEXTCOL, padding=(8, 8))
        self.out.bind(width=lambda *a: setattr(self.out, "text_size", (self.out.width, None)),
                      texture_size=self._chat_size)
        self.out.bind(on_ref_press=self._on_chat_ref)
        self.scroll.add_widget(self.out)
        body.add_widget(self.scroll)
        outer.add_widget(body)
        self.add_widget(outer)
        self.chat_outer = outer

        # every tool now lives in one place: the Tools button by the typing box
        self.deep_btn = RoundButton(text="Deep", bg=GREY, fg=TEXTCOL)   # not shown; keeps Deep's state

        # suggestion strip: matching commands appear above the box while you type; tap one to fill it in
        self.sugg_sv = ScrollView(size_hint_y=None, height=0, opacity=0, do_scroll_y=False, bar_width=0)
        self.sugg_row = BoxLayout(orientation="horizontal", size_hint_x=None, spacing=6, padding=[10, 2, 10, 2])
        self.sugg_row.bind(minimum_width=self.sugg_row.setter("width"))
        self.sugg_sv.add_widget(self.sugg_row)
        self.add_widget(self.sugg_sv)
        self._sugg_ev = None

        # input row: wraps and grows to 4 lines, stays above the keyboard
        self.in_row = row = BoxLayout(size_hint_y=None, height="62dp", spacing=8, padding=[10, 4, 10, 10])
        self.inp = style_input(ChatInput(hint_text="Ask Genius anything...",
                               multiline=True, do_wrap=True, font_size="15sp", size_hint_y=None,
                               write_tab=False, text_validate_unfocus=False))
        self.inp.bind(on_text_validate=self.send, text=self._typing, minimum_height=self._grow_input,
                      width=self._grow_input)
        send_col = BoxLayout(orientation="vertical", size_hint_x=None, width="84dp")
        send_col.add_widget(Widget())
        send = RoundButton(text="Send", bg=GOLD, fg=(0.1, 0.1, 0.1, 1),
                           size_hint_y=None, height="48dp", font_size="18sp", bold=True)
        send.bind(on_press=self.send)
        send_col.add_widget(send)
        plus_col = BoxLayout(orientation="vertical", size_hint_x=None, width="48dp")
        plus_col.add_widget(Widget())
        plus = RoundButton(text="+", bg=BLUE, fg=TEXTCOL, size_hint_y=None, height="48dp",
                           font_size="28sp", bold=True)
        plus.bind(on_press=self.attach_menu)
        plus_col.add_widget(plus)
        row.add_widget(plus_col)
        row.add_widget(self.inp)
        row.add_widget(send_col)
        self.add_widget(row)
        # empty space the size of the keyboard: the box sits right on top of it, the screen doesn't slide
        self.kb_pad = Widget(size_hint_y=None, height=0)
        self.add_widget(self.kb_pad)
        self.inp.bind(focus=self._kb_focus)
        self._kb_ev = None
        Clock.schedule_once(self._grow_input, 0)
        threading.Thread(target=groq_warmup, daemon=True).start()
        threading.Thread(target=newest_apk_link, daemon=True).start()
        threading.Thread(target=lock_private_files, daemon=True).start()
        if life_load().get("private_screen"):
            set_private_screen(True)

        self.say(f"Welcome {CURRENT['name']}. You are in command. Tap Search to find any tool, or + to add a photo, screenshot or file.")

    # ---------- listening: hear you, answer, speak back ----------
    SPEECH_CODE = 7777

    def speak_input(self, *_):
        """Tap Speak: start a hands-free conversation. Tap again (or say stop) to end it."""
        if getattr(self, "talking", False):
            native_stop()
            self.end_talk("Okay, I've stopped listening.")
            return
        self.talking = True
        self.misses = 0
        self.speak_btn.text = "Stop"
        self.speak_btn.set_bg(RED)
        self.speak_btn.color = TEXTCOL
        self.listen_now()

    def end_talk(self, msg=None):
        self.talking = False
        self.speak_btn.text = "Search"
        self.speak_btn.set_bg(BLUE)
        self.speak_btn.color = TEXTCOL
        if msg:
            self.say(msg)

    def listen_now(self, *_):
        if not getattr(self, "talking", False):
            return
        self.mic_errors = []

        def attempt(name, fn):
            try:
                return fn()
            except BaseException as e:
                self.mic_errors.append(f"{name}: {e}")
                log(f"MIC {name} failed: {e}")
                return None
        perm = safe(mic_permission_ok)
        if perm is False:
            # Pydroid has no mic permission (or Android won't show the box).
            # Google's voice box uses the Google app's own microphone, so use it instead.
            self.native_broken = True
            if attempt("google popup", self._listen_google):
                self.show("AI", "Speak into Google's voice box.")
                return
            self.end_talk()
            self.say("Android won't let me use the microphone. I'm opening Pydroid's settings: "
                     "tap Permissions, then Microphone, then Allow.")
            safe(open_app_settings)
            return
        self.show("AI", "Listening... speak now.")
        if not getattr(self, "native_broken", False) and attempt(
                "android", lambda: native_listen(self._heard, self._mic_error)):
            MIC_STATE["token"] += 1
            tok = MIC_STATE["token"]
            Clock.schedule_once(lambda dt: self._mic_watchdog(tok), 15)
            return
        if attempt("google popup", self._listen_google):
            return
        if attempt("plyer", self._listen_plyer):
            return
        self.end_talk()
        self.inp.focus = True
        self.say("Voice listening didn't start. Tap the mic on your keyboard and speak for now. "
                 "Type 'mic test' and send me what it shows.")

    def _mic_watchdog(self, tok):
        """If Android never answered, stop waiting and use another way."""
        if tok != MIC_STATE["token"] or not getattr(self, "talking", False):
            return
        if MIC_STATE["last"].startswith(("heard", "error")):
            return
        log(f"MIC watchdog: {MIC_STATE['last']}")
        native_stop()
        self.native_broken = True              # use the Google popup from now on
        self.say("The microphone didn't respond, so I'm switching to Google's voice box.")
        Clock.schedule_once(self.listen_now, 1)

    def mic_test(self):
        """Report every step so we can see exactly why it can't hear."""
        lines = []
        try:
            from jnius import autoclass
            lines.append("pyjnius: yes")
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            lines.append("activity: yes")
            ok = act.checkSelfPermission("android.permission.RECORD_AUDIO") == 0
            lines.append("microphone permission: " + ("allowed" if ok else "NOT allowed"))
            SR = autoclass("android.speech.SpeechRecognizer")
            lines.append("speech service: " + ("yes" if SR.isRecognitionAvailable(act) else "NOT found"))
        except BaseException as e:
            lines.append(f"stopped at: {e}")
        lines.append("android module: " + ("yes" if safe(lambda: __import__("android")) else "no"))
        lines.append("plyer: " + ("yes" if safe(lambda: __import__("plyer")) else "no"))
        lines.append("last listen: " + MIC_STATE["last"])
        if getattr(self, "mic_errors", None):
            lines.append("errors: " + " | ".join(self.mic_errors))
        self.show("AI", "Mic test\n" + "\n".join(lines))

    def _listen_google(self):
        from jnius import autoclass
        from android import activity
        Intent = autoclass("android.content.Intent")
        RI = autoclass("android.speech.RecognizerIntent")
        PA = autoclass("org.kivy.android.PythonActivity")
        if not getattr(self, "_bound", False):
            activity.bind(on_activity_result=self._on_speech_result)
            self._bound = True
        i = Intent(RI.ACTION_RECOGNIZE_SPEECH)
        i.putExtra(RI.EXTRA_LANGUAGE_MODEL, RI.LANGUAGE_MODEL_FREE_FORM)
        i.putExtra(RI.EXTRA_LANGUAGE, "en-UG")
        i.putExtra(RI.EXTRA_PROMPT, "Talk to Genius")
        PA.mActivity.startActivityForResult(i, self.SPEECH_CODE)
        return True

    def _on_speech_result(self, request, result, intent):
        if request != self.SPEECH_CODE:
            return
        words = ""
        try:
            if result == -1 and intent is not None:      # -1 = RESULT_OK
                RI = __import__("jnius").autoclass("android.speech.RecognizerIntent")
                lst = intent.getStringArrayListExtra(RI.EXTRA_RESULTS)
                if lst is not None and lst.size() > 0:
                    words = lst.get(0)
        except Exception:
            words = ""
        Clock.schedule_once(lambda *_: self._heard(words, cancelled=(result != -1)), 0)

    def _listen_plyer(self):
        from plyer import stt
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])
        except Exception:
            pass
        stt.start()
        self.show("AI", "Listening... speak now.")

        def check(dt):
            try:
                if getattr(stt, "listening", False):
                    return True
                stt.stop()
                words = " ".join(stt.results) if stt.results else ""
            except Exception:
                words = ""
            self._heard(words)
            return False
        Clock.schedule_interval(check, 0.6)
        return True

    def _mic_error(self, msg, code):
        log(f"MIC ERROR {code}")
        if code == -1:                         # Android listener couldn't start
            self.native_broken = True
            self.mic_errors = getattr(self, "mic_errors", []) + [msg]
            self.listen_now()
            return
        if code in (6, 7):                     # silence / unclear: count as a miss
            self._heard("")
            return
        self.end_talk(msg)

    def _heard(self, words, cancelled=False):
        words = (words or "").strip()
        if cancelled and not words:
            self.end_talk()                 # you closed the mic popup
            return
        if not words:
            self.misses += 1
            if self.misses >= 2:
                self.end_talk("I didn't hear anything, so I stopped listening.")
            else:
                self.say("I didn't catch that. Say it again.")
            return
        self.misses = 0
        if words.lower().strip(" .!") in ("stop", "stop listening", "bye", "goodbye",
                                           "that's all", "enough", "thank you bye"):
            self.end_talk("Okay. Tap Speak whenever you want to talk again.")
            return
        self.handle(words)

    # ---------- wake word: say "Hey Genius" without tapping ----------
    WAKE_WORDS = ("hey genius", "hi genius", "ok genius", "hey genious", "hey jeanius", "genius")

    def toggle_wake(self):
        self.waking = not getattr(self, "waking", False)
        if self.waking:
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([Permission.RECORD_AUDIO])
            except Exception:
                pass
            self.say("Hands-free on. Say Hey Genius, then your question. Keep the app open.")
            Clock.schedule_once(self._wake_listen, 4)
        else:
            self.say("Hands-free off.")

    def _wake_listen(self, *_):
        if not getattr(self, "waking", False):
            return
        if getattr(self, "busy", False) or getattr(self, "talking", False):
            Clock.schedule_once(self._wake_listen, 2)
            return
        eng = _android_tts.get("engine")
        if eng is not None and safe(lambda: bool(eng.isSpeaking())):
            Clock.schedule_once(self._wake_listen, 1)    # don't hear myself
            return

        def got(words):
            words = (words or "").lower()
            for w in self.WAKE_WORDS:
                if w in words:
                    rest = words.split(w, 1)[1].strip(" ,.!?")
                    if rest:
                        self.handle(rest)
                    else:
                        tts("Yes?")
                        self.talking = True
                        self.misses = 0
                        Clock.schedule_once(self.listen_now, 1.2)
                    break
            Clock.schedule_once(self._wake_listen, 1)

        def bad(msg, code):
            if code == 9:
                self.waking = False
                self.say(msg)
                return
            Clock.schedule_once(self._wake_listen, 1)
        if safe(lambda: native_listen(got, bad)):
            return

        def start():
            from plyer import stt
            stt.start()
            return stt
        engine = safe(start)
        if engine is None:
            self.waking = False
            self.say("Hands-free needs Google speech, which isn't available here. Use Speak instead.")
            return

        def check(dt):
            try:
                if getattr(engine, "listening", False):
                    return True
                engine.stop()
                words = " ".join(engine.results or []).lower().strip()
            except Exception:
                words = ""
            for w in self.WAKE_WORDS:
                if w in words:
                    rest = words.split(w, 1)[1].strip(" ,.!?")
                    if rest:
                        self.handle(rest)
                    else:
                        tts("Yes?")
                        self.talking = True
                        self.misses = 0
                        Clock.schedule_once(self.listen_now, 1.2)
                    break
            Clock.schedule_once(self._wake_listen, 1)    # keep listening
            return False
        Clock.schedule_interval(check, 0.5)

    def listen_after_speech(self):
        """Wait until Genius finishes talking, then listen again."""
        if not getattr(self, "talking", False) or getattr(self, "busy", False):
            return
        if getattr(self, "_wait_ev", None):
            self._wait_ev.cancel()
        start = time.time()

        def poll(dt):
            if not getattr(self, "talking", False) or getattr(self, "busy", False):
                return False
            eng = _android_tts.get("engine")
            speaking = safe(lambda: bool(eng.isSpeaking())) if eng is not None else None
            if speaking is None:                     # can't tell: guess from length
                if time.time() - start < 1.0 + len(self._last_said) * 0.065:
                    return True
            elif speaking or time.time() - start < 1.0:
                return True
            self._wait_ev = None
            self.listen_now()
            return False
        self._wait_ev = Clock.schedule_interval(poll, 0.4)

    def toggle_deep(self, *_):
        self.deep = not self.deep
        self.deep_btn.set_bg(GOLD if self.deep else GREY)
        self.deep_btn.color = (0.1, 0.1, 0.1, 1) if self.deep else TEXTCOL
        self.mode_lbl.text = "Deep" if self.deep else "Fast"
        self.mode_lbl.color = GOLD if self.deep else HINT
        self.say("Deep thinking on. I'll think harder and search the web, so answers take longer."
                 if self.deep else "Fast mode on. Short, quick answers.")

    def clear_chat(self, *_):
        history.clear()
        save_memory()
        self.out.text = ""
        log("CHAT CLEARED")
        self.say("Chat cleared. Fresh start.")

    # ---------- Genius Wealth bot ----------
    def _bg_simple(self, fn):
        self.show("AI", "[i]Working on it...[/i]")

        def d():
            try:
                out = fn()
            except Exception as e:
                out = f"That didn't work: {e}"
            Clock.schedule_once(lambda *_: self.say(out), 0)
        threading.Thread(target=d, daemon=True).start()

    def _wealth_profile(self):
        f = "wealth_" + re.sub(r"\W+", "_", str(CURRENT.get("name") or "me")) + ".txt"
        try:
            return open(f, encoding="utf8").read()[:600]
        except Exception:
            return ""

    def wealth_menu(self, *_):
        def bot_on():
            self.bot_mode = "wealth"
            self.mode_lbl.text = "Wealth"
            self.say("Genius Wealth is on. Ask me anything about money, saving, investing or trading. "
                     "Say 'exit bot' to go back.")

        def plan():
            self.bot_mode = "wealth"
            self.mode_lbl.text = "Wealth"
            self._bg(lambda: wealth_answer(
                "Build me a step-by-step plan to grow wealth by trading: how much to start with, demo practice, a simple "
                "strategy, risk 1-2% per trade with position size math, a journal, and a 12-month growth example in UGX "
                "with realistic (not hype) returns.",
                self._wealth_profile()))

        def about_me():
            box = BoxLayout(orientation="vertical", spacing=10, padding=12)
            ti = TextInput(hint_text="e.g. I earn 300,000 UGX a month, spend 200,000, have 50,000 saved, goal: buy land",
                           text=self._wealth_profile(), multiline=True)
            box.add_widget(ti)
            pop = Popup(title="About my money", content=box, size_hint=(0.94, 0.6),
                        separator_color=GOLD, title_color=GOLD)

            def save(*_):
                f = "wealth_" + re.sub(r"\W+", "_", str(CURRENT.get("name") or "me")) + ".txt"
                try:
                    open(f, "w", encoding="utf8").write(ti.text.strip())
                    self.say("Saved privately. Your wealth plans now fit your real numbers.")
                except Exception as e:
                    self.say(f"Couldn't save: {e}")
                pop.dismiss()
            b = RoundButton(text="Save", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None, height="52dp", bold=True)
            b.bind(on_press=save)
            box.add_widget(b)
            pop.open()

        self._buttons_popup("Genius Wealth", [
            ("Protect my money: check before I trade", lambda: self._bg(lambda: wealth_answer(
                "Give me a short money-protection checklist to go through before every trade, the top reasons people "
                "in Uganda lose money trading, and how to stop losses early.", self._wealth_profile())), RED),
            ("Talk to Genius Wealth bot (free for everyone)", bot_on, GOLD),
            ("Read a trading chart (picture)", self.chart_pick, GOLD),
            ("Check my trade screenshot (profit/loss advice)", self.chart_pick, GOLD),
            ("Make my trading plan", plan, BLUE),
            ("About my money (private)", about_me, BLUE),
            ("Live prices: Bitcoin", lambda: self._bg(lambda: market_quote("btc")), GREY),
            ("Live dollar rate (USD to UGX)", lambda: self._bg(lambda: market_quote("usd ugx")), GREY),
            ("Saving & investing in Uganda", lambda: self._bg(lambda: wealth_answer(
                "Explain the safest ways to save and invest in Uganda, from small amounts: SACCOs, money market and "
                "unit trust funds, treasury bills and bonds, and the stock exchange. Risks and how to start.")), GREY),
            ("Spot money scams", lambda: self._bg(lambda: wealth_answer(
                "How do I spot investment, crypto and forex scams in Uganda? Give clear warning signs.")), GREY)],
            hint="Free for everyone: real prices, chart reading and a wealth guide")

    def chart_pick(self, *_):
        self._chart_mode = True
        self.say("Pick a screenshot of a chart or your trade. I'll read the profit or loss, the risk and what to do next.")
        self.pick_file("image/*")

    def chart_read(self, path):
        def go():
            ans = ask_about_file(path, "image", CHART_PROMPT)
            return "Chart reading\n" + ans
        self._bg(go)

    # ---------- profile drawer: slides in from the left ----------
    def profile_drawer(self, *_):
        name = str(CURRENT.get("name") or "")
        acc = accounts_load().get(name, {}) if not CURRENT["owner"] else {}
        email = acc.get("email", "") if acc else ""
        try:
            _ok, plan = premium_status()
        except Exception:
            plan = ""
        box = BoxLayout(orientation="vertical", spacing=10, padding=[14, 14, 14, 14])
        pop = Popup(title="", separator_height=0, content=box, size_hint=(0.82, 1),
                    pos_hint={"x": 0, "top": 1}, background_color=(0.07, 0.05, 0.16, 0.97))
        top = BoxLayout(size_hint_y=None, height="96dp", spacing=12)
        big = ProfileChip(size=("84dp", "84dp"), font_size="34sp")
        top.add_widget(big)
        info = Label(text=f"[b]{name or 'Guest'}[/b]\n[size=13sp]{'Owner' if CURRENT['owner'] else (email or 'Member')}[/size]",
                     markup=True, color=TEXTCOL, font_size="20sp", halign="left", valign="middle")
        info.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        top.add_widget(info)
        box.add_widget(top)
        if plan:
            pl = Label(text=plan, color=GOLD, font_size="14sp", size_hint_y=None, height="44dp", halign="left", valign="middle")
            pl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
            box.add_widget(pl)

        def set_photo():
            pop.dismiss()
            self.change_profile_photo()

        opts = [("Home", self.app.open_home, GOLD),
                ("Genius Wealth (trading & money)", self.wealth_menu, GOLD),
                ("Change profile picture", set_photo, BLUE),
                ("Help improve Genius", self.help_improve_menu, BLUE),
                ("Set up AI key", self.key_wizard, GOLD),
                ("My plan (Premium)", self.premium_popup, BLUE),
                ("My storage", self.storage_box, BLUE),
                ("My creations", self.creations, BLUE),
                ("Genius everywhere", self.everywhere_menu, GREY),
                ("Share Genius", self.share_menu, GREY),
                ("Change secret code", lambda: self.handle("change code"), GREY),
                ("Sign out", self.app.build_login, RED)]
        sv = ScrollView()
        grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        for label, fn, col in opts:
            b = RoundButton(text=label, bg=col, fg=TEXTCOL, size_hint_y=None, height="50dp", font_size="16sp", bold=True)

            def go(btn, fn=fn):
                pop.dismiss()
                fn()
            b.bind(on_press=go)
            grid.add_widget(b)
        sv.add_widget(grid)
        box.add_widget(sv)
        box.add_widget(Label(text="Genius · App built by Ssali", color=HINT, font_size="12sp", size_hint_y=None, height="24dp"))
        pop.open()

    # ---------- Tools: every button in one place ----------
    def tools_menu(self, *_):
        if getattr(self, "talking", False):
            return self.speak_input()          # tapping while listening stops it
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        pop = Popup(title="Tools", content=box, size_hint=(0.94, 0.94),
                    separator_color=GOLD, title_color=GOLD)
        grid = GridLayout(cols=3, size_hint_y=None, height="370dp", spacing=8)
        quick = [("Share Genius", self.share_menu, GOLD), ("Speak", self.speak_input, GOLD),
                 ("Draw", lambda: self.handle("draw"), BLUE),
                 ("Locker", lambda: self.handle("secrets"), GREY), ("Notes", lambda: self.handle("notes"), GREY),
                 ("Weather", lambda: self.handle("weather"), GREY),
                 ("Deep: " + ("on" if self.deep else "off"), self.toggle_deep, GOLD if self.deep else GREY),
                 ("News", self.news_menu, GOLD), ("UNEB", lambda: self.handle("uneb"), BLUE),
                 ("Clear", self.clear_chat, GREY), ("Add file", self.attach_menu, BLUE),
                 ("Stop", lambda: self.handle("stop"), RED)]
        def go_btn(label, fn, col, h=None):
            b = RoundButton(text=label, bg=col, fg=(0.1, 0.1, 0.1, 1) if col == GOLD else TEXTCOL,
                            font_size="15sp", bold=True, **({"size_hint_y": None, "height": h} if h else {}))
            def go(btn, fn=fn):
                pop.dismiss()
                Clock.schedule_once(lambda *_: fn(), 0.1)
            b.bind(on_press=go)
            return b
        for label, fn, col in quick:
            grid.add_widget(go_btn(label, fn, col))
        box.add_widget(grid)
        sv = ScrollView()
        lst = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        lst.bind(minimum_height=lst.setter("height"))
        more = [("Minerals near me", lambda: self.handle("minerals"), GOLD),
                ("Metal Finder", lambda: self.handle("metal"), GOLD),
                ("Profile", self.profile_drawer, BLUE),
                ("Set up AI key", self.key_wizard, GOLD),
                ("Fun studio (collage, effects, video)", self.fun_studio, GOLD),
                ("My creations (pictures)", self.creations, BLUE),
                ("My storage", self.storage_box, BLUE),
                ("New in Genius 110", lambda: self.show("AI", V110_HELP), GOLD),
                ("What's new", lambda: self.show("AI", CHANGELOG), GREY),
                ("Help (all commands)", lambda: self.handle("help"), GREY),
                ("Change secret code", lambda: self.handle("change code"), GREY),
                ("Accounts", self.accounts_box, GREY),
                ("Lock Genius", self.app.build_login, GREY),
                ("Exit Genius", self.exit_app, RED)]
        for label, fn, col in more:
            lst.add_widget(go_btn(label, fn, col, "50dp"))
        sv.add_widget(lst)
        box.add_widget(sv)
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="46dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    def options_menu(self, *_):
        return self.tools_menu()

    def _old_options_menu(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        pop = Popup(title="Options", content=box, size_hint=(0.9, 0.94),
                    separator_color=GOLD, title_color=GOLD)
        opts = [("Fun studio (collage, effects, video)", self.fun_studio, GOLD),
                ("My creations (pictures)", self.creations, BLUE),
                ("My storage", self.storage_box, BLUE),
                ("Add a picture or file", self.attach_menu, BLUE),
                ("New in Genius 110", lambda: self.show("AI", V110_HELP), GOLD),
                ("What's new", lambda: self.show("AI", CHANGELOG), GREY),
                ("Help (all commands)", lambda: self.handle("help"), GREY),
                ("Change secret code", lambda: self.handle("change code"), GREY),
                ("Accounts", self.accounts_box, GREY),
                ("Lock Genius", self.app.build_login, GREY),
                ("Exit Genius", self.exit_app, RED)]
        for label, fn, col in opts:
            b = RoundButton(text=label, bg=col, fg=TEXTCOL, size_hint_y=None, height="52dp",
                            font_size="17sp", bold=True)

            def go(btn, fn=fn):
                pop.dismiss()
                Clock.schedule_once(lambda *_: fn(), 0.1)
            b.bind(on_press=go)
            box.add_widget(b)
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="48dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    def accounts_box(self, *_):
        if not CURRENT["owner"]:
            self.say(f"You are signed in as {CURRENT['name']}. Your chats and files are private to you. "
                     "Tap Lock Genius to sign out.")
            return
        a = accounts_load()
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        pop = Popup(title="Accounts", content=box, size_hint=(0.94, 0.8),
                    separator_color=GOLD, title_color=GOLD)
        box.add_widget(Label(text=f"Owner: {OWNER}  |  {len(a)} other account(s)", color=HINT,
                             size_hint_y=None, height="30dp"))
        grid = GridLayout(cols=1, spacing=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        sv = ScrollView()
        sv.add_widget(grid)
        box.add_widget(sv)
        for n, info in sorted(a.items()):
            line = BoxLayout(size_hint_y=None, height="50dp", spacing=6)
            line.add_widget(Label(text=f"{n}  {info.get('email', '')}\nsince {info.get('created', '?')}",
                                  color=TEXTCOL, font_size="13sp", halign="center"))
            db = RoundButton(text="Delete", bg=RED, fg=TEXTCOL, size_hint_x=0.32)

            def kill(btn, n=n):
                pop.dismiss()
                Clock.schedule_once(lambda *_: self.say(
                    f"Deleted the account {n} and all its data." if delete_account(n) else "Couldn't delete it."), 0.1)
            db.bind(on_press=kill)
            line.add_widget(db)
            grid.add_widget(line)
        if not a:
            grid.add_widget(Label(text="No other accounts yet. People tap 'Create an account' on the sign-in screen.",
                                  color=HINT, size_hint_y=None, height="60dp"))
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="48dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    # ---------- Fun studio ----------
    PICK_MULTI = 7781

    def _buttons_popup(self, title, opts, cols=1, hint=""):
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        pop = Popup(title=title, content=box, size_hint=(0.94, 0.88), separator_color=GOLD, title_color=GOLD)
        if hint:
            box.add_widget(Label(text=hint, color=HINT, font_size="14sp", size_hint_y=None, height="34dp"))
        grid = GridLayout(cols=cols, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        sv = ScrollView()
        sv.add_widget(grid)
        box.add_widget(sv)
        for label, fn, col in opts:
            b = RoundButton(text=label, bg=col, fg=TEXTCOL if col != GOLD else (0.1, 0.1, 0.1, 1),
                            size_hint_y=None, height="54dp", font_size="16sp", bold=True)

            def go(btn, fn=fn):
                pop.dismiss()
                Clock.schedule_once(lambda *_: fn(), 0.1)
            b.bind(on_press=go)
            grid.add_widget(b)
        close = RoundButton(text="Close", bg=GREY, fg=TEXTCOL, size_hint_y=None, height="48dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    def fun_studio(self, *_):
        self._buttons_popup("Fun studio", [
            ("Banana studio (realistic AI editing)", self.banana_studio, GOLD),
            ("Home page", self.app.open_home, GOLD),
            ("Genius Wealth (charts, prices, wealth plan)", self.wealth_menu, GOLD),
            ("Share Genius (WhatsApp, TikTok...)", self.share_menu, GOLD),
            ("Genius everywhere (bubble, Hey Genius)", self.everywhere_menu, GOLD),
            ("Genius Premium", self.premium_popup, GOLD),
            ("Music maker (AI songs)", self.music_menu, GOLD),
            ("Super zoom camera (1x-100x)", self.zoom_camera, GOLD),
            ("Zoom a photo", self.zoom_photo_menu, BLUE),
            ("Genius Ultra (best photo quality)", self.ultra_photo, GOLD),
            ("Pro camera looks (iPhone style)", self.looks_menu, GOLD),
            ("Replace something", lambda: self.ai_menu("Replace", REPLACE), GOLD),
            ("Change clothes", lambda: self.ai_menu("Change clothes", OUTFITS), GOLD),
            ("Change place", lambda: self.ai_menu("Change place", PLACES), GOLD),
            ("Beautiful photo", self.beauty_menu, GOLD),
            ("Make a collage", lambda: self.fun_pick("collage"), BLUE),
            ("Transform a picture", self.transform_menu, BLUE),
            ("Make a video slideshow", self.video_menu, BLUE),
            ("Collage of my newest 6 photos", lambda: self.fun_run("collage", newest_photos(6)), GREY),
            ("Video of my newest 6 photos", lambda: self.fun_run("video", newest_photos(6)), GREY),
            ("Watch fun videos", self.fun_videos, GOLD)], hint="Pick pictures and have fun")

    def _edit_src(self):
        src = LAST_IMAGE.get("path")
        if src and os.path.exists(src):
            return src
        me = my_photo()
        if me:
            remember_image(me, "my photo")
            return me
        return None

    def ai_menu(self, title, items):
        src = self._edit_src()
        if not src:
            self.say("First add your photo with + (or say setme after taking a selfie), then choose again.")
            return
        opts = [(t, lambda ins=ins: (remember_image(src, "photo to change"), self.do_edit(ins + "." + KEEP)), BLUE)
                for t, ins in items]
        opts.append(("Type my own...", lambda: self.say("Just type what you want, e.g. 'put me in a red suit at the airport'."), GREY))
        self._buttons_popup(title, opts, cols=2, hint="Changes: " + os.path.basename(src)[:28])

    def beauty_menu(self):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then tap Beautiful photo.")
            return
        opts = [("Quick beautify (instant)", lambda: self.fun_transform(src, "Beautify"), BLUE)]
        opts += [(t, lambda ins=ins: (remember_image(src, "photo to improve"), self.do_edit(ins + "." + KEEP)), GOLD)
                 for t, ins in BEAUTY]
        self._buttons_popup("Beautiful photo", opts, cols=1, hint="Blue = instant. Gold = AI")

    def video_menu(self):
        self._video_opts = getattr(self, "_video_opts", {"seconds": 2, "effect": ""})
        o = self._video_opts

        def setv(**k):
            o.update(k)
            self.say(f"Video: {o['seconds']} s per picture, effect: {o['effect'] or 'none'}. Now choose pictures.")
            self.video_menu()
        self._buttons_popup("Video slideshow", [
            ("Choose pictures and make it", lambda: self.fun_pick("video"), GOLD),
            ("Use my newest 6 photos", lambda: self.fun_run("video", newest_photos(6)), GOLD),
            ("Speed: fast (1 s)", lambda: setv(seconds=1), BLUE),
            ("Speed: normal (2 s)", lambda: setv(seconds=2), BLUE),
            ("Speed: slow (4 s)", lambda: setv(seconds=4), BLUE),
            ("Effect: none", lambda: setv(effect=""), GREY),
            ("Effect: beautify", lambda: setv(effect="Beautify"), GREY),
            ("Effect: vintage", lambda: setv(effect="Vintage"), GREY),
            ("Effect: black & white", lambda: setv(effect="Black & white"), GREY),
            ("Effect: vivid colours", lambda: setv(effect="Vivid colours"), GREY),
            ("Effect: soft glow", lambda: setv(effect="Soft glow"), GREY)], cols=2,
            hint=f"Now: {o['seconds']} s per picture, effect {o['effect'] or 'none'}")

    def looks_menu(self, *_):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then choose a look.")
            return
        opts = [(lk, lambda lk=lk: self.fun_transform(src, "LOOK:" + lk), BLUE) for lk in PRO_LOOKS]
        opts.append(("AI: flagship camera photo", lambda: self.banana_quick(
            "make it look like it was shot on the newest flagship phone camera: crisp detail, perfect exposure, "
            "rich true colours, natural skin, smooth background blur, HDR highlights"), GOLD))
        self._buttons_popup("Pro camera looks", opts, cols=2, hint="Instant looks. Gold = AI (Nano Banana)")

    # ---------- Super zoom camera: 1x to 100x ----------
    def zoom_camera(self, *_):
        try:
            from android.permissions import request_permissions, Permission
            from android.permissions import check_permission
            if not check_permission(Permission.CAMERA):
                def after(perms, grants):
                    if grants and all(grants):
                        Clock.schedule_once(lambda *_: self._open_camera(), 0.3)
                    else:
                        Clock.schedule_once(lambda *_: self.say(
                            "Genius needs camera permission. Allow it, or open Settings > Apps > Genius > Permissions."), 0)
                request_permissions([Permission.CAMERA], after)
                return
        except Exception:
            pass
        Clock.schedule_once(lambda *_: self._open_camera(), 0.2)

    # ---------- 111.5 answer ratings and Help improve Genius ----------
    def rate_answer(self, good):
        rt = getattr(self, "_rate", None)
        if not rt or rt.get("done"):
            if rt and not rt.get("told"):       # say it once; extra taps stay quiet
                rt["told"] = True
                self.say("Thanks, I already have your rating for that one.")
            return
        rt["done"] = True
        ai_record(rt["ai"], True, liked=bool(good))
        if good:
            self.say(f"Thanks! I'll use {AI_NAMES.get(rt['ai'], rt['ai'])} more for answers like that.")
            return
        opts = [("Tell me the right answer", lambda: setattr(self.inp, "text", "better: "), GOLD),
                ("Ask Genius Mind (every AI checks)", lambda: self.handle("mind " + rt["q"]) if rt.get("q") else None, BLUE)]
        if PIC_ASK.search(rt.get("q") or ""):    # a bad picture: offer a fresh one, not a written answer
            opts = [("Make a new picture", lambda: self.handle(rt["q"]), GOLD),
                    ("Tell me what to change", lambda: setattr(self.inp, "text", "change it to "), BLUE)]
        if reports_opt().get("on"):
            opts.append(("Send this to the developer", lambda: (send_report(
                "Bad answer", f"AI: {rt['ai']}\nQ: {rt['q'][:600]}\nA: {rt['a'][:1500]}"),
                self.say("Sent. Thank you for helping Genius get better.")), GREY))
        else:
            opts.append(("Turn on Help improve Genius", self.help_improve_menu, GREY))
        self._buttons_popup("Sorry about that", opts, cols=1,
                            hint="I'll use a different AI for questions like that")

    def help_improve_menu(self, *_):
        on = bool(reports_opt().get("on"))

        def toggle():
            reports_set(not on)
            self.say("Help improve Genius is ON. Thank you! Once a day Genius sends the developer which parts "
                     "had problems (never your chats, name or files), and you can send bad answers with one tap."
                     if not on else "Help improve Genius is OFF. Nothing is sent.")
        rows = ai_report()
        self._buttons_popup("Help improve Genius", [
            (("Turn OFF" if on else "Turn ON") + " Help improve Genius", toggle, GOLD),
            ("Add another free AI", self.key_wizard, BLUE),
            ("See how each AI is doing", lambda: self.say("\n".join(rows) if rows else
                                                           "No AI connected yet. Tap Add another free AI."), BLUE),
        ], cols=1, hint="Genius learns which AI answers best on your phone and uses it first")

    # ---------- profile picture ----------
    def change_profile_photo(self, *_):
        def cam(eye):
            self._to_profile = True
            self.take_photo(front=True, eye=eye)

        def gallery():
            self._to_profile = True
            self.pick_gallery()

        def last():
            self._apply_profile(LAST_IMAGE.get("path"))

        def remove():
            remove_profile_photo()
            self._redraw_profile()
            self.say("Profile picture removed. Your first letter shows instead.")
        opts = [("Take a selfie", lambda: cam(False), GOLD),
                ("Beauty selfie (Genius Eye)", lambda: cam(True), GOLD),
                ("Choose from gallery", gallery, BLUE)]
        if LAST_IMAGE.get("path") and os.path.exists(LAST_IMAGE["path"]):
            opts.append(("Use my last picture", last, BLUE))
        if profile_photo():
            opts.append(("Remove profile picture", remove, GREY))
        self._buttons_popup("Profile picture", opts, cols=1, hint="Only you see it on this account")

    def _redraw_profile(self):
        for w in (getattr(self, "profile_chip", None),):
            try:
                w.redraw()
            except Exception:
                pass
        try:
            hs = getattr(self.app, "home_screen", None)
            if hs is not None:
                for c in hs.walk():
                    if isinstance(c, ProfileChip):
                        c.redraw()
        except Exception:
            pass

    def _apply_profile(self, src, beauty=False):
        if not src or not os.path.exists(src):
            self.say("Take a selfie or pick a picture first.")
            return

        def work(*_):
            try:
                use = genius_eye(src, "natural")[0] if beauty else src
                out = set_profile_photo(use)
            except Exception as e:
                log(f"PROFILE pic: {type(e).__name__}: {e}")
                out = None

            def done(*_):
                if out:
                    self._redraw_profile()
                    self.show_image(out, "This is your new profile picture.")
                else:
                    self.say("I couldn't use that picture. Try another one.")
            Clock.schedule_once(done, 0)
        threading.Thread(target=work, daemon=True).start()

    def camera_menu(self, *_):
        self._buttons_popup("Camera", [
            ("Genius Eye (beauty selfie)", lambda: self.take_photo(front=True, eye=True), GOLD),
            ("Genius Eye (back camera)", lambda: self.take_photo(front=False, eye=True), GOLD),
            ("Selfie (front camera)", lambda: self.take_photo(front=True), GOLD),
            ("Back camera", lambda: self.take_photo(front=False), GOLD),
            ("Live zoom camera (1x-100x)", self.zoom_camera, BLUE),
            ("Effects for my last photo", self.transform_menu, BLUE),
            ("Pick from gallery", self.pick_gallery, GREY)], hint="Take a photo, then add effects")

    def _open_camera(self, index=0):
        from kivy.uix.camera import Camera
        from kivy.uix.slider import Slider
        from kivy.uix.stencilview import StencilView
        from kivy.uix.floatlayout import FloatLayout
        from kivy.graphics import PushMatrix, PopMatrix, Rotate
        cam = None
        for res in ((1280, 720), (640, 480), (-1, -1)):
            try:
                cam = Camera(index=index, resolution=res, play=True, allow_stretch=True, keep_ratio=True)
                break
            except Exception as e:
                log(f"CAMERA {res}: {e}")
        if cam is None:
            self.say("The live camera didn't start on this phone, so I'm opening your phone's camera instead.")
            self.take_photo(front=bool(index))
            return
        st = {"zoom": 1.0, "rot": -90 if os.path.isdir("/storage/emulated/0") else 0, "index": index}
        stencil = StencilView()
        holder = FloatLayout()
        stencil.add_widget(holder)
        holder.add_widget(cam)
        with cam.canvas.before:
            PushMatrix()
            rot = Rotate(angle=st["rot"], origin=cam.center)
        with cam.canvas.after:
            PopMatrix()

        def layout(*_):
            z = st["zoom"]
            holder.size, holder.pos = stencil.size, stencil.pos
            w, h = stencil.width * z, stencil.height * z
            if st["rot"] in (90, -90):
                w, h = h, w
            cam.size_hint = (None, None)
            cam.size = (w, h)
            cam.center = stencil.center
            rot.origin = cam.center
            rot.angle = st["rot"]
        stencil.bind(size=layout, pos=layout)
        box = BoxLayout(orientation="vertical", spacing=6, padding=6)
        box.add_widget(stencil)
        lbl = Label(text="1.0x", size_hint_y=None, height="34dp", color=GOLD, font_size="22sp", bold=True)
        box.add_widget(lbl)
        sl = Slider(min=0, max=2, value=0, size_hint_y=None, height="44dp")   # log scale: 10**0..10**2

        def on_zoom(*_):
            st["zoom"] = round(10 ** sl.value, 1)
            lbl.text = f"{st['zoom']:g}x" + ("  (AI super zoom)" if st["zoom"] >= 10 else "")
            layout()
        sl.bind(value=on_zoom)
        box.add_widget(sl)
        presets = BoxLayout(size_hint_y=None, height="46dp", spacing=4)
        import math
        for z in (1, 2, 5, 10, 30, 100):
            b = RoundButton(text=f"{z}x", bg=GREY, fg=TEXTCOL, font_size="15sp", bold=True)
            b.bind(on_press=lambda btn, z=z: setattr(sl, "value", math.log10(z)))
            presets.add_widget(b)
        box.add_widget(presets)
        row = BoxLayout(size_hint_y=None, height="56dp", spacing=6)
        pop = Popup(title="Super zoom camera", content=box, size_hint=(1, 1),
                    separator_color=GOLD, title_color=GOLD, auto_dismiss=False)

        def close(*_):
            try:
                cam.play = False
            except Exception:
                pass
            pop.dismiss()

        def shoot(*_):
            try:
                from PIL import Image
                tex = cam.texture
                im = Image.frombytes("RGBA", tex.size, tex.pixels).transpose(Image.FLIP_TOP_BOTTOM).convert("RGB")
                if st["rot"]:
                    im = im.rotate(st["rot"], expand=True)
                raw = os.path.join(genius_dl("camera"), f"photo_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
                try:
                    im = ultra_process(im)          # every shot gets the Genius Ultra engine
                except Exception as e:
                    log(f"ULTRA: {e}")
                im.save(raw, quality=97, subsampling=0)
            except Exception as e:
                log(f"CAMERA shoot: {e}")
                self.say("I couldn't take the picture. Try again.")
                return
            z = st["zoom"]
            close()
            if z <= 1.05:
                remember_image(raw, "camera photo")
                self.show_image(raw, "Photo taken")
                return
            self._zoom_and_show(raw, z)

        def rotate(*_):
            st["rot"] = {0: -90, -90: 90, 90: 180, 180: 0}[st["rot"]]
            layout()

        def switch(*_):
            close()
            Clock.schedule_once(lambda *_: self._open_camera(1 - st["index"]), 0.4)
        for t, fn, col in (("Close", close, RED), ("Turn", rotate, GREY), ("Flip cam", switch, GREY),
                           ("Take photo", shoot, GOLD)):
            b = RoundButton(text=t, bg=col, fg=(0.1, 0.1, 0.1, 1) if col == GOLD else TEXTCOL,
                            font_size="16sp", bold=True)
            b.bind(on_press=fn)
            row.add_widget(b)
        box.add_widget(row)
        pop.open()
        Clock.schedule_once(layout, 0.2)

    def _zoom_and_show(self, src, z):
        if getattr(self, "busy", False):
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        self.say(f"Zooming {z:g}x and sharpening...")

        def d(*_):
            try:
                out, msg = super_zoom(src, z)
            except Exception as e:
                log(f"ZOOM failed: {e}")
                out, msg = None, "Zoom didn't work on this photo. Add it again with + and retry."

            def done(*_):
                self.busy = False
                if out:
                    remember_image(out, f"{z:g}x zoom photo")
                    self.show_image(out, msg + (" Say 'ai zoom' to rebuild fine detail with AI." if z >= 4 else ""))
                    if z >= 10:
                        self.say("At high zoom, say 'ai zoom' and Nano Banana will rebuild sharp detail "
                                 "without changing what's in the photo.")
                else:
                    self.say(msg)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    # ---------- Genius everywhere ----------
    def share_menu(self, *_):
        apps = [("WhatsApp", "com.whatsapp"), ("WhatsApp Business", "com.whatsapp.w4b"),
                ("Facebook", "com.facebook.katana"), ("Facebook Lite", "com.facebook.lite"),
                ("TikTok", "com.zhiliaoapp.musically"), ("Instagram", "com.instagram.android"),
                ("X (Twitter)", "com.twitter.android"), ("Telegram", "org.telegram.messenger"),
                ("Messenger", "com.facebook.orca"), ("Snapchat", "com.snapchat.android")]

        def go(pkg=None):
            try:
                share_genius(pkg)
            except Exception as e:
                log(f"SHARE failed: {e}")
                copy_link()

        def copy_link():
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(share_text())
                self.say("Copied! Paste it in any chat, status or post so friends can download Genius:\n" + newest_apk_link())
            except Exception:
                self.say("Send friends this link to download Genius:\n" + newest_apk_link())
        self._buttons_popup("Share Genius", [(n, lambda p=p: go(p), BLUE) for n, p in apps] +
                            [("Copy link", copy_link, GREY), ("Any other app...", go, GOLD)], cols=2,
                            hint="Tap an app. Friends download Genius from your link")

    def everywhere_menu(self, *_):
        on = EVERYWHERE["bubble_on"]
        hey = getattr(self, "hey_on", False)
        self._buttons_popup("Genius everywhere", [
            ("Floating bubble: " + ("ON" if on else "OFF"), self.toggle_bubble, GOLD),
            ('"Hey Genius" wake word: ' + ("ON" if hey else "OFF"), self.toggle_hey, GOLD),
            ("Home-screen button: Talk", lambda: self.add_shortcut("talk", "Genius Talk"), BLUE),
            ("Home-screen button: Camera", lambda: self.add_shortcut("camera", "Genius Camera"), BLUE),
            ("Home-screen button: Selfie", lambda: self.add_shortcut("selfie", "Genius Selfie"), BLUE),
            ("Home-screen button: Music", lambda: self.add_shortcut("sound", "Genius Music"), BLUE),
            ("Home-screen button: Ultra photo", lambda: self.add_shortcut("ultra", "Genius Ultra"), BLUE),
        ], cols=1, hint="Use Genius from anywhere on your phone")

    def toggle_bubble(self, *_):
        EVERYWHERE["bubble_on"] = not EVERYWHERE["bubble_on"]
        everywhere_save()
        if not EVERYWHERE["bubble_on"]:
            bubble_hide()
            self.say("Floating bubble is off.")
            return
        try:
            if not can_draw_overlay():
                ask_overlay_permission()
                self.say("Turn on 'Allow display over other apps' for Genius, then come back. "
                         "When you leave Genius, a gold G bubble will float over your apps. Tap it to talk to me.")
                return
        except Exception as e:
            self.say(f"The bubble needs Android 8 or newer. ({e})")
            return
        self.say("Bubble is on. When you leave Genius, a gold G floats over your apps. Tap it to talk, drag it to move.")

    def add_shortcut(self, action, label):
        try:
            ok = pin_shortcut(action, label)
        except Exception as e:
            log(f"SHORTCUT: {e}")
            ok = False
        self.say(f"Tap 'Add' and the '{label}' button goes on your home screen." if ok
                 else "Your phone's home screen doesn't allow adding buttons this way.")

    def run_action(self, action):
        if not action:
            return
        log(f"EVERYWHERE action: {action}")
        if action == "talk":
            if not getattr(self, "talking", False):
                self.speak_input()
        else:
            self.handle(action)

    # "Hey Genius": while Genius is open, it quietly listens for its name
    def toggle_hey(self, *_):
        self.hey_on = not getattr(self, "hey_on", False)
        if self.hey_on:
            try:
                if not mic_permission_ok():
                    self.hey_on = False
                    self.say("Allow the microphone first, then turn Hey Genius on again.")
                    return
            except Exception:
                pass
            self.say("Hey Genius is on. Just say 'Hey Genius' and what you want, any time Genius is open.")
            Clock.schedule_once(lambda *_: self._hey_listen(), 3)
        else:
            native_stop()
            self.say("Hey Genius is off.")

    def _hey_listen(self, *_):
        if not getattr(self, "hey_on", False) or getattr(self, "talking", False) or self.busy:
            if getattr(self, "hey_on", False):
                Clock.schedule_once(self._hey_listen, 4)
            return
        try:
            native_listen(self._hey_heard, lambda msg, code=0: Clock.schedule_once(self._hey_listen, 1.0))
        except Exception as e:
            log(f"HEY: {e}")
            self.hey_on = False

    def _hey_heard(self, words):
        w = (words or "").lower()
        m = re.search(r"\b(?:hey|hi|ok|okay)?\s*(?:genius|jeanious|genus|genie us)\b[\s,]*(.*)", w)
        if m:
            rest = m.group(1).strip(" ,.")
            if rest:
                self.handle(rest)
            else:
                tts("Yes?")
                self.speak_input()
        Clock.schedule_once(self._hey_listen, 1.5)

    # ---------- Genius Premium ----------
    def premium_popup(self, *_):
        ok, msg = premium_status()
        box = BoxLayout(orientation="vertical", spacing=10, padding=14)
        pay = (f"Pay by Mobile Money to [b]{PAY_NUMBER}[/b] ({PAY_NAME})" if PAY_NUMBER
               else f"Pay by Mobile Money to the owner, {PAY_NAME}")
        email = accounts_load().get(CURRENT["name"], {}).get("email", "")
        txt = (f"[b][color=ffc84d]Genius Premium[/color][/b]\n{msg}\n\n"
               f"Unlock everything for [b]{PREMIUM_PRICE} a week[/b].\n"
               f"1. {pay}.\n2. Send the owner your email ([color=9db4ff]{email}[/color]) and the transaction ID.\n"
               f"3. Type the unlock code you get below.")
        if CURRENT["owner"]:
            txt = (f"[b][color=ffc84d]Genius Premium[/color][/b]\n{msg}\n\nOther people get {TRIAL_DAYS} free days "
                   f"{TRIAL_USES} uses (unlimited downloads), then pay {PREMIUM_PRICE} a week.\n"
                   f"When someone pays, say: makecode their@email.com (or makecode their@email.com 4 for 4 weeks).")
        lab = Label(text=txt, markup=True, color=TEXTCOL, font_size="15sp", halign="left", valign="top")
        lab.bind(width=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        box.add_widget(lab)
        pop = Popup(title="Upgrade", content=box, size_hint=(0.94, 0.78), separator_color=GOLD, title_color=GOLD)
        if not CURRENT["owner"]:
            code_in = style_input(TextInput(hint_text="Unlock code, like W1-2610-AB12CD", multiline=False,
                                            size_hint_y=None, height="52dp", font_size="17sp"))
            box.add_widget(code_in)
            info = Label(text="", color=(1, 0.5, 0.5, 1), size_hint_y=None, height="26dp", font_size="14sp")
            box.add_widget(info)

            def go(*_):
                err = premium_redeem(code_in.text)
                if err:
                    info.text = err
                    return
                pop.dismiss()
                self.say("Welcome to Genius Premium! Everything is unlocked. " + premium_status()[1])
            b = RoundButton(text="Unlock Premium", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="54dp", font_size="18sp", bold=True)
            b.bind(on_press=go)
            box.add_widget(b)
        c = RoundButton(text="Close", bg=GREY, size_hint_y=None, height="46dp")
        c.bind(on_press=pop.dismiss)
        box.add_widget(c)
        pop.open()

    def owner_make_code(self, line):
        if not CURRENT["owner"]:
            self.say("Only the owner can make unlock codes.")
            return
        parts = line.split()
        parts = parts[2:] if parts[0].lower() == "make" else parts[1:]
        if not parts:
            self.say("Say: makecode their@email.com  (add a number for more weeks, like makecode name@gmail.com 4)")
            return
        who = parts[0].strip().lower()
        months = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() and 1 <= int(parts[1]) <= 52 else 1
        if "@" not in who:
            acc = accounts_load().get(who)
            who = acc.get("email", "") if acc else ""
            if not who:
                self.say("I need their email, the one they signed up with.")
                return
        code = premium_code(who, months)
        log(f"PREMIUM CODE made for {who} ({months} week)")
        self.say(f"Unlock code for {who}, {months} week{'s' if months > 1 else ''}: {code}. "
                 f"Send it to them only after you see the payment. It works this month and next.")

    # ---------- Music maker ----------
    def music_menu(self, *_):
        opts = [("Afrobeat", "afrobeat"), ("Amapiano", "amapiano"), ("Kadongo Kamu", "kadongo kamu"),
                ("Luganda praise", "luganda praise"), ("Gospel", "gospel"), ("Dancehall", "dancehall"),
                ("Hip hop", "hip hop"), ("RnB", "rnb"), ("Love ballad", "love ballad"), ("Kids song", "kids"),
                ("Pop hit", "pop"), ("Lo-fi chill", "lofi"), ("Cinematic", "cinematic"), ("Dance", "dance")]
        self._buttons_popup("Music maker", [(t, lambda k=k: self.make_music(k + " song"), GOLD if i < 4 else BLUE)
                                            for i, (t, k) in enumerate(opts)] +
                            [("Describe my own...", lambda: self.say("Say 'make song' then the style and what it's about, "
                                                                     "like: make song amapiano about my mum. Add 'in Luganda' "
                                                                     "or 'English and Luganda' if you like."), GREY),
                             ("Sing it in my voice (record)", self.vocal_studio, RED),
                             ("Real singer song (ElevenLabs)", lambda: self.say(
                                 "Say 'pro song' then the style and topic, like: pro song amapiano about my mum. "
                                 "It needs your ElevenLabs key (seteleven)."), BLUE2),
                             ("Play my last song + lyrics", self.open_player, GREY)],
                            cols=2, hint="Pick a style. Genius writes the words and plays them with lyrics on screen")

    def make_music(self, desc=""):
        if self.busy:
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        req = song_request(desc)
        st = _STYLES[req["style"]]
        how = "you asked for" if req["chosen"] == "you" else "Genius picked for this idea"
        self.say(f"Making a {st['label']} song ({how}). Writing the words, then playing {st['lead']}, "
                 f"{st['chords']} and {st['bass']} at about {st['bpm']} BPM and mixing it like a studio. "
                 "On a phone this takes about 1 to 3 minutes, keep Genius open...")

        def d(*_):
            try:
                out, plan = make_song(desc)
                err = None
            except MemoryError:
                out, plan, err = None, None, "The phone ran low on memory. Close other apps and try again."
            except Exception as e:
                log(f"MUSIC failed: {e}")
                out, plan, err = None, None, "Something went wrong while mixing. Try again, or pick another style."

            def done(*_):
                self.busy = False
                if not out:
                    self._sing_after = False
                    self.say(f"Sorry, the song didn't work. {err}")
                    return
                self._last_song = out
                m = plan.get("meta", {})
                chorus = "\n".join(plan.get("sections", {}).get("chorus", [])) or plan.get("lyrics", "")
                self.show("AI", f"[b]{_esc(plan['title'])}[/b]\n"
                                f"Style: {plan.get('label', plan['style'])} "
                                f"({'your choice' if plan.get('chosen') == 'you' else 'Genius picked'}), "
                                f"{plan['key']} {plan['scale']}, {plan['bpm']} BPM, "
                                f"{_fmt_time(plan.get('duration', 0))} long.\n"
                                f"Instruments: {', '.join(m.get('instruments', []))}. Words by {plan.get('lyrics_by', 'Genius')}.\n"
                                f"Saved in {nice_where(out)} as {os.path.basename(out)}.\n"
                                f"Say 'play song' or 'lyrics' to see the words again, 'pause music' or 'stop music'."
                                + (f"\n\n[i]Chorus:[/i]\n{_esc(chorus)}" if chorus else ""))
                if getattr(self, "_sing_after", False):
                    self._sing_after = False
                    self.vocal_studio(out)
                else:
                    self.open_player(out, plan)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def open_player(self, wav=None, plan=None, *_):
        """Karaoke view: plays the song and lights up each line in time with the music."""
        wav = wav if isinstance(wav, str) else None
        wav = wav or getattr(self, "_last_song", None) or newest_song()
        if not wav or not os.path.exists(wav):
            self.say("No song yet. Say 'make song amapiano about my mum', or 'music' to pick a style.")
            return
        self._last_song = wav
        meta, lines = load_song_timeline(wav, plan)
        dur = meta.get("duration") or 1.0
        if not (_luganda.get("file") == wav and sound_playing()):
            if not _play_file(wav):
                self.say("I couldn't play the song here. Open it from your Files app: "
                         f"{nice_where(wav)}/{os.path.basename(wav)}")
        st = dict(t0=time.time(), offset=0.0, paused=False, ended=False, clock=False, idx=-2)
        acc, hint = _hx(PAL["accent"]), _hx(PAL["hint"])
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        info = " \u00b7 ".join(x for x in (meta.get("label") or meta.get("style", "").title(),
                                            f"{meta.get('key', '')} {meta.get('scale', '')}".strip(),
                                            f"{meta['bpm']} BPM" if meta.get("bpm") else "") if x)
        head = Label(text=f"[b][color={acc}]{_esc(meta.get('title', 'Your song'))}[/color][/b]\n"
                          f"[size=13sp][color={hint}]{_esc(info)}[/color][/size]",
                     markup=True, font_size="20sp", size_hint_y=None, height="62dp", halign="center", valign="middle")
        head.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        box.add_widget(head)
        sv = ScrollView(bar_color=(PAL["accent"][0], PAL["accent"][1], PAL["accent"][2], 0.6), bar_width="3dp")
        lyr = Label(text=karaoke_markup(lines, -1), markup=True, size_hint_y=None, halign="center", valign="top",
                    line_height=1.3, padding=(6, 40))
        lyr.bind(width=lambda w, *_: setattr(w, "text_size", (w.width, None)),
                 texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1]))
        sv.add_widget(lyr)
        box.add_widget(sv)
        clock_lbl = Label(text=f"0:00 / {_fmt_time(dur)}", color=HINT, font_size="14sp", size_hint_y=None, height="22dp")
        box.add_widget(clock_lbl)
        prog = Widget(size_hint_y=None, height="6dp")
        with prog.canvas:
            Color(1, 1, 1, 0.12)
            track = RoundedRectangle(radius=[3])
            Color(*PAL["accent"], 1)
            fill = RoundedRectangle(radius=[3])
        box.add_widget(prog)
        btns = BoxLayout(size_hint_y=None, height="54dp", spacing=8)
        b_pause = RoundButton(text="Pause", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), bold=True, font_size="17sp")
        b_stop = RoundButton(text="Stop", bg=BLUE, fg=TEXTCOL, bold=True, font_size="17sp")
        b_close = RoundButton(text="Close", bg=GREY, fg=TEXTCOL, bold=True, font_size="17sp")
        for b in (b_pause, b_stop, b_close):
            btns.add_widget(b)
        box.add_widget(btns)
        pop = Popup(title="Genius karaoke", content=box, size_hint=(0.96, 0.92), separator_color=GOLD, title_color=GOLD)

        def now():
            if st["paused"] or st["ended"]:
                return st["offset"]
            el = st["offset"] + time.time() - st["t0"]
            p = sound_pos()
            if not st["clock"] and (p is None or (p <= 0.01 and el > 1.2)):
                st["clock"] = True          # this player can't tell its position: follow the clock instead
            return el if st["clock"] or p is None else p

        def tick(*_):
            pos = now()
            if not st["paused"] and not st["ended"] and (time.time() - st["t0"] > 1.5) and \
                    (not sound_playing() or pos >= dur - 0.05):
                st["ended"], st["offset"] = True, min(pos, dur)
                b_pause.text = "Play again"
            pos = min(pos, dur)
            idx = current_line(lines, pos)
            clock_lbl.text = f"{_fmt_time(pos)} / {_fmt_time(dur)}"
            track.pos, track.size = prog.pos, prog.size
            fill.pos, fill.size = prog.pos, (prog.width * pos / max(0.1, dur), prog.height)
            if idx != st["idx"]:
                st["idx"] = idx
                lyr.text = karaoke_markup(lines, idx)
                if len(lines) > 1 and idx >= 0:
                    Animation.cancel_all(sv, "scroll_y")
                    Animation(scroll_y=max(0.0, min(1.0, 1 - idx / float(len(lines) - 1))), d=0.35).start(sv)

        def pause(*_):
            if st["ended"]:                  # play again from the start
                if _play_file(wav):
                    st.update(t0=time.time(), offset=0.0, paused=False, ended=False, clock=False, idx=-2)
                    b_pause.text = "Pause"
                return
            if st["paused"]:
                at = sound_resume()
                st.update(t0=time.time(), offset=at if at is not None else st["offset"], paused=False)
                b_pause.text = "Pause"
            else:
                st["offset"] = now()
                sound_pause()
                st["paused"] = True
                b_pause.text = "Play"

        def stop(*_):
            sound_stop()
            st.update(ended=True, offset=0.0, paused=False)
            b_pause.text = "Play again"
            tick()

        b_pause.bind(on_press=pause)
        b_stop.bind(on_press=stop)
        b_close.bind(on_press=pop.dismiss)      # closing keeps the music playing; 'stop music' stops it
        ev = Clock.schedule_interval(tick, 0.15)
        pop.bind(on_dismiss=lambda *_: ev.cancel())
        pop.open()
        tick()

    def pro_song(self, desc=""):
        """Real singer + band from ElevenLabs Music, with Genius's lyrics and karaoke."""
        if not eleven_key():
            self.say("For songs with a real singing voice, add your ElevenLabs key: open elevenlabs.io, sign in, "
                     "go to Developers, API keys, create a key, then type seteleven, a space, and the key.")
            return
        if self.busy:
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        self.say("Writing the words, then ElevenLabs is singing and playing your song. This takes 1 to 3 minutes "
                 "and uses about 900 ElevenLabs credits per minute of song. Keep Genius open...")

        def work():
            try:
                out, plan = eleven_music_song(desc or "afrobeat song")
                err = None
            except Exception as e:
                log(f"PRO SONG failed: {e}")
                out, plan, err = None, None, str(e)

            def done(*_):
                self.busy = False
                if not out:
                    self.say(f"Sorry, the song didn't work. {err}")
                    return
                self._last_song = out
                chorus = "\n".join(plan.get("sections", {}).get("chorus", []))
                self.show("AI", f"[b]{_esc(plan['title'])}[/b]\nSung and played by ElevenLabs, words by "
                                f"{plan.get('lyrics_by', 'Genius')}. {plan.get('label', '')}, about "
                                f"{_fmt_time(plan.get('duration', 0))}.\nSaved in {nice_where(out)} as "
                                f"{os.path.basename(out)}." + (f"\n\n[i]Chorus:[/i]\n{_esc(chorus)}" if chorus else ""))
                self.open_player(out, plan)
            Clock.schedule_once(done, 0)
        threading.Thread(target=work, daemon=True).start()

    def voice_clone_setup(self, *_):
        """Record about a minute of the user's voice and make their ElevenLabs voice clone."""
        if not eleven_key():
            self.say("To let Genius sing in your voice you need an ElevenLabs key with voice cloning (Starter plan). "
                     "Open elevenlabs.io, sign in, go to Developers, API keys, create a key, then type seteleven, "
                     "a space, and the key.")
            return
        try:
            if not mic_permission_ok():
                self.say("Allow the microphone for Genius, then say clone my voice again.")
                return
        except Exception:
            pass
        rec = VocalRecorder()
        st = dict(mode="ready", t0=0.0, take=None)
        passage = ("Read this out loud in your normal voice, then sing a little of any song you like:\n\n"
                   "Good morning! My name is me, and this is my voice. I love music, I love my family, "
                   "and I love the beautiful hills of Uganda. Every day I wake up, I thank God, and I go out to "
                   "chase my dreams. Some days are hard and some days are sweet, but I keep moving, I keep "
                   "smiling, and I keep singing. Mama, thank you for everything. Friends, let us dance tonight!")
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        txt = Label(text=passage, font_size="17sp", color=TEXTCOL, halign="left", valign="top")
        txt.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        box.add_widget(txt)
        status = Label(text="Record 45 to 90 seconds in a quiet place.", color=HINT, font_size="15sp",
                       size_hint_y=None, height="26dp")
        box.add_widget(status)
        meter = Widget(size_hint_y=None, height="26dp")
        with meter.canvas:
            Color(1, 1, 1, 0.10)
            m_track = RoundedRectangle(radius=[13])
            m_col = Color(0.3, 0.9, 0.45, 1)
            m_fill = RoundedRectangle(radius=[13])
        box.add_widget(meter)
        row = BoxLayout(size_hint_y=None, height="56dp", spacing=8)
        b_rec = RoundButton(text="\u25cf  Record", bg=RED, fg=TEXTCOL, bold=True, font_size="17sp")
        b_stop = RoundButton(text="\u25a0  Stop", bg=BLUE, fg=TEXTCOL, bold=True, font_size="17sp")
        row.add_widget(b_rec)
        row.add_widget(b_stop)
        box.add_widget(row)
        row2 = BoxLayout(size_hint_y=None, height="54dp", spacing=8)
        b_make = RoundButton(text="Make my voice clone", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), bold=True, font_size="16sp")
        b_close = RoundButton(text="Close", bg=GREY, fg=TEXTCOL, bold=True, font_size="16sp", size_hint_x=0.4)
        row2.add_widget(b_make)
        row2.add_widget(b_close)
        box.add_widget(row2)
        pop = Popup(title="Clone my voice", content=box, size_hint=(0.97, 0.94), separator_color=GOLD, title_color=GOLD)

        def tick(*_):
            m_track.pos, m_track.size = meter.pos, meter.size
            lv = rec.level if st["mode"] == "rec" else 0.0
            m_fill.pos, m_fill.size = meter.pos, (max(meter.height, meter.width * lv) if lv > 0.01 else 0, meter.height)
            m_col.rgba = (0.95, 0.3, 0.35, 1) if lv > 0.92 else (1, 0.78, 0.3, 1) if lv > 0.7 else (0.3, 0.9, 0.45, 1)
            if st["mode"] == "rec":
                sec = time.time() - st["t0"]
                status.text = f"Recording {_fmt_time(sec)}" + ("  - good, you can stop" if sec >= 45 else "")
                if rec.error:
                    stop()
                    status.text = f"The microphone stopped: {rec.error}"
                elif sec >= 150:
                    stop()

        def record(*_):
            if st["mode"] != "ready":
                return
            take = os.path.join(genius_dl("music"), "voice_sample.wav")
            rec.start(take)
            st.update(mode="rec", t0=time.time(), take=None)

        def stop(*_):
            if st["mode"] != "rec":
                return
            st["mode"] = "ready"
            got = rec.stop()
            if got and rec.seconds >= 20:
                st["take"] = got
                status.text = f"Got {int(rec.seconds)} seconds. Tap Make my voice clone."
            else:
                status.text = "That was too short. Record at least 30 seconds."

        def make(*_):
            if st["mode"] != "ready" or not st["take"]:
                status.text = "Record your voice first."
                return
            st["mode"] = "busy"
            status.text = "Making your voice clone at ElevenLabs..."

            def work():
                try:
                    eleven_clone(st["take"])
                    err = None
                except Exception as e:
                    err = str(e)

                def done(*_):
                    st["mode"] = "ready"
                    if err:
                        status.text = "It didn't work."
                        self.say(err)
                        return
                    try:
                        os.remove(st["take"])                 # the sample now lives only in the user's ElevenLabs account
                    except Exception:
                        pass
                    pop.dismiss()
                    self.say("Your voice clone is ready. Make a song, then tap 'AI sings in my voice' in the vocal studio, "
                             "or say ai sing my song.")
                Clock.schedule_once(done, 0)
            threading.Thread(target=work, daemon=True).start()

        def close(*_):
            if st["mode"] == "rec":
                rec.stop()
            pop.dismiss()

        b_rec.bind(on_press=record)
        b_stop.bind(on_press=stop)
        b_make.bind(on_press=make)
        b_close.bind(on_press=close)
        ev = Clock.schedule_interval(tick, 0.08)
        pop.bind(on_dismiss=lambda *_: (ev.cancel(), rec.running and rec.stop()))
        pop.open()

    def ai_sing(self, wav=None, *_):
        """The user's voice clone performs the song's words over the beat."""
        wav = wav if isinstance(wav, str) else None
        wav = wav or getattr(self, "_last_song", None) or newest_song()
        if not eleven_key() or not eleven_voice():
            self.voice_clone_setup()
            return
        if not wav or not os.path.exists(wav):
            self.say("Make a song first, like: make song amapiano about my mum. Then say ai sing my song.")
            return
        if "_my_voice_" in os.path.basename(wav) or not wav.lower().endswith(".wav"):
            self.say("That song already has singing. Make a new Genius beat first: make song amapiano about my mum.")
            return
        if self.busy:
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        self.say("Your voice clone is singing the words now. This takes about 1 to 2 minutes and uses your "
                 "ElevenLabs credits...")

        def work():
            try:
                out, err = ai_sing_song(wav), None
            except Exception as e:
                log(f"AI SING failed: {e}")
                out, err = None, str(e)

            def done(*_):
                self.busy = False
                if not out:
                    self.say(f"Sorry, the AI singing didn't work. {err}")
                    return
                self._last_song = out
                self.show("AI", f"Done! Your song is sung in your voice. Saved in {nice_where(out)} as "
                                f"{os.path.basename(out)}.")
                self.open_player(out)
            Clock.schedule_once(done, 0)
        threading.Thread(target=work, daemon=True).start()

    def vocal_studio(self, wav=None, *_):
        """Record your own voice singing over a Genius beat, with the words on screen and a live voice meter."""
        wav = wav if isinstance(wav, str) else None
        wav = wav or getattr(self, "_last_song", None) or newest_song()
        if not wav or not os.path.exists(wav):
            self.say("First make a beat for your song. Say 'song in my voice' then the style and topic, like: "
                     "song in my voice amapiano about my mum.")
            return
        try:
            if not mic_permission_ok():
                self.say("Allow the microphone for Genius, then open the vocal studio again.")
                return
        except Exception:
            pass
        if not wav.lower().endswith(".wav"):
            self.say("That song already has a singer. Make a Genius beat to sing on: song in my voice amapiano about my mum.")
            return
        sound_stop()
        meta, lines = load_song_timeline(wav)
        dur = meta.get("duration") or wav_seconds(wav) or 1.0
        rec = VocalRecorder()
        st = dict(mode="ready", t0=0.0, take=None, mixed=None, idx=-2)
        acc, hint = _hx(PAL["accent"]), _hx(PAL["hint"])
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        head = Label(text=f"[b][color={acc}]{_esc(meta.get('title', 'Your song'))}[/color][/b]\n"
                          f"[size=13sp][color={hint}]Sing it in your own voice. Use earphones so the beat stays clean.[/color][/size]",
                     markup=True, font_size="20sp", size_hint_y=None, height="62dp", halign="center", valign="middle")
        head.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        box.add_widget(head)
        sv = ScrollView(bar_width="3dp")
        lyr = Label(text=karaoke_markup(lines, -1), markup=True, size_hint_y=None, halign="center", valign="top",
                    line_height=1.3, padding=(6, 40))
        lyr.bind(width=lambda w, *_: setattr(w, "text_size", (w.width, None)),
                 texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1]))
        sv.add_widget(lyr)
        box.add_widget(sv)
        status = Label(text="Ready. Tap Record, then sing when the words light up.", color=HINT, font_size="15sp",
                       size_hint_y=None, height="24dp")
        box.add_widget(status)
        meter = Widget(size_hint_y=None, height="26dp")           # the voice bar: shows how loud you sing
        with meter.canvas:
            Color(1, 1, 1, 0.10)
            m_track = RoundedRectangle(radius=[13])
            m_col = Color(0.3, 0.9, 0.45, 1)
            m_fill = RoundedRectangle(radius=[13])
        box.add_widget(meter)
        prog = Widget(size_hint_y=None, height="6dp")
        with prog.canvas:
            Color(1, 1, 1, 0.12)
            p_track = RoundedRectangle(radius=[3])
            Color(*PAL["accent"], 1)
            p_fill = RoundedRectangle(radius=[3])
        box.add_widget(prog)
        row1 = BoxLayout(size_hint_y=None, height="56dp", spacing=8)
        b_rec = RoundButton(text="\u25cf  Record", bg=RED, fg=TEXTCOL, bold=True, font_size="18sp")
        b_stop = RoundButton(text="\u25a0  Stop", bg=BLUE, fg=TEXTCOL, bold=True, font_size="18sp")
        row1.add_widget(b_rec)
        row1.add_widget(b_stop)
        row2 = BoxLayout(size_hint_y=None, height="50dp", spacing=8)
        b_play = RoundButton(text="Listen", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), bold=True, font_size="16sp")
        b_share = RoundButton(text="Share", bg=GREY, fg=TEXTCOL, bold=True, font_size="16sp")
        b_close = RoundButton(text="Close", bg=GREY, fg=TEXTCOL, bold=True, font_size="16sp")
        for b in (b_play, b_share, b_close):
            row2.add_widget(b)
        b_ai = RoundButton(text="AI sings it in my voice", bg=BLUE2, fg=TEXTCOL, bold=True, font_size="16sp",
                           size_hint_y=None, height="48dp")
        b_ai.bind(on_press=lambda *_: (st["mode"] == "ready") and (pop.dismiss(), self.ai_sing(wav)))
        box.add_widget(row1)
        box.add_widget(row2)
        box.add_widget(b_ai)
        pop = Popup(title="Genius vocal studio", content=box, size_hint=(0.97, 0.94), separator_color=GOLD,
                    title_color=GOLD)

        def tick(*_):
            m_track.pos, m_track.size = meter.pos, meter.size
            lv = rec.level if st["mode"] == "rec" else max(0.0, rec.level * 0.8)
            rec.level = lv if st["mode"] != "rec" else rec.level
            m_fill.pos, m_fill.size = meter.pos, (max(meter.height, meter.width * lv) if lv > 0.01 else 0, meter.height)
            m_col.rgba = (0.95, 0.3, 0.35, 1) if lv > 0.92 else (1, 0.78, 0.3, 1) if lv > 0.7 else (0.3, 0.9, 0.45, 1)
            p_track.pos, p_track.size = prog.pos, prog.size
            pos = time.time() - st["t0"] if st["mode"] in ("rec", "play") else 0.0
            p_fill.pos, p_fill.size = prog.pos, (prog.width * min(1.0, pos / max(0.1, dur)), prog.height)
            if st["mode"] == "rec":
                status.text = f"[color=ff4d5e]\u25cf REC[/color]  {_fmt_time(pos)} / {_fmt_time(dur)}" + \
                              ("   [color=ff4d5e]too loud, move back a little[/color]" if lv > 0.92 else "")
                status.markup = True
                if rec.error:
                    stop()
                    status.text = f"The microphone stopped: {rec.error}"
                    return
                if pos >= dur + 0.5:
                    stop()
                    return
            if st["mode"] in ("rec", "play"):
                idx = current_line(lines, pos)
                if idx != st["idx"]:
                    st["idx"] = idx
                    lyr.text = karaoke_markup(lines, idx)
                    if len(lines) > 1 and idx >= 0:
                        Animation.cancel_all(sv, "scroll_y")
                        Animation(scroll_y=max(0.0, min(1.0, 1 - idx / float(len(lines) - 1))), d=0.35).start(sv)
                if st["mode"] == "play" and not sound_playing() and pos > 1.5:
                    st["mode"] = "ready"
                    status.text = "Done. Listen again, Share it, or Record a new take."

        def record(*_):
            if st["mode"] in ("rec", "mix"):
                return
            sound_stop()
            take = os.path.join(genius_dl("music"), "vocals_" + time.strftime("%H%M%S") + ".wav")
            rec.start(take)
            if not _play_file(wav):
                rec.stop()
                status.text = "I couldn't play the beat. Try again."
                return
            st.update(mode="rec", t0=time.time(), take=take, idx=-2)
            b_rec.text = "\u25cf  Recording..."

        def stop(*_):
            if st["mode"] == "play":
                sound_stop()
                st["mode"] = "ready"
                status.text = "Stopped."
                return
            if st["mode"] != "rec":
                return
            sound_stop()
            st["mode"] = "mix"
            b_rec.text = "\u25cf  Record again"
            got = rec.stop()
            if not got:
                st["mode"] = "ready"
                status.text = "I didn't catch your voice. " + (rec.error or "Sing a bit longer and try again.")
                return
            status.markup = False
            status.text = "Mixing your voice with the beat..."
            out = os.path.splitext(wav)[0][:60] + "_my_voice_" + time.strftime("%H%M%S") + ".wav"

            def work():
                try:
                    res, err = mix_vocals(wav, got, out), None
                except MemoryError:
                    res, err = None, "The phone ran low on memory. Close other apps and try again."
                except Exception as e:
                    log(f"VOCAL mix failed: {e}")
                    res, err = None, "The mix didn't work. Record again."

                def done(*_):
                    st["mode"] = "ready"
                    if not res:
                        status.text = err
                        return
                    st["mixed"] = res
                    self._last_song = res
                    status.text = "Your song is ready. Tap Listen."
                    self.show("AI", f"[b]{_esc(meta.get('title', 'Your song'))} (my voice)[/b]\n"
                                    f"Your voice is now on the song. Saved in {nice_where(res)} as "
                                    f"{os.path.basename(res)}. Say 'play song' to hear it with the words.")
                Clock.schedule_once(done, 0)
            threading.Thread(target=work, daemon=True).start()

        def listen(*_):
            if st["mode"] in ("rec", "mix"):
                return
            target = st["mixed"]
            if not target:
                status.text = "Record your voice first, then tap Listen."
                return
            if _play_file(target):
                st.update(mode="play", t0=time.time(), idx=-2)
                status.markup = False
                status.text = "Playing your song..."

        def share(*_):
            if st["mixed"]:
                share_media(st["mixed"])
            else:
                status.text = "Record your voice first, then Share."

        def close(*_):
            if st["mode"] == "rec":
                rec.stop()
            sound_stop()
            pop.dismiss()

        b_rec.bind(on_press=record)
        b_stop.bind(on_press=stop)
        b_play.bind(on_press=listen)
        b_share.bind(on_press=share)
        b_close.bind(on_press=close)
        ev = Clock.schedule_interval(tick, 0.08)
        pop.bind(on_dismiss=lambda *_: (ev.cancel(), rec.running and rec.stop()))
        pop.open()
        tick()

    def ultra_photo(self, *_):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then say 'ultra'.")
            return
        if getattr(self, "busy", False):
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        self.say("Genius Ultra is working: HDR, true colour, clarity, fine detail...")

        def d(*_):
            try:
                out, msg = ultra_hd(src)
            except Exception as e:
                log(f"ULTRA failed: {e}")
                out, msg = None, "Ultra didn't work on this photo. Add it again with + and retry."

            def done(*_):
                self.busy = False
                if out:
                    remember_image(out, "Genius Ultra photo")
                    self.show_image(out, msg)
                else:
                    self.say(msg)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def zoom_photo_menu(self, *_):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then choose a zoom.")
            return
        self._buttons_popup("Zoom a photo", [(f"{z}x", lambda z=z: self._zoom_and_show(src, z), BLUE)
                                             for z in (2, 3, 5, 10, 20, 30, 50, 100)] +
                            [("AI super detail", self.ai_zoom, GOLD)], cols=2, hint="Zooms into the centre")

    def ai_zoom(self, *_):
        self.banana_quick("enhance this zoomed-in photo into a real high-resolution photo: recover fine sharp "
                          "detail and clean edges, remove blur, noise and blocky pixels, like a top phone camera's "
                          "AI super zoom. Do not add, remove or move anything")

    def banana_studio(self, *_):
        def setb(**k):
            BANANA.update(k)
            self.say(f"Banana: {'Pro (most realistic)' if BANANA['pro'] else 'normal (faster)'}, "
                     f"shape {BANANA['aspect'] or 'same as photo'}.")
            self.banana_studio()
        self._buttons_popup("Banana studio", [
            ("Edit my picture (type the change)", self.banana_edit_box, GOLD),
            ("Blend 2-4 photos into one", lambda: self.fun_pick("blend"), GOLD),
            ("Ultra realistic", lambda: self.banana_quick("make it ultra realistic: real camera photo, 4K detail, "
                                                          "natural skin texture, true colours, sharp focus"), BLUE),
            ("Fix hands and face", lambda: self.banana_quick("fix any wrong hands, fingers, eyes or face so they look "
                                                             "perfectly natural"), BLUE),
            ("Remove people behind", lambda: self.banana_quick("remove the other people and objects in the "
                                                               "background, keep the main person"), BLUE),
            ("Restore old photo", lambda: self.banana_quick("restore this old photo: remove scratches and blur, "
                                                            "add natural colour, sharp and clear"), BLUE),
            ("Pro mode ON (best)", lambda: setb(pro=True), GREY),
            ("Pro mode OFF (faster)", lambda: setb(pro=False), GREY),
            ("Shape: square 1:1", lambda: setb(aspect="1:1"), GREY),
            ("Shape: phone 9:16", lambda: setb(aspect="9:16"), GREY),
            ("Shape: wide 16:9", lambda: setb(aspect="16:9"), GREY),
            ("Shape: same as photo", lambda: setb(aspect=""), GREY)], cols=2,
            hint=f"Nano Banana{' Pro' if BANANA['pro'] else ''}  |  shape {BANANA['aspect'] or 'same'}")

    def banana_quick(self, instruction):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then use the Banana studio.")
            return
        remember_image(src, "photo to edit")
        self.do_edit(instruction + "." + KEEP)

    def banana_edit_box(self):
        if not self._edit_src():
            self.say("Add a photo with + first, then type your change.")
            return
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        ti = style_input(TextInput(hint_text="e.g. put me in a blue suit at Entebbe airport at sunset",
                                   font_size="17sp"))
        box.add_widget(ti)
        pop = Popup(title="Banana edit", content=box, size_hint=(0.94, 0.55),
                    separator_color=GOLD, title_color=GOLD)
        b = RoundButton(text="Make it", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None, height="52dp", bold=True)

        def go(*_):
            t = ti.text.strip()
            pop.dismiss()
            if t:
                self.banana_quick(t)
        b.bind(on_press=go)
        box.add_widget(b)
        pop.open()
        Clock.schedule_once(lambda *_: setattr(ti, "focus", True), 0.3)

    def banana_blend(self, paths):
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        ti = style_input(TextInput(hint_text="What should the new photo show? e.g. us two shaking hands at Kololo",
                                   font_size="17sp"))
        box.add_widget(ti)
        pop = Popup(title=f"Blend {len(paths)} photos", content=box, size_hint=(0.94, 0.55),
                    separator_color=GOLD, title_color=GOLD)
        b = RoundButton(text="Blend", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None, height="52dp", bold=True)

        def go(*_):
            t = ti.text.strip() or "these people standing together, smiling, in a nice place"
            pop.dismiss()
            self.busy = True
            self.say("Blending your photos with Nano Banana...")

            def d(*_):
                try:
                    out, err = blend_images(paths, t)
                except Exception as e:
                    log(f"BLEND failed: {e}")
                    out, err = None, "Blending didn't work. Choose the photos again and retry."

                def done(*_):
                    self.busy = False
                    if out:
                        remember_image(out, t)
                        self.show_image(out, t)
                        self.show("AI", IMAGE_TIPS)
                    else:
                        self.say(err or "Blending didn't work. Try again.")
                Clock.schedule_once(done, 0)
            threading.Thread(target=d, daemon=True).start()
        b.bind(on_press=go)
        box.add_widget(b)
        pop.open()

    def fun_videos(self):
        self._buttons_popup("Watch fun videos", [
            (t, lambda q=q: (open_url("https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)),
                             self.say("Opening " + q + " on YouTube. Enjoy!")), BLUE)
            for t, q in (("Funny animals", "funny animals compilation"),
                         ("Ugandan comedy", "Ugandan comedy skits"),
                         ("Amazing science", "amazing science experiments"),
                         ("Football skills", "best football skills and goals"),
                         ("Music videos", "latest Ugandan music videos"),
                         ("Magic tricks", "magic tricks revealed"),
                         ("Space and planets", "NASA space amazing videos"))])

    def fun_pick(self, job):
        """Let the person choose several pictures from the phone."""
        self._fun_job = job
        try:
            from jnius import autoclass
            from android import activity
            Intent = autoclass("android.content.Intent")
            PA = autoclass("org.kivy.android.PythonActivity")
            if not getattr(self, "_multi_bound", False):
                activity.bind(on_activity_result=self._on_multi_result)
                self._multi_bound = True
            it = Intent(Intent.ACTION_GET_CONTENT)
            it.setType("image/*")
            it.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
            it.addCategory(Intent.CATEGORY_OPENABLE)
            PA.mActivity.startActivityForResult(Intent.createChooser(it, "Choose pictures (hold to pick many)"),
                                                self.PICK_MULTI)
            self.say("Choose 2 to 12 pictures. Press and hold to pick more than one.")
        except Exception as e:
            log(f"MULTI PICK: {e}")
            self.fun_run(job, newest_photos(6))

    def _on_multi_result(self, request, result, intent):
        if request != self.PICK_MULTI:
            return
        paths = []
        try:
            if result == -1 and intent is not None:
                clip = intent.getClipData()
                if clip is not None:
                    for i in range(min(clip.getItemCount(), 12)):
                        paths.append(self._copy_uri(clip.getItemAt(i).getUri()))
                elif intent.getData() is not None:
                    paths.append(self._copy_uri(intent.getData()))
        except Exception as e:
            log(f"MULTI PICK error: {e}")
        job = getattr(self, "_fun_job", "collage")
        Clock.schedule_once(lambda *_: self.fun_run(job, paths) if paths else self.say("Okay, nothing chosen."), 0)

    def fun_run(self, job, paths):
        if len(paths) < 2:
            self.say("I need at least 2 pictures. Allow Genius to see photos, or choose them yourself.")
            return
        if job == "blend":
            self.banana_blend(paths[:4])
            return
        self.busy = True
        self.say("Making your " + ("collage" if job == "collage" else "video") + "...")

        def d(*_):
            try:
                if job == "collage":
                    out, msg = make_collage(paths)
                else:
                    vo = getattr(self, "_video_opts", {"seconds": 2, "effect": ""})
                    out, msg = make_slideshow(paths, vo["seconds"], vo["effect"])
            except ImportError:
                out, msg = None, "The picture tools aren't installed in this version."
            except Exception as e:
                log(f"FUN {job} failed: {e}")
                out, msg = None, "That didn't work with these pictures. Try choosing them again, or fewer pictures."

            def done(*_):
                self.busy = False
                if out:
                    remember_image(out, job)
                    self.show_image(out, msg)
                    self.say(msg + f" Saved in {nice_where(out)}." +
                             (" Say 'transform' to add an effect." if job == "collage" else ""))
                else:
                    self.say(msg)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def transform_menu(self, *_):
        src = LAST_IMAGE.get("path")
        if not src or not os.path.exists(src):
            ph = newest_photos(1)
            src = ph[0] if ph else None
        if not src:
            self.say("Add a picture first with +, then tap Transform.")
            return
        opts = [(st, lambda st=st: self.fun_transform(src, st), BLUE) for st in ("Beautify",) + FUN_STYLES]
        opts += [("AI: " + t, lambda ins=ins: (remember_image(src, "picture to transform"), self.do_edit(ins)), GOLD)
                 for t, ins in AI_STYLES]
        self._buttons_popup("Transform: " + os.path.basename(src)[:24], opts, cols=2,
                            hint="Blue = instant. Gold = AI (needs internet)")

    def fun_transform(self, src, style):
        if getattr(self, "busy", False):
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True

        def d(*_):
            try:
                if style.startswith("LOOK:"):
                    out, msg = pro_look(src, style[5:])
                elif style.startswith("EYE:"):
                    out, msg = genius_eye(src, style[4:])
                else:
                    out, msg = beautify(src) if style == "Beautify" else transform_image(src, style)
            except ImportError:
                out, msg = None, "The picture tools aren't installed in this version."
            except Exception as e:
                log(f"EFFECT {style} failed: {e}")
                out, msg = None, "That effect didn't work on this picture. Try another effect, or add the picture again with +."

            def done(*_):
                self.busy = False
                if out:
                    remember_image(out, style)
                    self.show_image(out, msg + " Say 'undo picture' to go back.")
                else:
                    self.say(msg)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def exit_app(self):
        log("EXIT by menu")
        self.say(f"Goodbye {CURRENT['name']}.")
        Clock.schedule_once(lambda *_: self.app.stop(), 1.5)

    def creation_files(self):
        found = []
        for d in (".", attach_dir(), genius_dl("fun"), genius_dl("pictures"), private_dir("pictures"),
                  private_dir("fun")):
            try:
                for n in os.listdir(d):
                    if n.lower().endswith(IMG_EXTS) and (n.startswith("drawing_") or d != "."):
                        found.append(os.path.abspath(os.path.join(d, n)))
            except Exception:
                pass
        found = [f for f in set(found) if os.path.exists(f)]
        return sorted(found, key=lambda f: os.path.getmtime(f), reverse=True)

    def creations(self, query=""):
        files = self.creation_files()
        if query:
            files = [f for f in files if query.lower() in os.path.basename(f).lower()] or files
        if not files:
            self.say("No creations yet. Tap Draw or say 'draw ...' to make your first picture.")
            return
        grid = GridLayout(cols=3, spacing=6, padding=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        sv = ScrollView()
        sv.add_widget(grid)
        box = BoxLayout(orientation="vertical", spacing=8, padding=8)
        box.add_widget(Label(text=f"{len(files)} pictures. Tap one to open it and change it.",
                             size_hint_y=None, height="30dp", color=HINT, font_size="14sp"))
        box.add_widget(sv)
        pop = Popup(title="My creations", content=box, size_hint=(0.96, 0.9),
                    separator_color=GOLD, title_color=GOLD)
        for f in files[:60]:
            b = Button(background_normal=f, background_down=f, size_hint_y=None, height="150dp")

            def open_it(btn, f=f):
                pop.dismiss()
                remember_image(f, "my earlier picture")
                self.show_image(f, os.path.basename(f) + "\nSay what to change, e.g. change it to night")
            b.bind(on_press=open_it)
            grid.add_widget(b)
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="48dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    # ---------- My storage: a small private space inside Genius ----------
    def storage_box(self, *_):
        files = storage_files()
        used = storage_used()
        limit = STORAGE_LIMIT_MB * 1024 * 1024
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        pop = Popup(title="My storage", content=box, size_hint=(0.96, 0.9),
                    separator_color=GOLD, title_color=GOLD)
        pct = int(used * 100 / limit) if limit else 0
        box.add_widget(Label(text=f"Used {nice_size(used)} of {STORAGE_LIMIT_MB} MB ({pct}%)  |  {len(files)} items",
                             size_hint_y=None, height="30dp", color=HINT, font_size="15sp"))
        row = BoxLayout(size_hint_y=None, height="50dp", spacing=8)
        for label, fn, col in (("+ Save file", lambda: self.storage_add(), BLUE),
                               ("Save last picture", lambda: self.storage_save_last(), GREY),
                               ("+ Note", lambda: self.storage_note_box(), GREY)):
            b = RoundButton(text=label, bg=col, fg=TEXTCOL, font_size="14sp", bold=True)

            def go(btn, fn=fn):
                pop.dismiss()
                Clock.schedule_once(lambda *_: fn(), 0.1)
            b.bind(on_press=go)
            row.add_widget(b)
        box.add_widget(row)
        grid = GridLayout(cols=1, spacing=6, padding=4, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        sv = ScrollView()
        sv.add_widget(grid)
        box.add_widget(sv)
        if not files:
            grid.add_widget(Label(text="Empty. Save pictures, files and notes here.",
                                  size_hint_y=None, height="60dp", color=HINT))
        for f in files[:100]:
            line = BoxLayout(size_hint_y=None, height="52dp", spacing=6)
            nm = os.path.basename(f)
            ob = RoundButton(text=(nm[:26] + "..." if len(nm) > 29 else nm) + "  " + nice_size(os.path.getsize(f)),
                             bg=GREY, fg=TEXTCOL, font_size="14sp")
            db = RoundButton(text="Delete", bg=RED, fg=TEXTCOL, font_size="14sp", size_hint_x=0.3)

            def open_it(btn, f=f):
                pop.dismiss()
                Clock.schedule_once(lambda *_: self.storage_open(f), 0.1)

            def del_it(btn, f=f):
                pop.dismiss()
                Clock.schedule_once(lambda *_: self.storage_delete(f), 0.1)
            ob.bind(on_press=open_it)
            db.bind(on_press=del_it)
            line.add_widget(ob)
            line.add_widget(db)
            grid.add_widget(line)
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None,
                            height="48dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    def storage_add(self):
        self._to_storage = True
        self.pick_file("*/*")

    def storage_save_last(self):
        p = LAST_IMAGE.get("path")
        if not p or not os.path.exists(p):
            self.say("There's no picture yet. Draw one or add one first.")
            return
        _, msg = storage_put(p)
        self.say(msg)

    def storage_note_box(self):
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        ti = style_input(TextInput(hint_text="Write your note...", font_size="17sp"))
        box.add_widget(ti)
        pop = Popup(title="New note", content=box, size_hint=(0.94, 0.6),
                    separator_color=GOLD, title_color=GOLD)
        b = RoundButton(text="Save", bg=BLUE, fg=TEXTCOL, size_hint_y=None, height="50dp", bold=True)

        def save(*_):
            t = ti.text.strip()
            pop.dismiss()
            if t:
                f = storage_note(t)
                self.say("Note saved to your storage as " + os.path.basename(f) + ".")
        b.bind(on_press=save)
        box.add_widget(b)
        pop.open()
        Clock.schedule_once(lambda *_: setattr(ti, "focus", True), 0.3)

    def storage_open(self, f):
        kind = file_kind(f)
        if kind == "text":
            try:
                txt = open(f, encoding="utf8", errors="ignore").read()
            except Exception:
                txt = ""
            self.show("AI", os.path.basename(f) + ":\n" + (txt[:3000] or "(empty)"))
            self.attached = {"path": f, "kind": kind}
        else:
            self.got_attachment(f)

    def storage_delete(self, f):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        box.add_widget(Label(text="Delete " + os.path.basename(f) + "?\nThis can't be undone.",
                             color=TEXTCOL, halign="center"))
        row = BoxLayout(size_hint_y=None, height="50dp", spacing=8)
        pop = Popup(title="Delete", content=box, size_hint=(0.85, 0.4),
                    separator_color=GOLD, title_color=GOLD)
        yes = RoundButton(text="Delete", bg=RED, fg=TEXTCOL, bold=True)
        no = RoundButton(text="Keep", bg=GREY, fg=TEXTCOL, bold=True)

        def do(*_):
            pop.dismiss()
            try:
                os.remove(f)
                if self.attached and self.attached.get("path") == f:
                    self.attached = None
                self.say("Deleted " + os.path.basename(f) + ".")
            except Exception:
                self.say("I couldn't delete that file.")
        yes.bind(on_press=do)
        no.bind(on_press=pop.dismiss)
        row.add_widget(no)
        row.add_widget(yes)
        box.add_widget(row)
        pop.open()

    def _all_tools(self):
        """Every Genius tool in one list, so the Search button can find them all."""
        return [("Share Genius", self.share_menu, GOLD), ("Privacy shield", lambda: self.handle("privacy"), GOLD),
                ("Save last picture to gallery", lambda: self.handle("save"), GOLD),
                ("Save last picture to files", lambda: self.handle("save to files"), BLUE),
                ("Private screen on", lambda: self.handle("private on"), BLUE),
                ("Private screen off", lambda: self.handle("private off"), GREY), ("Speak (talk to Genius)", self.speak_input, GOLD),
                ("World news", self.news_menu, GOLD), ("Trending on social media", lambda: self.show_news("social"), GOLD), ("UNEB practice", lambda: self.handle("uneb"), BLUE),
                ("Homework from a photo", lambda: self.say("Tap Add file, pick your homework photo, then type homework."), BLUE),
                ("Draw a picture", lambda: self.handle("draw"), BLUE), ("Add file or photo", self.attach_menu, BLUE),
                ("Photo studio", lambda: self.handle("studio"), BLUE), ("Make a song", lambda: self.handle("music"), BLUE),
                ("Weather", lambda: self.handle("weather"), GREY), ("Farming help", lambda: self.handle("farm"), GREY),
                ("Luganda mode on", lambda: self.handle("luganda on"), GREY),
                ("Luganda mode off", lambda: self.handle("luganda off"), GREY),
                ("Translate English / Luganda", lambda: self.handle("translate"), GREY),
                ("Budget planner", lambda: self.handle("budget"), GREY),
                ("Mobile money charges", lambda: self.handle("fee mtn send 50000"), GREY),
                ("Scam checker", lambda: self.handle("scam"), GREY), ("Money and savings", lambda: self.handle("money"), GREY),
                ("Wealth and markets", lambda: self.handle("wealth"), GREY), ("Study and exams", lambda: self.handle("study"), GREY),
                ("Quiz", lambda: self.handle("quiz"), GREY), ("Freelancing", lambda: self.handle("freelance"), GREY),
                ("Notes", lambda: self.handle("notes"), GREY), ("Locker (secrets)", lambda: self.handle("secrets"), GREY),
                ("What Genius remembers", lambda: self.handle("memory"), GREY),
                ("Deep thinking: " + ("on" if self.deep else "off"), self.toggle_deep, GREY),
                ("Data saver on", lambda: self.handle("datasaver on"), GREY),
                ("Data saver off", lambda: self.handle("datasaver off"), GREY),
                ("Fun studio (collage, effects, video)", self.fun_studio, GREY),
                ("My creations (pictures)", self.creations, GREY), ("My storage", self.storage_box, GREY),
                ("Genius everywhere (bubble, shortcuts)", lambda: self.handle("everywhere"), GREY),
                ("Profile", self.profile_drawer, GREY), ("Set up AI key", self.key_wizard, GOLD),
                ("Theme / look", lambda: self.handle("theme"), GREY), ("Update Genius", lambda: self.handle("update"), GREY),
                ("New in Genius 110", lambda: self.show("AI", V110_HELP), GREY),
                ("What's new", lambda: self.show("AI", CHANGELOG), GREY),
                ("Help (all commands)", lambda: self.handle("help"), GREY),
                ("Change secret code", lambda: self.handle("change code"), GREY),
                ("Accounts", self.accounts_box, GREY), ("Clear chat", self.clear_chat, GREY),
                ("Lock Genius", self.app.build_login, GREY), ("Exit Genius", self.exit_app, RED)]

    def search_box(self, *_):
        if getattr(self, "talking", False):
            return self.speak_input()          # tapping while listening stops it
        box = BoxLayout(orientation="vertical", spacing=8, padding=10)
        ti = style_input(TextInput(hint_text="Search tools, chats or the internet...", multiline=False,
                                   font_size="18sp", size_hint_y=None, height="52dp"))
        box.add_widget(ti)
        pop = Popup(title="Search", content=box, size_hint=(0.95, 0.94),
                    separator_color=GOLD, title_color=GOLD)
        sv = ScrollView()
        lst = BoxLayout(orientation="vertical", spacing=8, size_hint_y=None)
        lst.bind(minimum_height=lst.setter("height"))
        sv.add_widget(lst)
        box.add_widget(sv)
        tools = self._all_tools()

        def run(fn, *a):
            pop.dismiss()
            Clock.schedule_once(lambda *_: fn(*a), 0.1)

        def btn(label, col, on):
            b = RoundButton(text=label, bg=col, fg=(0.1, 0.1, 0.1, 1) if col == GOLD else TEXTCOL,
                            size_hint_y=None, height="50dp", font_size="16sp", bold=True)
            b.bind(on_press=lambda *_: on())
            lst.add_widget(b)

        def refresh(*_):
            q = ti.text.strip()
            ql = q.lower()
            lst.clear_widgets()
            if q:
                btn(f"Ask Genius: {q[:30]}", GOLD, lambda: run(self.handle, q))
                btn(f"Search the internet: {q[:24]}", BLUE, lambda: run(self.web_search, q))
                btn("Search my chats and notes", BLUE, lambda: run(self.search_mine, q))
                btn("Search my creations", BLUE, lambda: run(self.creations, q))
            words = ql.split()
            for label, fn, col in tools:
                if not words or all(w in label.lower() for w in words):
                    btn(label, col, lambda fn=fn: run(fn))
        ti.bind(text=refresh)
        ti.bind(on_text_validate=lambda *_: run(self.handle, ti.text.strip()) if ti.text.strip() else None)
        refresh()
        close = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_y=None, height="46dp", bold=True)
        close.bind(on_press=pop.dismiss)
        box.add_widget(close)
        pop.open()

    def search_mine(self, q):
        ql = q.lower()
        hits = []
        for m in history:
            for part in m.get("parts", []):
                t = part.get("text", "")
                if ql in t.lower():
                    i = t.lower().find(ql)
                    who = "You" if m.get("role") == "user" else "Genius"
                    hits.append(f"{who}: ..." + t[max(0, i - 60): i + 100].replace("\n", " ") + "...")
        for fname, label in ((NOTES_FILE, "Note"), (LOG_FILE, "Log")):
            try:
                for line in open(fname, encoding="utf8", errors="ignore"):
                    if ql in line.lower():
                        hits.append(f"{label}: " + line.strip()[:160])
            except Exception:
                pass
        if hits:
            self.show("AI", f"Found '{q}' {len(hits)} time(s):\n" + "\n".join(hits[-15:]))
        else:
            self.say(f"I couldn't find '{q}' in your chats or notes. Try 'Search the internet'.")

    def web_search(self, q):
        self.busy = True
        self.say("Searching the internet...")

        def d(*_):
            try:
                r = ask_gemini("Search the internet and answer briefly with the key facts: " + q, 700, search=True)
            except Exception as e:
                log(f"WEB search failed: {e}")
                r = None

            def done(*_):
                self.busy = False
                self.say(r or "The search didn't work. Check your internet, or add an AI key with setkey.")
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    # ---------- + button: add pictures and files ----------
    PICK_CODE = 7780

    def attach_menu(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        pop = Popup(title="Add to Genius", content=box, size_hint=(0.9, 0.62),
                    separator_color=GOLD, title_color=GOLD)
        pop.size_hint = (0.9, 0.82)
        opts = [("Take a photo (camera)", self.take_photo, GOLD),
                ("Gallery: photos and screenshots", self.pick_gallery, BLUE),
                ("My newest screenshot", self.attach_screenshot, BLUE),
                ("A file (PDF, notes, text...)", lambda: self.pick_file("*/*"), BLUE),
                ("My newest photo", lambda: self.attach_newest(True), GREY),
                ("Cancel", None, RED)]
        for label, fn, col in opts:
            b = RoundButton(text=label, bg=col, fg=TEXTCOL, size_hint_y=None, height="54dp",
                            font_size="17sp", bold=True)

            def go(btn, fn=fn):
                pop.dismiss()
                if fn:
                    fn()
            b.bind(on_press=go)
            box.add_widget(b)
        pop.open()

    CAM_CODE = 7781

    def take_photo(self, *_, front=False, eye=False):
        """Open the phone's camera (front for selfies); the photo comes straight back into the chat.
        eye=True: Genius Eye beautifies it automatically."""
        self._cam_front = bool(front)
        self._cam_eye = bool(eye)
        try:
            from android.permissions import request_permissions, check_permission, Permission
            need = [Permission.CAMERA]
            if android_sdk() < 29:
                need.append(Permission.WRITE_EXTERNAL_STORAGE)
            if all(check_permission(p) for p in need):
                self._launch_camera()
                return

            def after(perms, grants):
                if grants and all(grants):
                    Clock.schedule_once(lambda *_: self._launch_camera(), 0.2)
                else:
                    Clock.schedule_once(lambda *_: self.say(
                        "Genius needs the camera to take a photo. Tap + again and allow Camera, "
                        "or choose a picture from your gallery."), 0)
            request_permissions(need, after)
        except Exception as e:
            log(f"CAM perm: {e}")
            self.say("The camera isn't available here. Tap + and choose a picture from your gallery.")

    def _launch_camera(self):
        try:
            from jnius import autoclass, cast
            from android import activity
            Intent = autoclass("android.content.Intent")
            MediaStore = autoclass("android.provider.MediaStore")
            ContentValues = autoclass("android.content.ContentValues")
            PA = autoclass("org.kivy.android.PythonActivity")
            cr = PA.mActivity.getContentResolver()
            cv = ContentValues()
            cv.put("_display_name", f"Genius_{int(time.time())}.jpg")
            cv.put("mime_type", "image/jpeg")
            if android_sdk() >= 29:
                cv.put("relative_path", "Pictures/Genius")
            uri = cr.insert(autoclass("android.provider.MediaStore$Images$Media").EXTERNAL_CONTENT_URI, cv)
            if not getattr(self, "_cam_bound", False):
                activity.bind(on_activity_result=self._on_cam_result)
                self._cam_bound = True
            it = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            it.putExtra(MediaStore.EXTRA_OUTPUT, cast("android.os.Parcelable", uri))
            if getattr(self, "_cam_front", False):        # ask for the selfie camera (most phone cameras obey)
                it.putExtra("android.intent.extras.CAMERA_FACING", 1)
                it.putExtra("android.intent.extras.LENS_FACING_FRONT", 1)
                it.putExtra("android.intent.extra.USE_FRONT_CAMERA", True)
                it.putExtra("com.google.assistant.extra.USE_FRONT_CAMERA", True)
            it.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION)
            self._cam_uri = uri
            PA.mActivity.startActivityForResult(it, self.CAM_CODE)
        except Exception as e:
            log(f"CAM launch: {e}")
            self.say("I couldn't open the camera. Tap + and choose a picture from your gallery instead.")

    def _on_cam_result(self, request, result, intent):
        if request != self.CAM_CODE:
            return
        uri, self._cam_uri = getattr(self, "_cam_uri", None), None
        path = None
        try:
            if result == -1 and uri is not None:
                path = self._copy_uri(uri)
            elif uri is not None:
                from jnius import autoclass
                autoclass("org.kivy.android.PythonActivity").mActivity.getContentResolver().delete(uri, None, None)
        except Exception as e:
            log(f"CAM result: {e}")
        if path and os.path.getsize(path) > 0:
            eye, self._cam_eye = getattr(self, "_cam_eye", False), False
            if getattr(self, "_to_profile", False):
                self._to_profile = False
                Clock.schedule_once(lambda *_: self._apply_profile(path, beauty=eye), 0)
                return

            def show(*_):
                self.got_attachment(path)
                if eye:
                    remember_image(path, "camera")
                    self.fun_transform(path, "EYE:natural")
                    self._show_suggestions([("Glam beauty", "word:glam beauty"), ("Portrait blur", "word:portrait blur"),
                                            ("Add effects", "word:effects")])
                    return
                self._show_suggestions([("Genius Eye beauty", "word:eye beauty"), ("Add effects", "word:effects"),
                                        ("Homework", "word:homework")])
            Clock.schedule_once(show, 0)
        else:
            self._to_profile = False
            Clock.schedule_once(lambda *_: self.say("Okay, no photo taken."), 0)

    def pick_gallery(self, *_):
        """The phone's Gallery, where photos and screenshots are (no extra permission needed)."""
        try:
            from jnius import autoclass
            from android import activity
            Intent = autoclass("android.content.Intent")
            MediaStore = autoclass("android.provider.MediaStore")
            PA = autoclass("org.kivy.android.PythonActivity")
            if not getattr(self, "_pick_bound", False):
                activity.bind(on_activity_result=self._on_pick_result)
                self._pick_bound = True
            it = Intent(Intent.ACTION_PICK, autoclass("android.provider.MediaStore$Images$Media").EXTERNAL_CONTENT_URI)
            it.setType("image/*")
            PA.mActivity.startActivityForResult(it, self.PICK_CODE)
        except Exception as e:
            log(f"GALLERY: {e}")
            self.pick_file("image/*")

    def attach_screenshot(self, *_):
        self._storage_permission()
        best, bt = None, 0
        for d in ("/storage/emulated/0/Pictures/Screenshots", "/storage/emulated/0/DCIM/Screenshots",
                  "/storage/emulated/0/Screenshots"):
            try:
                for n in os.listdir(d):
                    f = os.path.join(d, n)
                    if os.path.isfile(f) and file_kind(f) == "image" and os.path.getmtime(f) > bt:
                        best, bt = f, os.path.getmtime(f)
            except Exception:
                continue
        if best:
            self.got_attachment(best)
        else:
            self.say("I couldn't see your screenshots yet. Opening your gallery so you can pick one.")
            self.pick_gallery()

    def _storage_permission(self):
        try:
            from android.permissions import request_permissions, Permission
            perms = [Permission.READ_EXTERNAL_STORAGE]
            for n in ("READ_MEDIA_IMAGES",):
                if hasattr(Permission, n):
                    perms.append(getattr(Permission, n))
            request_permissions(perms)
        except Exception:
            pass

    def attach_newest(self, images_only):
        self._storage_permission()
        f = newest_file(images_only)
        if not f:
            self.say("I couldn't see your files yet. Allow Genius to see photos, or tap + and Choose instead.")
            return
        self.got_attachment(f)

    def pick_file(self, mime):
        """Open Android's own file picker (no extra permission needed)."""
        try:
            from jnius import autoclass
            from android import activity
            Intent = autoclass("android.content.Intent")
            PA = autoclass("org.kivy.android.PythonActivity")
            if not getattr(self, "_pick_bound", False):
                activity.bind(on_activity_result=self._on_pick_result)
                self._pick_bound = True
            it = Intent(Intent.ACTION_GET_CONTENT)
            it.setType(mime)
            it.addCategory(Intent.CATEGORY_OPENABLE)
            PA.mActivity.startActivityForResult(Intent.createChooser(it, "Add to Genius"), self.PICK_CODE)
        except Exception as e:
            log(f"PICK: no Android picker ({e})")
            self.attach_newest(mime.startswith("image"))

    def _on_pick_result(self, request, result, intent):
        if request != self.PICK_CODE:
            return
        path, err = None, None
        try:
            if result == -1 and intent is not None and intent.getData() is not None:
                path = self._copy_uri(intent.getData())
            else:
                err = "Okay, nothing added."
        except Exception as e:
            err = "I couldn't open that file. Try another one."
            log(f"PICK error: {e}")
        if path and getattr(self, "_chart_mode", False):
            self._chart_mode = False
            Clock.schedule_once(lambda *_: self.chart_read(path), 0)
            return
        self._chart_mode = False
        to_prof, self._to_profile = getattr(self, "_to_profile", False), False
        if path and to_prof:
            Clock.schedule_once(lambda *_: self._apply_profile(path), 0)
            return
        to_store = getattr(self, "_to_storage", False)
        self._to_storage = False
        if path and to_store:
            def store(*_):
                newp, msg = storage_put(path, move=True)
                self.say(msg)
            Clock.schedule_once(store, 0)
            return
        Clock.schedule_once(lambda *_: self.got_attachment(path) if path else self.say(err), 0)

    def _copy_uri(self, uri):
        """Copy the picked file into Download/Genius/attached and return its path."""
        from jnius import autoclass
        PA = autoclass("org.kivy.android.PythonActivity")
        cr = PA.mActivity.getContentResolver()
        name, mime = "", cr.getType(uri) or ""
        try:
            OC = autoclass("android.provider.OpenableColumns")
            cur = cr.query(uri, None, None, None, None)
            if cur is not None:
                if cur.moveToFirst():
                    name = cur.getString(cur.getColumnIndex(OC.DISPLAY_NAME)) or ""
                cur.close()
        except Exception:
            pass
        name = re.sub(r"[^\w.\-]+", "_", name) or ("file_" + str(int(time.time())))
        if "." not in name:
            name += {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp",
                     "application/pdf": ".pdf", "text/plain": ".txt"}.get(mime, "")
        dest = os.path.join(attach_dir(), str(int(time.time())) + "_" + name)
        stream = cr.openInputStream(uri)
        try:
            buf = bytearray(65536)
            with open(dest, "wb") as out:
                while True:
                    n = stream.read(buf)
                    if n is None or n < 0:
                        break
                    out.write(bytes(buf[:n]))
        finally:
            stream.close()
        if os.path.getsize(dest) == 0:
            try:
                Files = autoclass("java.nio.file.Files")
                JFile = autoclass("java.io.File")
                os.remove(dest)
                Files.copy(cr.openInputStream(uri), JFile(dest).toPath())
            except Exception as e:
                log(f"PICK copy fallback failed: {e}")
        return dest

    def got_attachment(self, path):
        kind = file_kind(path)
        self.attached = {"path": path, "kind": kind}
        name = os.path.basename(path)
        if kind == "image":
            remember_image(path, "the attached photo")
            self.show_image(path, "Added " + name)
            self.say("Picture added. Ask me about it, or change it, e.g. 'make me near a building' "
                     "or 'change it to night'. Say 'keep this face' to save it as your face.")
        elif kind in ("pdf", "text"):
            self.say(f"Added {name}. Ask me anything about it, or say 'summarize'.")
        else:
            self.attached = None
            self.say("I can read pictures, PDFs and text files. That type isn't supported yet.")

    def file_question(self, question):
        a = self.attached
        self.busy = True
        self.say("Reading your " + ("picture" if a["kind"] == "image" else "file") + "...")

        def d(*_):
            try:
                r = ask_about_file(a["path"], a["kind"], question)
            except Exception as e:
                log(f"FILE question failed: {e}")
                r = None
            r = r or "I couldn't read that file right now. Check your internet, or add the file again with +."
            history.append({"role": "user", "parts": [{"text": "[About " + os.path.basename(a["path"]) + "] " + question}]})
            history.append({"role": "model", "parts": [{"text": r}]})
            try:
                save_memory()
            except Exception:
                pass

            def done(*_):
                self.busy = False
                self.say(r)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def do_edit(self, instruction):
        self.busy = True
        self.say("Changing your picture... this takes a moment.")

        def d(*_):
            try:
                path, note = edit_image(instruction)
            except Exception as e:
                log(f"EDIT failed: {e}")
                path, note = None, "I couldn't change the picture this time. Check your internet and try again."

            def done(*_):
                self.busy = False
                if path:
                    remember_image(path, LAST_IMAGE["prompt"] + ", " + instruction)
                    self.show_image(path, instruction)
                    self.say(note or "Here it is.")
                    self.show("AI", IMAGE_TIPS)
                else:
                    self.say(note)
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def show_image(self, path, caption):
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda *_: self.show_image(path, caption), 0)
            return
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        if not path or not os.path.exists(path):
            self.say("I made it, but couldn't find the picture file. Please try once more.")
            return
        box.add_widget(KivyImage(source=path, allow_stretch=True, keep_ratio=True, nocache=True))
        box.add_widget(Label(text=f"{caption}\nSaved in {nice_where(path)}",
                             size_hint_y=None, height="72dp", font_size="15sp", color=TEXTCOL,
                             halign="center", valign="middle", text_size=(Window.width * 0.85, None)))
        acts = BoxLayout(size_hint_y=None, height="52dp", spacing=6)
        for label, where, col in (("Save to gallery", "gallery", GOLD), ("Save to files", "files", BLUE),
                                  ("Share", "share", BLUE)):
            b = RoundButton(text=label, bg=col, fg=(0.1, 0.1, 0.1, 1) if col == GOLD else TEXTCOL,
                            font_size="14sp", bold=True)

            def act(_b, where=where):
                if where == "share":
                    if not share_media(path):
                        self.say("Sharing didn't open. Save it to your gallery, then share it from there.")
                    return
                _u, msg = save_media(path, where)
                _b.text = "Saved" if _u is not None else _b.text
                self.say(msg)
            b.bind(on_press=act)
            acts.add_widget(b)
        box.add_widget(acts)
        btn = RoundButton(text="Close", bg=GREY, fg=TEXTCOL,
                          size_hint_y=None, height="48dp", bold=True)
        box.add_widget(btn)
        pop = Popup(title="Your picture", content=box, size_hint=(0.95, 0.9),
                    separator_color=GOLD, title_color=GOLD)
        btn.bind(on_press=pop.dismiss)
        pop.open()

    # output
    def show(self, who, text, plain=False):
        if threading.current_thread() is not threading.main_thread():   # 111.7: screen work only on the main thread
            Clock.schedule_once(lambda *_: self.show(who, text, plain), 0)
            return
        if who == "AI" and isinstance(text, str) and not plain:
            text = colorize(md_to_markup(text))
        if who == "AI" and getattr(self, "_rate_next", False):
            self._rate_next = False
            text += ("\n[size=13sp][ref=like][color=7ee787][u]Good answer[/u][/color][/ref]     "
                     "[ref=dislike][color=ff8a8a][u]Bad answer[/u][/color][/ref][/size]")
        if who == "AI" and CURRENT.get("owner") and isinstance(text, str) and _needs_key_text(text):
            text += "\n[ref=keywizard][b][color=ffc84d][u]\u00bb Tap here to set up a free AI key[/u][/color][/b][/ref]"
            if text.startswith(NO_AI_MSG[:40]):
                Clock.schedule_once(self.offer_key_wizard, 0.3)
        if who == "AI":
            head = self._ai_head()
        else:
            head = f"[b]{gradient_word(who, PAL['user'], PAL['accent2']) if who == 'You' else _esc(who)}[/b]"
            text = f"[color={_hx(PAL['text'])}]{_esc(text)}[/color]"     # your words exactly as typed, never highlighted
        self.out.text += f"{head}\n{text}\n[size=6sp] [/size]\n"
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.1)

    def _ai_head(self):
        return f"[b]{gradient_word('Genius', PAL['accent'], PAL['accent2'])}[/b]"

    # ---- streaming: the answer types itself out as it arrives ----
    def _stream_begin(self, placeholder):
        self.show("AI", placeholder)
        self._stream_head = self._ai_head()
        self._stream_tail = colorize(md_to_markup(placeholder)) + "\n[size=6sp] [/size]\n"
        self._stream_buf, self._stream_shown = "", ""
        self._stream_ev = Clock.schedule_interval(self._stream_paint, 0.12)

    def _stream_feed(self, txt):          # called from the worker thread; painting happens on the UI clock
        self._stream_buf = txt

    def _stream_paint(self, *_):
        buf = getattr(self, "_stream_buf", "")
        if not buf or buf == self._stream_shown or not self.out.text.endswith(self._stream_tail):
            return
        self._stream_shown = buf
        shown = re.sub(r"(?m)^\s*Ask next:.*$", "", buf).rstrip()
        try:
            body = colorize(md_to_markup(shown))
        except Exception:
            body = _esc(shown)
        tail = body + "\n[size=6sp] [/size]\n"
        self.out.text = self.out.text[:-len(self._stream_tail)] + tail
        self._stream_tail = tail
        self.scroll.scroll_y = 0

    def _stream_end(self):
        ev = getattr(self, "_stream_ev", None)
        if ev is not None:
            ev.cancel()
        self._stream_ev = None
        whole = getattr(self, "_stream_head", "") + "\n" + getattr(self, "_stream_tail", "")
        if self._stream_tail and self.out.text.endswith(whole):
            self.out.text = self.out.text[:-len(whole)]     # the finished answer replaces the live one
        self._stream_tail = ""

    CHAT_MAX_PX = 3400          # phone GPUs can't draw one text picture taller than ~4096 px: it turns black
    _CHAT_SEP = "\n[size=6sp] [/size]\n"
    _CHAT_OLD = "[size=12sp][i]Older messages are hidden to keep the chat clear.[/i][/size]" + "\n[size=6sp] [/size]\n"

    def _chat_size(self, lbl, size):
        """Keep the chat readable: when the text gets too tall for the phone to draw (it would show
        as a black box), drop the oldest messages, never the newest one."""
        if size[1] > self.CHAT_MAX_PX:
            body = lbl.text.replace(self._CHAT_OLD, "", 1)
            msgs = [m for m in body.split(self._CHAT_SEP) if m.strip()]
            if len(msgs) > 1:
                keep = max(1, int(len(msgs) * min(0.6, self.CHAT_MAX_PX * 0.6 / size[1])))
                lbl.text = self._CHAT_OLD + self._CHAT_SEP.join(msgs[-keep:]) + self._CHAT_SEP
                return
            if len(body) > 4000:          # one huge message: show its end
                lbl.text = self._CHAT_OLD + "..." + body[-3500:]
                return
        lbl.height = size[1]

    def say(self, text, plain=False):
        if threading.current_thread() is not threading.main_thread():
            Clock.schedule_once(lambda *_: self.say(text, plain), 0)
            return
        follow = []
        if isinstance(text, str) and not plain:
            text, follow = split_follow_ups(text)
        self.show("AI", text, plain=plain)
        if follow:
            Clock.schedule_once(lambda *_: self._show_suggestions([(q, "word:" + q) for q in follow]), 0.2)
        self._last_said = text
        q = getattr(self, "_pending_q", "")
        if q and text and len(text) > 30 and not text.startswith(("Still ", "Say it like")):
            self._pending_q = ""
            if LAST_QA.get("q") != q or LAST_QA.get("a") != text:
                LAST_QA.update(q=q, a=text)
                brain_reflect(q, text)          # every question makes the brain a little smarter
        tts(re.sub(r"(?m)^Sources: .*$", "", re.sub(r"[*#]+", "", text)) if isinstance(text, str) else text)
        if getattr(self, "talking", False):
            self.listen_after_speech()

    def send(self, *_):
        text = self.inp.text.strip()
        self.inp.text = ""
        self._show_suggestions([])
        if text:
            try:
                learn_words(text)
            except Exception as e:
                log(f"WORDS learn failed: {e}")
            self.handle(text)

    # ---------- typing: growing box + command suggestions ----------
    def _kb_focus(self, _ti, focused):
        if self._kb_ev is not None:
            self._kb_ev.cancel()
            self._kb_ev = None
        if focused:
            self._kb_ev = Clock.schedule_interval(self._kb_check, 0.15)
        self._typing_mode(focused)
        Clock.schedule_once(self._kb_check, 0.05)
        Clock.schedule_once(self._kb_check, 0.4)

    def _typing_mode(self, on):
        """While typing: hide the top bar and make Genius's words smaller, so there's room to see yours."""
        hd = getattr(self, "header", None)
        if hd is not None:
            hd.height = 0 if on else dp(60)
            hd.opacity = 0 if on else 1
            hd.disabled = bool(on)
        self.out.font_size = "14sp" if on else "18sp"
        if getattr(self, "chat_outer", None) is not None:
            self.chat_outer.padding = [6, 4, 6, 2] if on else [10, 10, 10, 8]
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.1)

    def _kb_check(self, *_):
        h = keyboard_overlap() if self.inp.focus else 0
        if not h and not ANDROID_OK() and self.inp.focus:
            h = int(getattr(Window, "keyboard_height", 0) or 0)
        if abs(self.kb_pad.height - h) > 2:
            opening = h > self.kb_pad.height
            self.kb_pad.height = h
            if opening:      # keep the newest message in view, just above the box
                Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.05)

    def _grow_input(self, *_):
        ti = self.inp
        pad = ti.padding[1] + ti.padding[3] if len(ti.padding) == 4 else 2 * ti.padding[-1]
        one = ti.line_height + pad
        four = ti.line_height * 6 + ti.line_spacing * 5 + pad   # grows to 6 lines so you see all your words
        h = max(one, min(four, ti.minimum_height))
        if abs(ti.height - h) > 0.5:
            ti.height = h
        self.in_row.height = h + dp(14)

    def _typing(self, _ti, text):
        if self._sugg_ev is not None:
            self._sugg_ev.cancel()
        self._sugg_ev = Clock.schedule_once(lambda *_: self._show_suggestions(
            suggest_commands(self.inp.text) or suggest_words(self.inp.text)), 0.15)

    def _show_suggestions(self, items):
        row = self.sugg_row
        row.clear_widgets()
        if not items:
            self.sugg_sv.height, self.sugg_sv.opacity = 0, 0
            return
        cols = PAL["chip"]
        for i, (fill, hint) in enumerate(items):
            col = cols[i % len(cols)]
            dark = col[3] == 1 and _lum(col) > 0.45
            fg = (0.08, 0.07, 0.05, 1) if dark else TEXTCOL
            label = fill.strip()
            if hint.startswith("word:"):
                label = _esc(hint[5:])
            elif hint.startswith("Luganda for "):
                label += f"  [size=11sp]{_esc(hint[12:])}[/size]"
            b = RoundButton(text=label, bg=col, fg=fg, markup=True, size_hint_x=None, font_size="14sp", bold=True,
                            width=dp(22) + dp(8.2) * len(re.sub(r"\[[^\]]*\]", "", label)))

            def pick(_b, fill=fill):
                self.inp.text = fill
                self.inp.cursor = (len(fill), 0)
                self.inp.focus = True
                if not fill.endswith(" "):
                    self._show_suggestions([])
            b.bind(on_press=pick)
            row.add_widget(b)
        self.sugg_sv.height, self.sugg_sv.opacity = dp(40), 1

    # brain
    def handle(self, line):
        low = line.lower()
        if not low.startswith(("setkey", "save ", "setvoice", "setgroq", "setrouter", "setpolli", "seteleven", "setsunbird", "better:",
                               "correct:", "actually:", "wrong:", "teach")):
            self._pending_q = line
        if low.strip(" .!?") in ("mic test", "test mic", "test microphone", "microphone test"):
            self.mic_test()
            return
        if (low.startswith(("setkey", "setvoice", "setgroq", "setrouter", "setpolli", "seteleven"))
                or (low.startswith("save ") and low.strip(" .!?") not in SAVE_PHRASES)):
            head = line.split()[0]
            self.show("You", f"{head} ********")
        elif getattr(self, "_quiet_echo", False):
            self._quiet_echo = False
        else:
            self.show("You", line)
        if is_crisis(line):
            log("SAFETY: crisis words detected")
            self.show("AI", HELPLINES)
        action, _, arg = line.partition(" ")
        action, arg = action.lower(), arg.strip()
        action = LUGANDA_CMDS.get(action, action)
        action = {"whatsnew": "version", "changelog": "version", "updates": "update", "getupdate": "update"}.get(action, action)
        _alias = {"ai status": "ais", "my ai": "ais", "my ais": "ais", "which ai": "ais", "connected ais": "ais",
                  "what can you do": "help", "commands": "help", "show commands": "help", "menu": "help"}
        if low.strip(" .!?") in _alias:
            action, arg = _alias[low.strip(" .!?")], ""
            line = low = action
        # Typo-tolerant commands: "itruders" -> "intruders" (short inputs only)
        if action not in ALLOWED and action.isalpha() and len(action) >= 5 and not arg \
                and action not in COMMON_WORDS and not action.startswith("set"):
            import difflib
            names = [k for k in ALLOWED if k.isalpha() and len(k) >= 4 and not k.startswith("set")]
            near = [n for n in difflib.get_close_matches(action, names, n=1, cutoff=0.85)
                    if abs(len(n) - len(action)) <= 2]
            if near:
                self.show("AI", f"I took '{action}' as '{near[0]}'.")
                action = near[0]
                line = (near[0] + " " + arg).strip()
                low = line.lower()

        try:
            if v110_handle(self, line, action, arg, low):
                return
        except Exception as e:
            log(f"V110 command failed: {type(e).__name__}: {e}")
        # Genius Brain: it learns and improves itself
        lw = low.strip(" .!?")
        if action in ("do", "agent", "job", "run") and not arg and lw in ("do", "agent", "job", "run"):
            self.say("Tell me the job, e.g. do compare 3 phones under 800k. "
                     "For a skill you taught, say run and its name (see skillbook).")
            return
        if action == "speak" and not arg:
            self.speak_input()
            return
        if action == "clear" and not arg:
            self.clear_chat()
            return
        if action in ("do", "agent", "job") and arg:
            self._bg(lambda: genius_agent(arg), "Genius Agent is planning and doing your job step by step...",
                     speak=False)
            return
        if low.startswith("teach skill "):
            name, _, steps = line[12:].partition(":")
            name = name.strip().lower()
            st = [x.strip() for x in re.split(r";|\n|,? then ", steps) if x.strip()]
            if not name or not st:
                self.say("Say it like: teach skill news: find today's Uganda news; pick the top 5; explain each simply")
                return
            d = skillbook_load()
            d[name] = st
            skillbook_save(d)
            self.say(f"Learned the skill '{name}' ({len(st)} steps). Say 'run {name}' any time.")
            return
        if action == "run" and arg:
            d = skillbook_load()
            nm, _, extra = arg.partition(" for ")
            st = d.get(nm.strip().lower())
            if not st:
                have = ", ".join(d) or "none yet"
                self.say(f"I don't know the skill '{nm}'. My skills: {have}.")
                return
            task = nm + (" for " + extra if extra else "")
            self._bg(lambda: genius_agent(task, st), f"Running your skill '{nm}'...", speak=False)
            return
        if lw in ("skillbook", "my genius skills", "genius skills"):
            d = skillbook_load()
            self.say("Skills I've learned:\n" + "\n".join(f"- {k}: {' > '.join(v)}" for k, v in d.items())
                     if d else "No skills yet. Teach one: teach skill <name>: step one; step two")
            return
        if lw in ("self review", "review yourself", "improve yourself", "upgrade yourself"):
            self._bg(lambda: brain_self_review(force=True), "Studying my lessons and sharpening them...", speak=False)
            return
        if action in ("teach", "learn", "remember:") and arg:
            brain_add(arg, kind="correction", score=3)
            self.say("Learned. I'll use that from now on.")
            return
        if low.startswith(("better:", "correct:", "actually:", "wrong:")):
            fix = line.split(":", 1)[1].strip()
            if LAST_QA["q"] and fix:
                brain_add(f"For '{LAST_QA['q'][:120]}': {fix}", q=LAST_QA["q"], kind="correction", score=3)
                _answer_cache.pop(LAST_QA["q"].strip().lower(), None)
                self.say("Thanks, I've corrected myself. Next time I'll answer it the better way.")
            else:
                self.say("Tell me what to fix, like 'better: the capital is Kampala'.")
            return
        if lw in ("good", "good answer", "perfect", "correct", "thanks genius", "👍"):
            if LAST_QA["q"]:
                brain_add(f"This kind of answer worked well for '{LAST_QA['q'][:120]}': keep the same style.",
                          q=LAST_QA["q"], score=1)
            self.say("Noted. I'll keep answering like that.")
            return
        if lw in ("bad", "bad answer", "wrong", "not good", "👎"):
            if LAST_QA["q"]:
                _answer_cache.pop(LAST_QA["q"].strip().lower(), None)
                brain_add(f"My answer to '{LAST_QA['q'][:120]}' was not good. Answer it more carefully and check facts.",
                          q=LAST_QA["q"], score=1)
            self.say("Sorry. Tell me the right answer with 'better: ...' and I'll learn it, or ask again and I'll think harder.")
            return
        if lw in ("what have you learned", "what did you learn", "brain", "my brain", "lessons", "your lessons"):
            self.say(brain_report())
            return
        if lw in ("forget lessons", "reset brain", "clear brain"):
            brain_save([])
            self.say("Done. My learned lessons are cleared.")
            return

        # picture follow-ups, like Gemini: "make me near building" edits the last picture
        if low.strip(" .!") in ("setme", "set me", "this is me", "use this face", "keep this face", "save my face"):
            src = LAST_IMAGE["path"] if low.strip(" .!") in ("use this face", "keep this face") else None
            f = set_my_photo(src)
            self.say("Saved your face. Now say 'make me ...' and every picture keeps it." if f
                     else "I couldn't find a photo. Take a clear selfie first, then say setme.")
            return
        if not CURRENT["owner"] and (action in OWNER_ONLY or low.startswith(("setkey", "setgroq", "setrouter", "setpolli", "seteleven", "setvoice", "setsunbird"))):
            self.say("Only the owner of this phone can do that.")
            return
        if action in KEY_WIZARD_WORDS and (not arg or arg.lower() in KEY_WIZARD_INFO
                                           or arg.lower() in ("google", "openrouter", "router", "ai key", "key")):
            want = {"google": "gemini", "router": "openrouter"}.get(arg.lower(), arg.lower())
            self.key_wizard(want if want in KEY_WIZARD_INFO else None)
            return
        lw = low.strip(" .!")
        # Free access to the phone's apps: owner only, never other users
        # 'open wifi' shows a locked secret when one is saved under that name (vault before apps)
        if action == "open" and arg and vault_get(arg) is not None:
            self.run(line, "open", arg)
            return
        if lw in ("apps", "my phone apps", "phone apps", "list apps") or (
                lw.startswith(("open ", "launch ", "start ")) and lw not in ("start fresh", "open storage",
                                                                             "open camera")):
            if not CURRENT["owner"]:
                self.say("Only the owner of this phone can open its apps through Genius.")
                return
            if lw.startswith(("open ", "launch ", "start ")):
                target = lw.split(" ", 1)[1].strip()
                if target and target not in ("camera", "music", "studio"):
                    try:
                        label, pkg = find_phone_app(target)
                        if pkg and open_phone_app(pkg):
                            self.say(f"Opening {label}.")
                        else:
                            self.say(f"I couldn't find an app called {target}. Say apps to see them all.")
                    except Exception as e:
                        log(f"OPEN app failed: {e}")
                        self.say(f"I couldn't open {target} just now. Say apps to see what's installed.")
                    return
            else:
                try:
                    names = sorted(phone_apps(refresh=True), key=str.lower)
                    self.say(f"You have {len(names)} apps. Say open and a name, e.g. open WhatsApp.\n" + ", ".join(names))
                except Exception as e:
                    log(f"LIST apps failed: {e}")
                    self.say("I couldn't list your apps just now. Please try again in a moment.")
                return
        if lw.startswith(("quick ", "fast ", "q ")):
            q = line.split(" ", 1)[1]
            self._bg(lambda: fast_answer(q))
            return
        if lw.startswith(("mind ", "think ", "genius mind ")):
            q = line.split(" ", 2)[2] if lw.startswith("genius mind ") else line.split(" ", 1)[1]
            if PIC_ASK.search(q):           # 111.6: Mind can't draw, so a picture ask goes to the picture maker
                self._quiet_echo = True
                self.handle(q)
                return
            self._bg(lambda: genius_mind(q))
            return
        if lw in ("home", "home page", "dashboard"):
            self.app.open_home()
            return
        if lw in ("wealth", "wealth bot", "genius wealth", "money bot", "trading bot", "trade bot", "invest"):
            self.wealth_menu()
            return
        if lw in ("trade", "my trade", "check trade", "check my trade", "read trade", "trade screenshot",
                  "profit", "loss", "profit or loss"):
            self.chart_pick()
            return
        if lw in ("chart", "read chart", "trading chart", "analyse chart", "analyze chart"):
            self.chart_pick()
            return
        if lw.startswith(("market ", "live ", "rate ")) or lw in ("dollar rate", "usd rate"):
            q = "usd ugx" if lw in ("dollar rate", "usd rate") else lw.split(" ", 1)[1]
            self._bg(lambda: market_quote(q))
            return
        if getattr(self, "bot_mode", None) == "wealth":
            if lw in ("exit bot", "leave bot", "stop bot", "normal", "exit wealth"):
                self.bot_mode = None
                self.mode_lbl.text = "Fast"
                self.say("Back to normal Genius.")
                return
            q = line
            self._bg(lambda: wealth_answer(q, self._wealth_profile()))
            return
        if lw in ("profile", "my profile", "account", "me"):
            self.profile_drawer()
            return
        if lw in ("share", "share genius", "share app", "invite", "invite friends"):
            self.share_menu()
            return
        if lw in ("everywhere", "bubble", "hey genius", "shortcuts", "widget", "home screen"):
            self.everywhere_menu()
            return
        if lw in ("premium", "upgrade premium", "pay", "subscribe", "trial", "my plan", "unlock premium"):
            self.premium_popup()
            return
        if lw.startswith("makecode") or lw.startswith("make code"):
            self.owner_make_code(line)
            return
        FREE_WEALTH = (lw in ("wealth", "wealth bot", "genius wealth", "money bot", "trading bot", "trade bot", "invest",
                              "trade", "my trade", "check trade", "check my trade", "read trade", "trade screenshot",
                              "profit", "loss", "profit or loss", "chart", "read chart", "trading chart", "analyse chart", "analyze chart", "dollar rate",
                              "usd rate", "home", "home page", "dashboard")
                       or lw.startswith(("market ", "live ", "rate "))
                       or getattr(self, "bot_mode", None) == "wealth")
        if not CURRENT["owner"] and not FREE_WEALTH and lw not in ("help", "version", "exit", "close", "bye"):
            ok, _msg = premium_status()
            if not ok:
                self.premium_popup()
                return
            premium_count_use()
        if lw in ("fun", "fun studio", "studio", "have fun"):
            self.fun_studio()
            return
        if lw in ("camera", "open camera", "take photo", "take a photo", "photo"):
            self.camera_menu()
            return
        if lw in ("help improve", "help improve genius", "improve genius", "ai scores", "best ai", "ai stats"):
            self.help_improve_menu()
            return
        if lw in ("profile picture", "profile photo", "change profile picture", "change profile photo", "change my photo",
                  "change my picture", "profile pic", "change profile pic", "set profile picture", "my profile picture"):
            self.change_profile_photo()
            return
        if lw in ("eye camera", "genius eye", "iphone camera", "iphone 18 camera", "beauty camera", "beauty selfie"):
            self.take_photo(front=True, eye=True)
            return
        if lw in ("eye beauty", "glam beauty", "portrait blur", "portrait mode", "natural beauty"):
            src = LAST_IMAGE.get("path")
            if not src or not os.path.exists(src):
                self.say("Take a photo first: say genius eye.")
                return
            mode = "glam" if "glam" in lw else "portrait" if "portrait" in lw else "natural"
            self.fun_transform(src, "EYE:" + mode)
            return
        if lw in ("selfie", "front camera", "selfie camera"):
            self.take_photo(front=True)
            return
        if lw in ("zoom camera", "super zoom", "zoom"):
            self.zoom_camera()
            return
        if lw in ("clone my voice", "voice clone", "my voice clone", "make my voice clone", "new voice clone"):
            self.voice_clone_setup()
            return
        if lw in ("ai sing", "ai sing my song", "ai sing it", "sing it for me", "sing for me in my voice",
                  "ai sings in my voice", "sing my song in my voice"):
            self.ai_sing()
            return
        if lw in ("record vocals", "record my voice", "vocal studio", "vocals", "sing my song", "sing it",
                  "song in my voice", "my voice song", "record song", "sing in my voice", "add my voice"):
            self.vocal_studio()
            return
        for pre in ("pro song ", "real song ", "eleven song ", "elevenlabs song ", "ai song ", "song with singing ",
                    "sung song ", "make a pro song ", "make a real song "):
            if lw.startswith(pre) and len(lw) > len(pre) + 2:
                self.pro_song(line.strip()[len(pre):])
                return
        if lw in ("pro song", "real song", "eleven song", "elevenlabs song", "ai song", "song with singing"):
            self.pro_song("")
            return
        for pre in ("song in my voice ", "make a song in my voice ", "make song in my voice ", "create a song in my voice ",
                    "create song in my voice ", "my voice song "):
            if lw.startswith(pre) and len(lw) > len(pre) + 2:
                self._sing_after = True
                self.make_music(line.strip()[len(pre):])
                return
        if ("in my voice" in lw or "with my voice" in lw) and any(w in lw for w in ("song", "sing", "music")):
            self._sing_after = True
            desc = re.sub(r"\b(in|with) my (own )?voice\b", "", line.strip(), flags=re.I)
            desc = re.sub(r"^\s*(please\s+)?(make|create|compose)\s+(me\s+)?(a\s+)?(song|music)\s*", "", desc, flags=re.I)
            self.make_music(desc.strip() or "afrobeat song")
            return
        if lw in ("sound", "music", "music maker", "make music", "make a song", "song", "make song", "beat", "make a beat"):
            self.music_menu()
            return
        if lw in ("stop music", "stop song"):
            sound_stop()
            self.say("Music stopped.")
            return
        if lw in ("pause music", "pause song", "pause"):
            if sound_playing():
                sound_pause()
                self.say("Paused. Say 'play song' to open the player again.")
            else:
                self.say("Nothing is playing.")
            return
        if lw in ("play song", "play music", "play again", "lyrics", "show lyrics", "karaoke", "song words",
                  "my song", "play my song"):
            self.open_player()
            return
        for pre in ("sound ", "music ", "make music ", "make a song ", "make song ", "song about ", "make a beat ",
                    "create song ", "create a song ", "sing about ", "sing ", "song ", "make me a song "):
            if lw.startswith(pre) and len(lw) > len(pre) + 2:
                self.make_music(line.strip()[len(pre):])
                return
        if lw in ("ultra", "genius ultra", "ultra hd", "best quality", "make it better", "enhance"):
            self.ultra_photo()
            return
        if lw in ("zoom photo", "zoom picture", "zoom a photo"):
            self.zoom_photo_menu()
            return
        if lw in ("ai zoom", "super detail", "enhance zoom"):
            self.ai_zoom()
            return
        if lw in ("looks", "pro looks", "iphone", "iphone look", "camera looks", "iphone effect"):
            self.looks_menu()
            return
        if lw in ("replace", "replace something"):
            self.ai_menu("Replace", REPLACE)
            return
        if lw in ("banana", "banana studio", "nano banana", "banana creator"):
            self.banana_studio()
            return
        if lw in ("banana pro", "banana pro on", "pro mode"):
            BANANA["pro"] = True
            self.say("Nano Banana Pro is on: the most realistic pictures (a bit slower).")
            return
        if lw in ("banana pro off", "pro mode off"):
            BANANA["pro"] = False
            self.say("Back to normal Nano Banana (faster).")
            return
        if low.startswith("banana ") and len(line.split()) > 2:
            self.banana_quick(line.split(" ", 1)[1])
            return
        if lw in ("change clothes", "clothes", "outfit", "change outfit", "change wear"):
            self.ai_menu("Change clothes", OUTFITS)
            return
        if lw in ("change place", "places", "change background", "background"):
            self.ai_menu("Change place", PLACES)
            return
        if lw in ("beautiful", "beautify", "beautiful photo", "make it beautiful"):
            self.beauty_menu()
            return
        if lw in ("collage", "make a collage", "make collage"):
            self.fun_pick("collage")
            return
        if lw in ("slideshow", "make a video", "make video", "video slideshow", "edit video", "video"):
            self.video_menu()
            return
        if lw in ("transform", "effects", "filters", "transform picture"):
            self.transform_menu()
            return
        if lw in ("fun videos", "watch videos", "funny videos"):
            self.fun_videos()
            return
        if low.strip(" .!") in ("accounts", "users", "manage accounts"):
            self.accounts_box()
            return
        if low.strip(" .!") in ("change code", "set code", "secret code", "new code", "setcode"):
            if not CURRENT["owner"]:
                self.say("To change your code, ask the owner to delete your account, then make a new one.")
                return
            code_setup_popup(lambda: self.say("Secret code saved. You'll need it with your password to unlock."))
            return
        if low.strip(" .!") in ("storage", "my storage", "open storage", "show storage"):
            self.storage_box()
            return
        if low.strip(" .!") in ("save this", "save picture", "save to storage", "store this"):
            if self.attached and os.path.exists(self.attached["path"]):
                self.say(storage_put(self.attached["path"])[1])
            else:
                self.storage_save_last()
            return
        if low.startswith("store note ") or low.startswith("save note "):
            f = storage_note(line.split(" ", 2)[2])
            self.say("Note saved to your storage as " + os.path.basename(f) + ".")
            return
        if low.strip(" .!") in ("new picture", "new photo", "start fresh"):
            LAST_IMAGE.update(path=None, time=0, prompt="")
            self.say("Okay, the next picture starts fresh.")
            return
        if low.strip(" .!") in ("undo picture", "undo", "go back", "previous picture"):
            if IMAGE_STACK:
                LAST_IMAGE.update(IMAGE_STACK.pop())
                LAST_IMAGE["time"] = time.time()
                self.show_image(LAST_IMAGE["path"], "Back to the previous picture")
            else:
                self.say("There's no earlier picture to go back to.")
            return
        if action == "edit" or (action not in ALLOWED and action not in NEW_ACTIONS
                                and action not in LIFE_ACTIONS and is_image_edit(low)):
            instr = arg if action == "edit" else line
            if not LAST_IMAGE["path"]:
                self.say("Draw a picture first, then tell me what to change.")
            elif not instr:
                self.say("Tell me what to change, e.g. edit make it night time")
            else:
                self.do_edit(instr)
            return
        att = getattr(self, "attached", None)
        if att and low.strip(" .!") in ("remove file", "remove picture", "forget file", "clear file"):
            self.attached = None
            self.say("Okay, I put that file away.")
            return
        if att and action not in ALLOWED and action not in NEW_ACTIONS and action not in LIFE_ACTIONS \
                and (att["kind"] != "image" or re.search(
                    r"\?|^(what|who|where|which|why|how|read|explain|describe|summari[sz]e|translate|tell|is |are |does |can you see|look)", low)):
            self.file_question(line)
            return
        if not LAST_IMAGE["path"] and my_photo() and re.match(r"^(make|put|show|place) me\b", low):
            self.run(line, "draw", line)
            return
        # 111.7: a clear picture ask goes straight to the picture maker, so no AI can answer it with only words
        if (action not in ALLOWED and action not in NEW_ACTIONS and action not in LIFE_ACTIONS
                and not (att and att.get("kind") == "image") and PIC_ASK.search(low)
                and not re.match(r"^\s*(how|why|what|when|where|who|which|can|could|is|are|do|does|explain|tell)\b", low)):
            self.run(line, "draw", line)
            return
        if getattr(self, "pending_quiz", None) and action.strip(".)") in ("a", "b", "c", "d"):
            self.check_quiz(action.strip(".)").upper())
            return
        if action in NEW_ACTIONS:
            self.guardian(action, arg)
            return
        if action in LIFE_ACTIONS:
            self.life(action, arg)
            return
        if action in FORBIDDEN:
            log(f"BLOCKED by watcher: {line}")
            self.say("Watcher blocked that. I can't do it.")
            return
        if action not in ALLOWED:
            log("CHAT")
            self.chat(line)
            return
        if action == "stop":
            log("STOP by ssalimuto")
            self.say(f"Shutting down. Goodbye {CURRENT['name']}.")
            Clock.schedule_once(lambda *_: self.app.stop(), 2.5)
            return
        if action == "deep":
            self.toggle_deep()
            return
        if action == "help":
            self.show("AI", "[b]Commands[/b]\n" + "\n".join(f"{k} - {v}" for k, v in ALLOWED.items())
                      + "\n\n[b]More things you can say[/b]\n" + "\n".join(f"{k} - {v}" for k, v in HELP_EXTRA.items())
                      + "\n\nOr just talk to me normally.")
            return
        if action == "about":
            self.show("AI", ABOUT_TEXT)
            return
        if action in ("version", "whatsnew", "changelog"):
            self.show("AI", CHANGELOG)
            return
        if action == "licenses":
            self.show("AI", LICENSES_TEXT)
            return
        if action == "mic":
            self.mic_test()
            return
        if action == "log":
            lines = open(LOG_FILE).readlines()[-15:] if os.path.exists(LOG_FILE) else []
            self.show("AI", "".join(lines) or "Log is empty.")
            return
        if action == "wake":
            self.toggle_wake()
            return
        if action == "aboutme":
            if arg:
                remember_about_me(arg)
                self.say("Got it. I'll remember that about you.")
            else:
                self.show("AI", about_me() or "You haven't told me about yourself yet.")
            return
        if action == "setvoice":
            if arg:
                open(SUNBIRD_KEY_FILE, "w").write(arg.strip())
                _luganda["voice"] = None
                self.say("Voice token saved. I'll use the Sunbird voice.")
            else:
                self.say("Type setvoice, a space, then your Sunbird AI token.")
            return
        if action == "seteleven":
            if not arg:
                self.say("To let Genius sing in your voice: open elevenlabs.io, sign in, go to Developers, API keys, "
                         "create a key, then type seteleven, a space, and the key.")
                return
            k = arg.strip().strip("'\"")
            open(ELEVEN_KEY_FILE, "w").write(k)
            self.say(f"ElevenLabs key saved, ending in {k[-4:]}. Now say clone my voice to record your voice sample.")
            return
        if action == "setpolli":
            if not arg:
                self.say("For sharper, more real pictures for free: open enter.pollinations.ai, sign in, "
                         "create a key, then type setpolli, a space, and the key.")
                return
            k = clean_key(arg)
            open(POLLI_KEY_FILE, "w").write(k)
            self.say(f"Picture key saved, ending in {k[-4:]}. Your pictures now use the sharper Z-Image and Flux makers.")
            return
        if action in ("setgroq", "setrouter"):
            prov = "groq" if action == "setgroq" else "openrouter"
            if not arg:
                site = "console.groq.com" if prov == "groq" else "openrouter.ai"
                self.say(f"Type {action}, a space, then your free key from {site}.")
                return
            k = clean_key(arg)
            open(PROVIDERS[prov]["file"], "w").write(k)
            _model_cache.pop(prov, None)
            self.say(f"{prov.title()} key saved, ending in {k[-4:]}. AIs connected: "
                     + ", ".join(connected_ais()) + ".")
            return
        if action == "ais":
            have = connected_ais()
            self.say("Connected AIs: " + (", ".join(have) or "none") +
                     f". Turbo is {'on' if self.turbo_on() else 'off'}.")
            return
        if action == "turbo":
            d = life_load()
            d["turbo"] = arg.lower() != "off"
            life_save(d)
            self.say("Turbo on. Simple questions go to the fastest AI." if d["turbo"]
                     else "Turbo off. Gemini answers everything.")
            return
        if action in ("mood", "moods", "calm", "talk", "helpline", "trusted", "sos", "call",
                      "myphone"):
            self.personal(action, arg)
            return
        if action == "think":
            if not arg:
                self.say("Say it like: think should I study at night or in the morning")
                return
            self._bg(lambda: think_together(arg), "All your AIs are thinking together...",
                     speak=False)
            return
        if action == "askall":
            if not arg:
                self.say("Say it like: askall what causes rain")
                return
            self._bg(lambda: ask_all(arg), "Asking all your AIs at once...", speak=False)
            return
        if action == "update" and PLAY_BUILD:
            self.say("Genius updates through the Play Store. Open Play Store, search Genius, and tap Update.")
            return
        if action == "upgrade" and PLAY_BUILD:
            self.say("Genius updates through the Play Store. Open Play Store, search Genius, and tap Update.")
            return
        if action == "update":
            def work():
                tell = lambda t: Clock.schedule_once(lambda *_: self.say(t))
                got = fetch_live_update()
                if got == "ready":
                    tell("The newest Genius is ready. Close and reopen Genius to use it.")
                    return
                found, why = online_update()
                if not found:
                    tell(why)
                    return
                install_online_update(found[0], found[1], tell)
            self.say("Checking for a new Genius...")
            threading.Thread(target=work, daemon=True).start()
            return
        if action == "theme":
            pick = arg.lower().strip()
            if pick not in ("gold", "diamond", "classic"):
                self.say(f"Your look is {THEME}. Type theme gold, theme diamond, or theme classic.")
                return
            try:
                open(THEME_FILE, "w").write(pick)
            except Exception:
                self.say("I couldn't save the new look. Try again.")
                return
            self.say(f"{pick.title()} look saved. Close and reopen Genius to see it.")
            return
        if action == "setkey":
            if arg:
                key = clean_key(arg)
                open(KEY_FILE, "w").write(key)
                self.say(f"Key saved, ending in {key[-4:]}. Ask me anything.", plain=True)
            else:
                self.say("Type setkey, a space, then your Gemini key.")
            return
        if action in NEEDS_APPROVAL:
            self.ask_approval(line, action, arg)
            return
        self.run(line, action, arg)

    def ask_approval(self, line, action, arg):
        box = BoxLayout(orientation="vertical", spacing=14, padding=16)
        box.add_widget(Label(text=f"Approve '{line}'?", font_size="20sp", color=TEXTCOL))
        btns = BoxLayout(spacing=12, size_hint_y=None, height="58dp")
        yes = RoundButton(text="Yes", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), font_size="20sp", bold=True)
        no = RoundButton(text="No", bg=GREY, font_size="20sp")
        btns.add_widget(yes)
        btns.add_widget(no)
        box.add_widget(btns)
        pop = Popup(title="Your approval", content=box, size_hint=(0.85, 0.35),
                    auto_dismiss=False, separator_color=GOLD, title_color=GOLD)

        def on_yes(*_):
            pop.dismiss()
            self.run(line, action, arg)

        def on_no(*_):
            pop.dismiss()
            log(f"REJECTED: {line}")
            self.say("Okay, I will not do it.")
        yes.bind(on_press=on_yes)
        no.bind(on_press=on_no)
        pop.open()

    def run(self, line, action, arg):
        log(f"DONE: {line}")
        if action == "draw":
            if not arg:
                self.say("Tell me what to draw, e.g. draw a blue car in Kampala")
                return
            if getattr(self, "busy", False):
                self.say("One moment, I'm still finishing the last job.")
                return
            self.busy = True
            self.say("Drawing... usually under a minute (the free picture maker can take up to 3).")

            def d(*_):
                try:
                    path, err = gemini_image(arg)
                except Exception as e:
                    log(f"DRAW failed: {e}")
                    path, err = None, "Drawing didn't work this time. Check your internet and say it again."

                def done(*_):
                    self.busy = False
                    if path:
                        remember_image(path, arg)
                        self.show_image(path, arg)
                        self.say("Here is your picture.")
                        self.show("AI", IMAGE_TIPS)
                    else:
                        self.say(err)
                Clock.schedule_once(done, 0)
            threading.Thread(target=d, daemon=True).start()
        elif action == "calc":
            self.say(do_calc(arg) if arg else "Type a sum, e.g. calc 12*8+5")
        elif action == "note":
            if arg:
                with open(NOTES_FILE, "a") as f:
                    f.write(time.strftime("%Y-%m-%d %H:%M") + " | " + arg + "\n")
                self.say("Noted.")
            else:
                self.say("Say it like this: note buy airtime")
        elif action == "notes":
            lines = open(NOTES_FILE).readlines() if os.path.exists(NOTES_FILE) else []
            self.show("AI", "".join(lines[-20:]) if lines else "No notes yet.")
        elif action == "save":
            parts = arg.split(maxsplit=1)
            if len(parts) < 2:
                self.say("Say it like this: save wifi MyPass123")
            else:
                vault_save(parts[0], parts[1])
                self.say(f"Locked '{parts[0]}'. Only you can open it here.")
            return
        elif action == "open":
            if not arg:
                self.say("Say which one, e.g. open wifi")
                return
            val = vault_get(arg)
            self.say(f"{arg}: {val}" if val is not None else f"Nothing saved under '{arg}'.", plain=True)  # secrets stay uncoloured
            return
        elif action == "secrets":
            v = vault_load()
            self.show("AI", "In your locker: " + ", ".join(v.keys()) if v else "Your locker is empty.")
            return
        elif action == "weather":
            self.busy = True
            self.say("Checking the weather...")

            def w(*_):
                r = weather_report(arg or "Kampala")

                def done(*_):
                    self.busy = False
                    self.say(r)
                Clock.schedule_once(done, 0)
            threading.Thread(target=w, daemon=True).start()
        elif action == "restore":
            self._bg(restore_backup, "Restoring your backup...")
            return
        elif action == "runapp":
            if not arg:
                self.say("Type runapp and a name from myapps.")
                return
            self._bg(lambda: run_program(arg), f"Running {arg}...", speak=False)
            return
        elif action == "time":
            self.say("It is " + time.strftime("%I:%M %p, %A %d %B %Y"))
        elif action == "battery":
            self.say(battery_text())
        elif action == "vibrate":
            self.say(vibrate())
        elif action == "notify":
            msg = arg or "Hello ssalimuto, your AI is working."
            self.say("Notification sent." if notify("Genius", msg) else "Notifications are not available.")
        elif action == "remind":
            parts = arg.split(maxsplit=1)
            if not parts or not parts[0].isdigit():
                self.say("Say it like this: remind 5 drink water")
                return
            minutes, text = int(parts[0]), (parts[1] if len(parts) > 1 else "Reminder")
            self.say(f"Okay, I will remind you in {minutes} minutes. Keep me open.")

            def fire(*_):
                notify("Reminder", text)
                log(f"REMINDER fired: {text}")
                self.say("Reminder: " + text)
            Clock.schedule_once(fire, minutes * 60)

    def _fire_reminder(self, text):
        notify("Reminder", text)
        vibrate()
        log(f"REMINDER fired: {text}")
        self.say("Reminder: " + text)

    # ================= life tools on screen =================
    def _bg(self, job, wait_msg=None, speak=None):
        """Run a slow job in the background, then show/speak the result."""
        if speak is None:
            speak = wait_msg is not None
        wait_msg = wait_msg or "[i]Working on it...[/i]"
        if getattr(self, "busy", False):
            self.say("Still working on the last thing. One moment.")
            return
        self.busy = True
        self.show("AI", wait_msg)

        def work():
            try:
                r = job()
            except Exception as e:
                log(f"LIFE error: {e}")
                r = "Something went wrong. Check your internet and try again."

            def done(*_):
                self.busy = False
                if speak:
                    self.say(r)
                else:
                    self.show("AI", r)
            Clock.schedule_once(done, 0)
        threading.Thread(target=work, daemon=True).start()

    # ---------- Set up AI key: a friendly step-by-step wizard ----------
    def key_wizard(self, prov=None, *_):
        if not CURRENT["owner"]:
            self.say("Only the owner of this phone can add an AI key. Ask the owner to set it up.")
            return
        dark = (0.1, 0.1, 0.1, 1)
        root = BoxLayout(orientation="vertical", spacing=10, padding=[12, 10, 12, 12])
        pop = Popup(title="Set up AI key", content=root, size_hint=(0.96, 0.94),
                    separator_color=GOLD, title_color=GOLD, title_size="20sp", auto_dismiss=False)
        state = {"prov": prov if prov in KEY_WIZARD_INFO else None, "busy": False, "open": True}

        def text(t, size="18sp", col=TEXTCOL, bold=False):
            lb = Label(text=t, markup=True, font_size=size, color=col, bold=bold, size_hint_y=None,
                       halign="left", valign="top")
            lb.bind(width=lambda w, *_: setattr(w, "text_size", (w.width, None)),
                    texture_size=lambda w, *_: setattr(w, "height", w.texture_size[1] + dp(6)))
            return lb

        def button(t, fn, col=BLUE, h="56dp", size="18sp"):
            b = RoundButton(text=t, bg=col, fg=dark if col == GOLD else TEXTCOL, size_hint_y=None,
                            height=h, font_size=size, bold=True, halign="center", valign="middle")
            b.bind(size=lambda w, *_: setattr(w, "text_size", (w.width - dp(16), None)))
            b.bind(on_press=lambda *_: fn())
            return b

        def page(title, items, nav):
            root.clear_widgets()
            sv = ScrollView(bar_color=(1.0, 0.78, 0.30, 0.7), bar_width="3dp")
            col = GridLayout(cols=1, spacing=10, size_hint_y=None, padding=[2, 2, 2, 8])
            col.bind(minimum_height=col.setter("height"))
            col.add_widget(text(f"[b]{title}[/b]", "21sp", GOLD))
            for w in items:
                col.add_widget(w)
            sv.add_widget(col)
            root.add_widget(sv)
            row = BoxLayout(size_hint_y=None, height="56dp", spacing=10)
            for w in nav:
                row.add_widget(w)
            root.add_widget(row)

        def close():
            state["open"] = False
            pop.dismiss()

        def step1():
            have = connected_ais()
            items = [text("An AI key lets Genius answer anything. It's free and takes about 2 minutes. "
                          "Pick one (the first is best):")]
            if have:
                items.append(text("Already connected: " + ", ".join(have) + ". You can add another.",
                                  "15sp", HINT))
            for i, (p, info) in enumerate(KEY_WIZARD):
                star = "* Recommended\n" if i == 0 else ""
                items.append(button(f"{star}{info['name']}\n[size=14sp]{info['tag']}[/size]",
                                    lambda p=p: step2(p), GOLD if i == 0 else BLUE, h="88dp"))
            for b in items:
                if isinstance(b, RoundButton):
                    b.markup = True
            page("Step 1 of 3: Pick an AI", items, [button("Close", close, GREY)])

        def step2(p):
            state["prov"] = p
            info = KEY_WIZARD_INFO[p]
            items = [text(f"Get your free {info['name']} key:")]
            for n, s in enumerate(info["steps"], 1):
                items.append(text(f"[b][color=ffc84d]{n}.[/color][/b]  {s}"))
            items.append(button("Open the key page", lambda: open_url(info["url"]), GOLD))
            items.append(text("Your key is like a password. Keep it secret and never send it to anyone. "
                              "Genius keeps it only on this phone.", "15sp", HINT))
            page(f"Step 2 of 3: Get a {info['name']} key", items,
                 [button("Back", step1, GREY), button("I copied it", lambda: step3(p), GOLD)])

        def step3(p, keep=""):
            info = KEY_WIZARD_INFO[p]
            box = style_input(TextInput(hint_text=f"Your key starts with {info['starts'][0]}",
                                        multiline=False, password=True, font_size="18sp",
                                        size_hint_y=None, height="54dp", text=keep))
            status = text("", "17sp", HINT)
            tail = text("", "15sp", HINT)

            def show_tail(*_):
                k = wizard_clean_key(p, box.text)
                tail.text = f"Pasted a key ending in {key_tail(k)}" if k else ""
            box.bind(text=show_tail)
            show_tail()

            def paste():
                try:
                    from kivy.core.clipboard import Clipboard
                    got = Clipboard.paste() or ""
                except Exception:
                    got = ""
                if got.strip():
                    box.text = wizard_clean_key(p, got)
                    status.color, status.text = HINT, "Pasted. Now tap 'Test and save'."
                else:
                    status.color, status.text = RED, ("Nothing copied yet. On the key page tap 'Copy', "
                                                      "then come back and tap Paste.")

            def test():
                if state["busy"]:
                    return
                key = wizard_clean_key(p, box.text)
                ok, why = key_format_check(p, key)
                if not ok:
                    status.color, status.text = RED, why
                    return
                state["busy"] = True
                status.color, status.text = GOLD, "Checking your key with " + info["name"] + "..."

                def work():
                    good, msg = test_ai_key(p, key)
                    if good:
                        try:
                            save_ai_key(p, key)
                        except Exception as e:
                            log(f"KEY WIZARD: save failed: {type(e).__name__}")
                            good, msg = False, "The key works, but I couldn't save it. Free some phone space and try again."

                    def done(*_):
                        state["busy"] = False
                        if not state["open"]:
                            return
                        if good:
                            finish(p, msg)
                        else:
                            fail(p, box.text, msg)
                    Clock.schedule_once(done, 0)
                threading.Thread(target=work, daemon=True).start()

            items = [text("Paste the key you copied:"), box, tail,
                     button("Paste", paste, BLUE), status]
            page("Step 3 of 3: Paste and test", items,
                 [button("Back", lambda: step2(p), GREY), button("Test and save", test, GOLD)])

        def fail(p, keep, msg):
            items = [text("[b][color=ff6b85]That didn't work.[/color][/b]"), text(msg)]
            page("Key not saved", items,
                 [button("Back", lambda: step2(p), GREY), button("Try again", lambda: step3(p, keep), GOLD)])

        def finish(p, msg):
            name = KEY_WIZARD_INFO[p]["name"]
            items = [text(f"[b][color=ffc84d]{msg}[/color][/b]", "21sp"),
                     text(f"{name} is connected. Ask me anything!")]
            page("All set", items, [button("Done", close, GOLD)])
            self.say(f"{name} key saved and tested, ending in {msg.split('Ending in ')[-1].rstrip('.')}. "
                     "AIs connected: " + (", ".join(connected_ais()) or name) + ".")
            Clock.schedule_once(lambda *_: close() if state["open"] else None, 4)

        if state["prov"]:
            step2(state["prov"])
        else:
            step1()
        pop.open()

    def offer_key_wizard(self, *_):
        """When an answer needs a key, offer the wizard with one tap (once per session)."""
        if not CURRENT["owner"] or getattr(self, "_key_offered", False):
            return
        self._key_offered = True
        box = BoxLayout(orientation="vertical", spacing=12, padding=14)
        lb = Label(text="I need a free AI key to answer that. Want me to walk you through getting one? "
                        "It takes about 2 minutes.", font_size="18sp", color=TEXTCOL,
                   halign="center", valign="middle")
        lb.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, None)))
        box.add_widget(lb)
        row = BoxLayout(size_hint_y=None, height="56dp", spacing=10)
        later = RoundButton(text="Later", bg=GREY, fg=TEXTCOL, font_size="18sp")
        go = RoundButton(text="Set up key", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), font_size="18sp", bold=True)
        row.add_widget(later)
        row.add_widget(go)
        box.add_widget(row)
        pop = Popup(title="Set up AI key", content=box, size_hint=(0.9, 0.42),
                    separator_color=GOLD, title_color=GOLD)
        later.bind(on_press=pop.dismiss)

        def start(*_):
            pop.dismiss()
            Clock.schedule_once(lambda *_: self.key_wizard(), 0.1)
        go.bind(on_press=start)
        pop.open()

    def _on_chat_ref(self, _w, ref):
        if ref in ("like", "dislike"):
            self.rate_answer(ref == "like")
            return
        if ref == "keywizard":
            self.key_wizard()
        elif ref in NEWS_LINKS:
            try:
                open_in_genius(NEWS_LINKS[ref], "News")
            except Exception as e:
                log(f"NEWS open failed: {e}")
                self.say("I couldn't open that story. Check your internet.")

    def _retry_later(self, text):
        """No AI reachable even after waiting: keep the question and answer it by itself when signal returns.
        Runs in the background, so the app never freezes while it waits."""
        self._pending_q = text
        if getattr(self, "_pending_on", False):
            return
        self._pending_on = True

        def watch():
            end = time.time() + 600
            while time.time() < end and getattr(self, "_pending_q", None):
                if wait_for_net(10):
                    while getattr(self, "busy", False) and time.time() < end:
                        time.sleep(1)
                    q, self._pending_q = self._pending_q, None
                    if q:
                        def go(*_):
                            self.show("AI", "[i]Signal is back. Answering your question now...[/i]")
                            self.chat(q)
                        Clock.schedule_once(go, 0)
                    break
                time.sleep(5)
            self._pending_on = False
        threading.Thread(target=watch, daemon=True).start()

    def _v110_after(self, r):
        """Keep good answers for offline use; if no AI was reachable, answer from what's saved."""
        q = getattr(self, "_v110_q", "")
        if r and r not in (NET_AI_MSG, NO_AI_MSG) and len(r) > 60:
            self._rate = {"ai": LAST_AI.get("name") or "gemini", "q": q, "a": r}
            self._rate_next = True
        try:
            if r in (NET_AI_MSG,) or not r:
                off = offline_answer(q) if q else None
                return off or r or NET_AI_MSG
            if q:
                offline_cache_add(q, r)
        except Exception as e:
            log(f"V110 cache failed: {type(e).__name__}")
        return r

    # ---------- world news ----------
    def news_menu(self, *_):
        self.show_news("uganda")          # 111.9: straight to the video news screen (topics are tabs there)
        return
        opts = [(NEWS_TOPICS[k][0], (lambda k=k: self.show_news(k)), GOLD if k in ("world", "uganda", "social") else BLUE)
                for k in NEWS_TOPICS]
        opts.append(("News brief (AI summary)", lambda: self._bg(lambda: news_brief("world"),
                                                                 "Reading today's headlines...", speak=False), GOLD))
        self._buttons_popup("World news", opts, cols=2, hint="Pick a topic. Tap a headline to read the full story")

    def show_news(self, topic):
        """111.9: news screen, videos first (they play inside Genius), then photo stories, then headlines."""
        topic = (topic or "world").strip()
        t = NEWS_ALIASES.get(topic.lower(), topic.lower())
        name = NEWS_TOPICS[t][0] if t in NEWS_TOPICS else topic.title()
        root = BoxLayout(orientation="vertical", spacing=dp(6), padding=[dp(6), dp(6)])
        tabs_sv = ScrollView(size_hint_y=None, height=dp(52), do_scroll_y=False, bar_width=0)
        tabs = BoxLayout(size_hint_x=None, spacing=dp(6))
        tabs.bind(minimum_width=tabs.setter("width"))
        pop = Popup(title=f"{name} news", content=root, size_hint=(1, 1), separator_color=GOLD,
                    title_color=GOLD, title_size="20sp")
        for k in ("uganda", "world", "sports", "africa", "business", "tech", "entertainment", "health", "social"):
            b = RoundButton(text=NEWS_TOPICS[k][0], bg=GOLD if k == t else GREY,
                            fg=(0.1, 0.1, 0.1, 1) if k == t else TEXTCOL, size_hint_x=None,
                            width=dp(30) + dp(9) * len(NEWS_TOPICS[k][0]), font_size="14sp", bold=True)
            b.bind(on_press=lambda _b, k=k: (pop.dismiss(), Clock.schedule_once(lambda *_: self.show_news(k), 0.1)))
            tabs.add_widget(b)
        tabs_sv.add_widget(tabs)
        root.add_widget(tabs_sv)
        sv = ScrollView(do_scroll_x=False)
        grid = GridLayout(cols=1, spacing=dp(10), size_hint_y=None, padding=[0, dp(4)])
        grid.bind(minimum_height=grid.setter("height"))
        wait = Label(text="Getting the latest videos and stories...", size_hint_y=None, height=dp(60),
                     color=HINT, font_size="16sp")
        grid.add_widget(wait)
        sv.add_widget(grid)
        root.add_widget(sv)
        close = RoundButton(text="Close", bg=GREY, fg=TEXTCOL, size_hint_y=None, height=dp(50), bold=True)
        close.bind(on_press=pop.dismiss)
        root.add_widget(close)
        pop.open()
        state = {"open": True}
        pop.bind(on_dismiss=lambda *_: state.update(open=False))

        def tap(card):
            it = card.item
            if it.get("url"):
                open_in_genius(it["url"], it.get("src") or "News")

        def work():
            vids, pics, heads = [], [], []
            try:
                vids = news_videos(t, 12)
            except Exception as e:
                log(f"NEWS videos failed: {type(e).__name__}")
            try:
                pics = news_photos(t, 6)
            except Exception as e:
                log(f"NEWS photos failed: {type(e).__name__}")
            if len(vids) + len(pics) < 6:
                try:
                    heads = [{"title": a, "src": b, "url": c, "when": d, "video": False, "img": ""}
                             for a, b, c, d in news_items(topic, 8)]
                except Exception as e:
                    log(f"NEWS headlines failed: {type(e).__name__}")
            items = vids[:4] + pics[:2] + vids[4:8] + pics[2:4] + vids[8:] + pics[4:] + heads   # mostly videos

            def fill(*_):
                grid.clear_widgets()
                if not items:
                    grid.add_widget(Label(text=f"I couldn't get {name} news right now. Check your internet and try again.",
                                          size_hint_y=None, height=dp(80), color=HINT, font_size="16sp",
                                          text_size=(Window.width * 0.85, None), halign="center"))
                    return
                cards = []
                for it in items:
                    c = NewsCard(it)
                    c.bind(on_release=tap)
                    grid.add_widget(c)
                    cards.append(c)
                grid.add_widget(Label(text="Tap any video or story to watch or read it inside Genius.",
                                      size_hint_y=None, height=dp(40), color=HINT, font_size="13sp"))

                def pics_job():
                    for c in cards:
                        if not state["open"]:
                            return
                        if c.item.get("img"):
                            pth = news_thumb(c.item["img"])
                            if pth:
                                Clock.schedule_once(lambda *_, c=c, pth=pth: c.set_pic(pth), 0)
                threading.Thread(target=pics_job, daemon=True).start()
            Clock.schedule_once(fill, 0)
        threading.Thread(target=work, daemon=True).start()

    def _need_key(self):
        if connected_ais():
            return False
        self.say("This one needs an AI key. Type key (or tap below) and I'll help you get a free one in 2 minutes, "
                 "then ask again.")
        Clock.schedule_once(self.offer_key_wizard, 0.3)
        return True

    def life(self, action, arg):
        d = life_load()
        if action in ("makeai", "myais", "ask", "backup"):
            self.ai_maker(action, arg)
            return
        if action in ("build", "myapps", "showapp", "hotspot"):
            self.builder(action, arg)
            return
        if action in ("life", "freelance"):
            self.show("AI", LIFE_HELP)
            return
        # ---- study ----
        if action == "study":
            self.say(study_status(d))
        elif action == "subjects":
            subs = [x.strip().title() for x in re.split(r"[,;]| and ", arg) if x.strip()]
            if not subs:
                self.say("Say it like: subjects Maths, Biology, English")
                return
            d["study"]["subjects"] = subs
            life_save(d)
            self.say("Saved your subjects: " + ", ".join(subs) + ". Type quiz to practise.")
        elif action == "exam":
            m = re.search(r"(\d{4}-\d{2}-\d{2})", arg)
            if not m:
                self.say("Say it like: exam UCE 2026-11-02")
                return
            name = arg.replace(m.group(1), "").strip() or "your exam"
            d["study"]["exam"] = {"name": name, "date": m.group(1)}
            life_save(d)
            self.say("Saved. " + exam_countdown(d))
        elif action == "quiz":
            subs = d["study"]["subjects"]

            def job():
                q = make_quiz(arg, subs)
                self.pending_quiz = q
                return (f"{q['topic']}\n{q['q']}\n" +
                        "\n".join(f"{l}. {o}" for l, o in zip("ABCD", q["o"])) +
                        "\nAnswer A, B, C or D.")
            self._bg(job, "Making a question...")
        elif action == "explain" and (not arg or re.fullmatch(
                r"(it|that|this|more|again|better|further|each part|every part|the parts|all|deeper|"
                r"each|each one|step by step|simply|in detail|more please|it more|that more)", arg.strip().lower())):
            self.chat("Explain your last answer " + (arg or "more") + ", in more detail and simply.")
        elif action == "explain":
            if not arg:
                self.say("Tell me what to explain, e.g. explain osmosis")
                return
            if self._need_key():
                return
            self._bg(lambda: ask_gemini(
                f"Explain '{arg}' for a Ugandan secondary school student in under 120 words: "
                f"a simple definition, one everyday Ugandan example, and one exam tip.", 500)
                or "No AI could be reached after trying every way. Check your data or Wi-Fi, then send it again.", "Thinking...")
        elif action == "studyplan":
            if self._need_key():
                return
            info = study_status(d)
            self._bg(lambda: ask_gemini(
                f"Make today's study plan (max 6 short lines with times, total about 2 hours, "
                f"with breaks) for this student:\n{info}\nFocus on weak topics first.", 600)
                or "No AI could be reached after trying every way. Check your data or Wi-Fi, then send it again.", "Planning your day...", speak=False)
        # ---- money ----
        elif action in ("spent", "got"):
            amt = parse_amount(arg)
            if not amt:
                self.say(f"Say it like: {action} 2000 airtime")
                return
            words = re.sub(r"(ugx|shs?|shillings?)", "", arg, flags=re.I)
            words = re.sub(r"\d[\d,]*\.?\d*\s*[kKmM]?\b", "", words, count=1).split()
            if action == "got":                 # "got 50k pocket money" -> "pocket money"
                cat, note = (" ".join(words).lower() or "income"), ""
            else:
                cat = words[0].lower() if words else "other"
                note = " ".join(words[1:])
            money_add("out" if action == "spent" else "in", amt, cat, note)
            msg = f"Recorded {ugx(amt)} {'spent on' if action == 'spent' else 'received:'} {cat}."
            if action == "spent":
                d2 = life_load()
                week = money_summary(d2, 7).split("\n")[0]
                msg += " " + week
            self.say(msg)
        elif action == "money":
            days = parse_amount(arg) or 7
            self.say(money_summary(d, days))
        elif action == "goal":
            amt = parse_amount(arg)
            name = re.sub(r"\d[\d,]*\.?\d*\s*[kKmM]?\b", "", arg).strip().lower()
            if not amt or not name:
                self.say("Say it like: goal phone 300k")
                return
            d["money"]["goals"][name] = {"target": amt,
                                         "saved": d["money"]["goals"].get(name, {}).get("saved", 0)}
            life_save(d)
            self.say(f"Goal set: {name}, {ugx(amt)}. Add money with: put {name} 10k")
        elif action == "put":
            amt = parse_amount(arg)
            name = re.sub(r"\d[\d,]*\.?\d*\s*[kKmM]?\b", "", arg).strip().lower()
            g = d["money"]["goals"].get(name)
            if not amt or not g:
                have = ", ".join(d["money"]["goals"]) or "none yet"
                self.say(f"Say it like: put phone 10k. Your goals: {have}.")
                return
            g["saved"] += amt
            life_save(d)
            left = max(0, g["target"] - g["saved"])
            self.say(f"Added {ugx(amt)} to {name}. Saved {ugx(g['saved'])}, "
                     + (f"{ugx(left)} to go." if left else "goal reached! Well done."))
        # ---- brief ----
        elif action == "brief":
            low = arg.lower()
            if low == "off":
                d["brief"]["auto"], d["brief"]["at"] = False, ""
                life_save(d)
                self.say("Morning brief is off. Type brief anytime to hear it.")
            elif low.startswith("at"):
                m = re.search(r"(\d{1,2}):(\d{2})", low)
                if not m:
                    self.say("Say it like: brief at 07:00")
                    return
                d["brief"]["at"] = f"{int(m.group(1)):02d}:{m.group(2)}"
                d["brief"]["auto"] = True
                life_save(d)
                self.say(f"I'll give your brief at {d['brief']['at']} every day while I'm open, "
                         "and when you first open me each day.")
            elif low.startswith("city"):
                d["brief"]["city"] = arg[4:].strip() or "Kampala"
                life_save(d)
                self.say(f"Brief city set to {d['brief']['city']}.")
            else:
                self._bg(lambda: build_brief(os.path.exists(KEY_FILE)), "Preparing your brief...")
        # ---- freelancing ----
        elif action == "skills":
            if not arg:
                self.say(f"Your skills: {d['work']['skills'] or 'not set'}. Add them: skills typing, Canva")
                return
            d["work"]["skills"] = arg
            life_save(d)
            remember_about_me("Skills: " + arg)
            self.say("Saved your skills. Try: gigs, cv, or price <task>.")
        elif action in ("cv", "proposal", "gigs", "price"):
            if self._need_key():
                return
            skills = d["work"]["skills"] or "not given yet"
            if action == "proposal" and not arg:
                self.say("Paste the job after the word proposal.")
                return
            if action == "price" and not arg:
                self.say("Tell me the task, e.g. price logo design")
                return
            prompts = {
                "cv": (f"Write a one-page beginner CV in plain text for this person. Skills: {skills}. "
                       "Use only facts they gave; put [brackets] where details are missing. "
                       "Sections: Profile, Skills, Education, Projects, Contact.", 1200, False),
                "proposal": (f"Write a short, confident freelance proposal (under 150 words) for this job. "
                             f"My skills: {skills}. Don't invent experience. Job:\n{arg}", 600, False),
                "gigs": (f"List 5 real, current places where a beginner in Uganda with these skills "
                         f"can find paid online work: {skills}. Include the site name, the kind of "
                         f"gig, and how payment reaches Uganda. Be brief.", 0, True),
                "price": (f"What should a beginner freelancer in Uganda charge for: {arg}? Give a "
                          f"range in USD and UGX for local and international clients, in 3 lines.",
                          400, False),
            }
            text, toks, search = prompts[action]
            res = {}

            def job():
                r = ask_gemini(text, toks or 600, search=search) or "No AI could be reached after trying every way. Check your data or Wi-Fi, then send it again."
                if action == "cv":
                    open("my_cv.txt", "w").write(r)
                    r += "\n\n(Saved as my_cv.txt)"
                return r
            self._bg(job, "Working on it...", speak=action in ("price",))

    def ai_maker(self, action, arg):
        if action == "makeai":
            name, _, purpose = arg.partition(":")
            if not name.strip() or not purpose.strip():
                self.say("Say it like: makeai tutor: a biology teacher for UCE")
                return
            if self._need_key():
                return

            def job():
                n, path = make_bot(name, purpose.strip())
                return (f"Your new AI '{n}' is ready. Ask it with: ask {n} your question. "
                        f"I also saved it as its own program, {os.path.basename(path)}.")
            self._bg(job, "Designing your AI...")
        elif action == "myais":
            bots = bots_load()
            self.show("AI", "\n".join(f"{k}: {v['purpose']}" for k, v in bots.items())
                      if bots else "No AIs yet. Try: makeai coach: a football fitness coach")
        elif action == "ask":
            name, _, q = arg.partition(" ")
            if name.lower() not in bots_load() or not q.strip():
                have = ", ".join(bots_load()) or "none yet"
                self.say(f"Say it like: ask tutor what is osmosis. Your AIs: {have}.")
                return
            if self._need_key():
                return
            self._bg(lambda: ask_bot(name, q.strip()), f"Asking {name}...")
        elif action == "backup":
            self._bg(make_backup, "Backing up...")

    def builder(self, action, arg):
        if action == "build":
            if not arg:
                self.say("Tell me what to build, e.g. build a calculator for school fees")
                return
            if self._need_key():
                return

            def job():
                name, path, code, about = build_program(arg)
                if not name:
                    return about
                return (f"Built '{name}'. {about}\nSaved as {path}.\n"
                        f"Type runapp {name} to run it, or showapp {name} to see the code.")
            self._bg(job, "Writing your program...", speak=False)
        elif action == "myapps":
            apps = list_programs()
            self.say("Your programs: " + ", ".join(apps) if apps else
                     "No programs yet. Try: build a times-table quiz")
        elif action == "showapp":
            path = os.path.join(APPS_DIR, re.sub(r"[^a-z0-9_]", "", arg.lower()) + ".py")
            self.show("AI", open(path).read()[:4000] if arg and os.path.exists(path)
                      else "Type showapp and a name from myapps.")
        elif action == "hotspot":
            ok = safe(open_hotspot_settings)
            self.say("Opening hotspot settings. Turn on Mobile hotspot to share your data as Wi-Fi."
                     if ok else "Open Settings, then Connections, then Mobile hotspot, and turn it on.")

    def check_quiz(self, letter):
        q, self.pending_quiz = self.pending_quiz, None
        d = life_load()
        sc = d["study"]["scores"].setdefault(q.get("topic", "General"), [0, 0])
        ok = letter == q["a"]
        sc[0] += int(ok)
        sc[1] += 1
        life_save(d)
        right = q["o"]["ABCD".index(q["a"])]
        self.say(("Correct! " if ok else f"Not quite. The answer is {q['a']}, {right}. ")
                 + q.get("why", "") + " Type quiz for another.")

    def life_start(self):
        """First open of the day: give the brief. Then check the clock every 30 seconds."""
        d = life_load()
        today = time.strftime("%Y-%m-%d")
        if d["brief"].get("auto", True) and d["brief"].get("last") != today:
            d["brief"]["last"] = today
            life_save(d)
            self._bg(lambda: build_brief(os.path.exists(KEY_FILE)), "Preparing your brief...")
        Clock.schedule_interval(self._brief_tick, 30)

    def _brief_tick(self, dt):
        d = life_load()
        at = d["brief"].get("at")
        if not at or not d["brief"].get("auto"):
            return
        stamp = time.strftime("%Y-%m-%d ") + at
        if time.strftime("%H:%M") == at and d["brief"].get("fired") != stamp:
            d["brief"]["fired"] = stamp
            life_save(d)
            self._bg(lambda: build_brief(os.path.exists(KEY_FILE)), "Your brief:")

    def turbo_on(self):
        return life_load().get("turbo", True)

    def _ui_hooks(self):
        return {
            "remind": lambda m, t: Clock.schedule_once(
                lambda *_: self._fire_reminder(t), m * 60),
            "image": lambda path, cap: Clock.schedule_once(
                lambda *_: self.show_image(path, cap), 0),
        }

    def personal(self, action, arg):
        if action == "mood":
            m = re.match(r"\s*([1-5])\b\s*(.*)", arg)
            if not m:
                self.say("How are you feeling from 1 (very low) to 5 (great)? Type: mood 3 tired")
                return
            n, note = int(m.group(1)), m.group(2)
            mood_add(n, note)
            replies = {1: "I'm really sorry it's that hard right now. I'm here. Want to tell me "
                          "what's going on, or try calm to breathe together?",
                       2: "Thanks for telling me. That sounds heavy. What's weighing on you most?",
                       3: "Okay, a middle kind of day. Anything I can take off your plate?",
                       4: "Good to hear. What went well today?",
                       5: "That's wonderful! What made today great?"}
            self.say(replies[n])
            if n == 1:
                self.show("AI", HELPLINES)
        elif action == "moods":
            self.show("AI", mood_summary())
        elif action == "calm":
            for i, step in enumerate(CALM_STEPS):
                Clock.schedule_once(lambda dt, s=step: self.say(s), i * 6)
        elif action == "talk":
            d = life_load()
            d["support"] = arg.lower() != "off"
            life_save(d)
            self.say("I'm here and I'm listening. Tell me anything, no judgement."
                     if d["support"] else "Okay, back to normal mode. I'm always here if you need to talk.")
        elif action == "myphone":
            d = life_load()
            num = re.sub(r"[^\d+]", "", arg)
            if len(num) < 9:
                have = d.get("my_phone")
                self.say(f"Your number is {have}." if have else
                         "Say it like: myphone 0772123456")
                return
            d["my_phone"] = num
            life_save(d)
            remember_about_me("My phone number is " + num)
            self.say(f"Saved your number, {num}. I'll add it to SOS messages so people can call you back.")
        elif action == "helpline":
            self.show("AI", HELPLINES)
        elif action == "trusted":
            d = life_load()
            c = d.setdefault("contacts", {})
            m = re.match(r"\s*(.+?)\s+(\+?\d[\d\s-]{6,})\s*$", arg)
            if arg.lower().startswith("remove "):
                c.pop(arg[7:].strip().title(), None)
                life_save(d)
                self.say("Removed.")
            elif m:
                c[m.group(1).strip().title()] = re.sub(r"[\s-]", "", m.group(2))
                life_save(d)
                self.say(f"Saved {m.group(1).strip().title()} as a trusted person. "
                         "Type sos if you ever need them.")
            else:
                self.show("AI", ("Trusted people: " + ", ".join(f"{k} {v}" for k, v in c.items()))
                          if c else "No trusted people yet. Add one: trusted Mum 0772123456")
        elif action == "sos":
            c = contacts_load()
            if not c:
                self.say("Add a trusted person first, e.g. trusted Mum 0772123456. "
                         "If you're in danger now, call 999 or 112.")
                self.show("AI", HELPLINES)
                return
            ok = safe(lambda: sos_message(c))
            self.say("I've opened a help message to " + ", ".join(c) + ". Press Send. "
                     "If you're in danger, call 999." if ok else
                     "I couldn't open messages. Call 999 or 112, or Sauti 116.")
        elif action == "call":
            num = contacts_load().get(arg.strip().title()) or re.sub(r"[^\d+]", "", arg)
            if not num:
                if arg.strip():
                    self.say(f"I don't have a number for {arg.strip().title()} yet. Add it like: trusted "
                             f"{arg.strip().title()} 0772123456, then say call {arg.strip().title()}.")
                else:
                    self.say("Say it like: call 116, or call Mum")
                return
            ok = safe(lambda: dial(num))
            self.say(f"Opening the dialer for {num}. Press call." if ok
                     else f"Dial {num} on your phone.")

    def _care_checkin(self, tok):
        if tok != getattr(self, "care_tok", 0):
            return                          # they talked again since; no need
        self.say("Hey, I've been thinking about what you told me earlier. "
                 "How are you feeling now? You can just type a number, mood 1 to 5.")

    # ---------- Genius 101: problem solver, upgrade, security ----------
    def security_alert(self):
        d = intruder_data()
        new = d["events"][d.get("seen", 0):]
        if integrity_check() == "changed":
            self.say("Warning: my code was changed outside an upgrade. If you didn't do it, reinstall Genius.")
        if new:
            trips = sum(1 for e in new if e["e"].startswith("TRIPWIRE"))
            self.say(f"Security alert: {len(new)} break-in events since last time"
                     + (f", and {trips} tripwire(s) opened" if trips else "") + ". Type intruders to see them.")
        d["seen"] = len(d["events"])
        json.dump(d, open(INTRUDER_FILE, "w"))

    def guardian(self, action, arg):
        if action == "solve":
            if not arg:
                self.say("Tell me the problem, e.g. solve I can't focus when studying at home")
                return
            if getattr(self, "busy", False):
                self.say("One moment, I'm still working.")
                return
            self.busy = True
            self.say("Let me think this through with you...")

            def work():
                try:
                    n, plan = solve_problem(arg)
                    txt = plan_text(n, plan)
                    spoken = plan.get("best", "") + " Your first step: " + plan.get("today", "")
                except Exception as e:
                    txt, spoken = f"I couldn't build a plan: {e}", ""

                def done(*_):
                    self.busy = False
                    self.show("AI", txt)
                    if spoken:
                        tts(spoken)
                Clock.schedule_once(done, 0)
            threading.Thread(target=work, daemon=True).start()
            return
        if action == "problems":
            p = problems_load()
            if not p:
                self.say("No problems saved yet. Try: solve <your problem>")
            elif arg.strip().isdigit() and 0 < int(arg) <= len(p):
                self.show("AI", plan_text(int(arg), p[int(arg) - 1]))
            else:
                self.show("AI", "\n".join(
                    f"{i}. {x.get('title')} - {len(x.get('done', []))}/{len(x.get('steps', []))} steps done"
                    for i, x in enumerate(p, 1)) + "\n\nOpen one with: problems 1")
            return
        if action == "step":
            nums = [int(x) for x in arg.split() if x.isdigit()]
            p = problems_load()
            if len(nums) != 2 or not (0 < nums[0] <= len(p)):
                self.say("Say it like this: step 1 2  (problem 1, step 2)")
                return
            plan = p[nums[0] - 1]
            if not (0 < nums[1] <= len(plan.get("steps", []))):
                self.say("That step number isn't in the plan.")
                return
            if nums[1] not in plan["done"]:
                plan["done"].append(nums[1])
            problems_save(p)
            left = len(plan["steps"]) - len(plan["done"])
            self.say("Well done! " + (f"{left} steps to go." if left else "You finished the whole plan. I'm proud of you."))
            return
        if action == "know":
            if not arg:
                self.say("Say it like this: know school: fees are due on 5 November")
                return
            topic = know_add(arg)
            self.say(f"Got it. I'll use that when I help you with {topic}.")
            return
        if action == "knowledge":
            self.show("AI", know_text() or "Nothing yet. Teach me with: know topic: fact")
            return
        if action == "upgrade":
            if arg.lower() in ("yes", "y", "ok") and getattr(self, "pending_upgrade", None):
                self.say(apply_update(self.pending_upgrade))
                self.pending_upgrade = None
                return
            upd, why = find_update()
            if not upd:
                self.say(why)
                return
            self.pending_upgrade = upd
            self.say(f"Found Genius {upd['version']} and its fingerprint checks out. "
                     f"You're on {VERSION}. Type 'upgrade yes' to install it.")
            return
        if action == "rollback":
            self.say(rollback())
            return
        if action == "security":
            self.show("AI", security_report())
            return
        if action == "intruders":
            ev = intruder_data()["events"][-20:]
            self.show("AI", "\n".join(f"{e['t']} | {e['e']} {e['d']}" for e in ev) or "No break-in attempts. All clear.")
            return
        if action == "tripwire":
            if not arg:
                self.show("AI", "Tripwires: " + ", ".join(tripwires().keys()))
                return
            tripwire_add(arg.split()[0])
            self.say(f"Tripwire '{arg.split()[0]}' set. If a hacker opens it in the decoy, I'll tell you.")
            return

    def _run_queued(self, *_):
        if getattr(self, "busy", False) and time.time() - getattr(self, "_busy_since", 0) <= 75:
            return
        if self._queue_ev is not None:
            self._queue_ev.cancel()
        self._queue_ev = None
        q, self._queued = getattr(self, "_queued", None), None
        if q:
            self.busy = False
            self.chat(q)

    def chat(self, text):
        said = text                         # what the person typed, before any hidden rules are added
        if is_distressed(text):
            soft_voice(True)
            self.care_tok = getattr(self, "care_tok", 0) + 1
            tok = self.care_tok
            Clock.schedule_once(lambda dt: self._care_checkin(tok), 30 * 60)
            log("CARE: distress noticed")
            text = CARE_RULES + text
        else:
            soft_voice(False)
            self.care_tok = getattr(self, "care_tok", 0) + 1
        if life_load().get("support"):
            text = ("[Support mode: the owner wants to be heard. Listen, comfort, reflect "
                    "feelings, ask one gentle question; no lectures, no tools unless asked.]\n" + text)
        reply = offline_reply(text)
        if reply:
            self.say(reply)
            return
        harm = harmful_redirect(text)
        if harm:
            self.say(harm)
            return
        self._v110_q = text
        if not net_online():
            off = offline_answer(said)
            self.say(off or OFFLINE_HELP)
            return
        try:
            pre = v110_prompt_prefix(text)
        except Exception:
            pre = ""
        if pre:
            text = pre + "\n" + text
        ck = text.strip().lower()
        if ck in _answer_cache and not needs_tools(text):
            self.say(_answer_cache[ck])          # instant: answered before
            return
        if self.turbo_on() and provider_key("groq") and not needs_tools(text) \
                and not self.deep and not getattr(self, "busy", False):
            self.busy = True
            self._busy_since = time.time()
            self._stream_begin("Thinking fast...")

            def turbo():
                r = groq_stream(text, convo=history, on_text=self._stream_feed) or other_ai("groq", text, convo=history)
                if r:
                    history.append({"role": "user", "parts": [{"text": text}]})
                    history.append({"role": "model", "parts": [{"text": r}]})
                    save_memory()
                    _answer_cache[ck] = r
                else:
                    try:
                        r, err = agent_reply(text, ui_hooks, self.deep) if os.path.exists(KEY_FILE) \
                            else (None, NET_AI_MSG)
                    except Exception as e:
                        log(f"CHAT agent failed: {e}")
                        r, err = None, NET_AI_MSG
                    r = r or err or NET_AI_MSG
                if is_fail_reply(r):
                    Clock.schedule_once(lambda *_: self.show("AI", "[i]Reconnecting to another AI...[/i]"), 0)
                    r2 = rescue_answer(text, convo=history)
                    if r2:
                        r = r2
                        history.append({"role": "user", "parts": [{"text": text}]})
                        history.append({"role": "model", "parts": [{"text": r}]})
                        save_memory()
                    else:
                        self._retry_later(text)

                def done(*_):
                    self.busy = False
                    self._stream_end()
                    self.say(self._v110_after(r))
                Clock.schedule_once(done, 0)
            ui_hooks = self._ui_hooks()
            threading.Thread(target=turbo, daemon=True).start()
            return
        if getattr(self, "busy", False):
            if time.time() - getattr(self, "_busy_since", 0) > 75:
                self.busy = False          # the last one got lost on a bad network: don't stay stuck
            else:
                self._queued = text
                self.say("Got it. I'll do that right after the last one.")
                if not getattr(self, "_queue_ev", None):
                    self._queue_ev = Clock.schedule_interval(self._run_queued, 0.5)
                return
        self.busy = True
        self._busy_since = time.time()
        self.show("AI", "Thinking deeply..." if self.deep else "Thinking...")

        ui = {
            "remind": lambda m, t: Clock.schedule_once(
                lambda *_: self._fire_reminder(t), m * 60),
            "image": lambda path, cap: Clock.schedule_once(
                lambda *_: self.show_image(path, cap), 0),
        }

        def work():
            try:
                r = answer()
            except Exception as e:
                log(f"CHAT failed: {e}")
                r = NET_AI_MSG
            if is_fail_reply(r):
                Clock.schedule_once(lambda *_: self.show("AI", "[i]Reconnecting to another AI...[/i]"), 0)
                r2 = rescue_answer(text, convo=history)
                if r2:
                    r = r2
                    history.append({"role": "user", "parts": [{"text": text}]})
                    history.append({"role": "model", "parts": [{"text": r}]})
                    save_memory()
                else:
                    self._retry_later(text)

            def done(*_):
                self.busy = False
                self.say(self._v110_after(r))
            Clock.schedule_once(done, 0)

        def answer():
            reply, err = None, None
            tried = set()
            fast_ok = not self.deep and not needs_tools(text)
            try:
                have = connected_ais() if fast_ok else []
            except Exception:
                have = []
            if fast_ok and ("groq" in have or "openrouter" in have):
                # speed race: the first good answer wins, nobody waits for the slowest AI
                import queue
                q = queue.Queue()
                racers = []
                if os.path.exists(KEY_FILE):
                    racers.append(lambda: agent_reply(text, ui, False)[0])
                for prov in ranked_providers()[:2]:
                    if prov in have:
                        tried.add(prov)
                        racers.append(lambda prov=prov: other_ai(prov, text, convo=history))

                def run(fn):
                    try:
                        q.put(fn())
                    except Exception:
                        q.put(None)
                for fn in racers:
                    threading.Thread(target=run, args=(fn,), daemon=True).start()
                for _ in racers:
                    try:
                        r_ = q.get(timeout=45)
                    except Exception:
                        break
                    if r_ and r_.strip():
                        reply = r_
                        break
            if not reply and os.path.exists(KEY_FILE):
                reply, err = agent_reply(text, ui, self.deep)
            if not reply:                       # backup AIs not already tried in the race
                for prov in ranked_providers():
                    if prov in tried:
                        continue
                    reply = other_ai(prov, text, convo=history)
                    if reply:
                        break
            if reply and not needs_tools(text):
                _answer_cache[ck] = reply
                if len(_answer_cache) > 300:
                    _answer_cache.pop(next(iter(_answer_cache)))
            return reply or err or NET_AI_MSG
        threading.Thread(target=work, daemon=True).start()



class HomeScreen(BoxLayout):
    """Genius home page: greeting, profile, and big tiles for every feature."""
    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=0, spacing=0, **kw)
        self.app = app
        add_gradient_bg(self)
        header = Panel(bg=HEADER, radius=0, orientation="horizontal", size_hint_y=None, height="64dp",
                       padding=[12, 0, 18, 0], spacing=10)
        pbox = BoxLayout(size_hint_x=None, width="46dp", padding=[0, 11, 0, 11])
        chip = ProfileChip()
        chip.bind(on_press=lambda *_: self.go("profile"))
        pbox.add_widget(chip)
        header.add_widget(pbox)
        hr = time.localtime().tm_hour
        hello = "Good morning" if hr < 12 else "Good afternoon" if hr < 17 else "Good evening"
        name = str(CURRENT.get("name") or "")
        t = Label(text=f"[b]{hello}, {name.title()}[/b]\n[size=12sp][color=9aa0c0]What shall we do today?[/color][/size]",
                  markup=True, color=TEXTCOL, font_size="19sp", halign="left", valign="middle")
        t.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        header.add_widget(t)
        self.add_widget(header)

        sv = ScrollView()
        col = BoxLayout(orientation="vertical", size_hint_y=None, padding=[14, 14, 14, 20], spacing=14)
        col.bind(minimum_height=col.setter("height"))
        self.rate_lbl = Label(text="[color=9aa0c0]Loading live prices...[/color]", markup=True, font_size="14sp",
                              size_hint_y=None, height="44dp", halign="left", valign="middle")
        self.rate_lbl.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        col.add_widget(self.rate_lbl)
        grid = GridLayout(cols=2, spacing=12, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))
        tiles = [("Chat with Genius", None, GOLD), ("Talk (voice)", "talk", BLUE),
                 ("Genius Wealth", "wealth", GOLD), ("Read a trading chart", "chart", GOLD2),
                 ("Make music", "sound", BLUE2), ("Photo studio", "fun", BLUE),
                 ("Super zoom camera", "camera", BLUE2), ("Selfie camera", "selfie", GOLD2),
                 ("Genius Eye beauty", "genius eye", GOLD),
                 ("Genius Ultra photo", "ultra", BLUE),
                 ("My storage", "storage", GREY), ("Genius everywhere", "everywhere", GREY),
                 ("Share Genius", "share", GREY), ("My plan", "premium", GREY)]
        for label, act, c in tiles:
            b = RoundButton(text=label, bg=c, fg=(0.1, 0.08, 0.02, 1) if c in (GOLD, GOLD2) else TEXTCOL,
                            size_hint_y=None, height="88dp", font_size="16sp", bold=True)
            b.bind(on_press=lambda _b, a=act: self.go(a))
            grid.add_widget(b)
        col.add_widget(grid)
        col.add_widget(Label(text="Genius \u00b7 App built by Ssali", color=HINT, font_size="12sp",
                             size_hint_y=None, height="28dp"))
        sv.add_widget(col)
        self.add_widget(sv)
        threading.Thread(target=self._load_rates, daemon=True).start()

    def _load_rates(self):
        parts = []
        try:
            r = usd_rates()
            if r.get("UGX"):
                parts.append(f"$1 = UGX {r['UGX']:,.0f}")
        except Exception:
            pass
        try:
            c = crypto_price("btc")
            if c:
                parts.append(f"BTC ${c['usd']:,.0f}" + (f" ({c['chg']:+.1f}%)" if c.get("chg") is not None else ""))
        except Exception:
            pass
        txt = "   \u2022   ".join(parts) if parts else "Live prices need internet"
        Clock.schedule_once(lambda *_: setattr(self.rate_lbl, "text", f"[b][color=ffc84d]Live:[/color][/b] {txt}"), 0)

    def go(self, action):
        EVERYWHERE["pending"] = action
        self.app.open_chat()


class DecoyScreen(BoxLayout):
    """Looks like Genius, but holds nothing real. Logs everything, answers slowly, then exits."""
    def __init__(self, app, tried="", **kw):
        super().__init__(orientation="vertical", **kw)
        self.app = app
        add_gradient_bg(self)
        intruder_log("entered decoy", f"name={tried or '(blank)'}")
        header = Panel(bg=HEADER, radius=0, orientation="horizontal",
                       size_hint_y=None, height="60dp", padding=[18, 0, 18, 0])
        header.add_widget(Label(text="[b]Genius[/b]", markup=True, font_size="23sp", color=GOLD))
        self.add_widget(header)
        self.scroll = ScrollView()
        self.out = Label(text="[b][color=f2c033]AI[/color][/b]\nWelcome. Loading your data...\n\n",
                         markup=True, font_size="18sp", size_hint_y=None, halign="left",
                         valign="top", color=TEXTCOL, padding=(8, 8))
        self.out.bind(width=lambda *a: setattr(self.out, "text_size", (self.out.width, None)),
                      texture_size=lambda *a: setattr(self.out, "height", self.out.texture_size[1]))
        self.scroll.add_widget(self.out)
        self.add_widget(self.scroll)
        row = BoxLayout(size_hint_y=None, height="62dp", padding=8, spacing=8)
        self.inp = style_input(TextInput(hint_text="Type a command", multiline=False, font_size="18sp"))
        self.inp.bind(on_text_validate=self.send)
        b = RoundButton(text="Send", bg=GOLD, fg=(0.1, 0.1, 0.1, 1), size_hint_x=None, width="90dp")
        b.bind(on_press=self.send)
        row.add_widget(self.inp)
        row.add_widget(b)
        self.add_widget(row)
        Clock.schedule_once(lambda *_: self.app.build_login(), 180)   # kicked out after 3 min

    def show(self, text):
        self.out.text += f"[b][color=f2c033]AI[/color][/b]\n{text}\n\n"
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.1)

    def send(self, *_):
        t = self.inp.text.strip()
        self.inp.text = ""
        if not t:
            return
        self.out.text += f"[b][color=6fb7ff]You[/color][/b]\n{t}\n\n"
        intruder_log("decoy typed", t)
        a, _, arg = t.partition(" ")
        a = a.lower()
        trips = tripwires()
        if a == "notes":
            r = "\n".join(DECOY_NOTES)
        elif a == "secrets":
            r = "In your locker: " + ", ".join(trips.keys())
        elif a == "open" and arg.lower() in trips:
            intruder_log("TRIPWIRE opened", arg)
            r = f"{arg}: {trips[arg.lower()]}"
        elif a in ("money", "spent", "got"):
            r = "Money this week: in 0 UGX, out 0 UGX."
        elif a in ("backup", "restore", "setkey", "upgrade", "rollback", "security", "intruders"):
            r = "Syncing... please wait."
        else:
            r = random.choice(["Thinking...", "Network is slow. Try again.", "Loading...",
                               "I didn't get that. Type help."])
        delay = random.uniform(4, 9)                      # tarpit: waste their time
        Clock.schedule_once(lambda *_: self.show(r), delay)


# ===================== 112.4 Metal Finder =====================
# Uses the phone's own magnetic sensor (magnetometer). It notices iron and steel close to the phone
# and magnets. A coil detector (ESP32) can be joined over Wi-Fi to find all metals, deeper.
import math as _md_math

MD_FINDS = "metal_finds.json"
MD_COIL_URL = "http://192.168.4.1/data"
MD_GREEN = (0.30, 0.90, 0.55, 1)
MD_ORANGE = (1.0, 0.62, 0.20, 1)

MD_GUIDE = """[b]Metal Finder: what it can really do[/b]

[b]Phone sensor[/b] (built into many phones, not all)
- Finds [b]iron and steel[/b]: nails, screws, bolts, iron pipes, tins, tools, steel rods, and magnets.
- Range is short: a nail at about 2 to 5 cm, a hammer or bolt at about 5 to 10 cm, a big steel thing (gate, car) further.
- It can NOT see gold, silver, copper, aluminium or brass. They are not magnetic.
- The sensor sits near the TOP of most phones. Sweep with the top edge, low and slow.

[b]Coil detector[/b] (Genius + an ESP32 coil kit)
- A real detector coil sees ALL metals, gold and coins too.
- A 20 cm coil finds a coin at about 15 to 25 cm and bigger metal deeper.
- Genius shows its signal on this same screen. Join the Wi-Fi called Genius-Detector, then tap Coil detector.

[b]How to sweep well[/b]
1. Stand away from metal and tap Zero.
2. Hold the phone flat, top edge forward, 1 to 2 cm above the ground or wall.
3. Move slowly, about a hand's width per second, in straight lines.
4. When it beeps faster, go back and forth to find where the Peak is highest. That's the spot.

[b]Things that fool every detector[/b]
- Steel rods inside concrete walls and floors, iron roofing, water pipes and power cables.
- Your own phone case magnet, watch, rings, keys, belt buckle and shoe nails.
- Speakers and fridges (strong magnets).
Zero again whenever you move to a new place.

[b]Honesty promise[/b]
Genius never says "treasure" or "gold" from the phone sensor. It shows a real reading in uT (microtesla) and tells you how strong it is.

[b]The law in Uganda[/b]
Minerals like gold belong to the Government, and mining them needs a licence. Ask before digging on land that is not yours. Very old objects you find are history: report them to the Uganda Museum."""


class MetalBrain:
    """Turns raw sensor numbers into a steady, honest signal (no Kivy, so it can be tested)."""
    CAL_SAMPLES = 36

    def __init__(self, coil=False):
        self.coil = coil
        self.sens = 1.0          # 1.6 low, 1.0 normal, 0.6 high
        self.reset()

    def reset(self):
        self.cal = []
        self.base = None
        self.noise = 0.0
        self.ema = None
        self.peak = 0.0
        self.hist = []
        self.frozen_bias = None

    @property
    def calibrating(self):
        return self.base is None

    def thr(self):
        floor = 2.0 if self.coil else 1.5
        return max(3.0 * self.noise, floor) * self.sens

    def feed(self, vec, bias=None):
        """vec: (x, y, z) in uT (coil: (value, 0, 0)). Returns the change from normal in uT (0 while zeroing)."""
        if vec is None:
            return 0.0
        if bias is not None and not self.coil:
            if self.frozen_bias is None:
                self.frozen_bias = tuple(bias)
            vec = tuple(v - b for v, b in zip(vec, self.frozen_bias))
        m = abs(vec[0]) if self.coil else _md_math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
        self.ema = m if self.ema is None else 0.35 * m + 0.65 * self.ema
        if self.base is None:
            self.cal.append(m)
            if len(self.cal) >= self.CAL_SAMPLES:
                c = self.cal[6:]                     # skip the first wobble
                mean = sum(c) / len(c)
                self.base = mean
                self.noise = _md_math.sqrt(sum((x - mean) ** 2 for x in c) / len(c))
                self.ema = mean
            return 0.0
        d = abs(self.ema - self.base)
        if d < self.thr():                           # slow drift correction while nothing is found
            self.base += 0.003 * (self.ema - self.base)
        self.peak = max(self.peak, d)
        self.hist.append(d)
        if len(self.hist) > 160:
            self.hist.pop(0)
        return d

    def pct(self, d):
        t = self.thr()
        if d < t:
            return 0.0
        top = 400.0 if self.coil else 150.0
        return min(100.0, 100.0 * _md_math.log10(1 + (d - t) / 2.0) / _md_math.log10(1 + top / 2.0))

    def level(self, d):
        """(0..4, short title, explanation)"""
        t = self.thr()
        if d < t:
            return 0, "Nothing found", "No metal near the sensor. Keep sweeping slowly."
        if self.coil:
            p = self.pct(d)
            if p < 25:
                return 1, "Faint metal", "Small or deep metal. Go back and forth to find the strongest spot."
            if p < 55:
                return 2, "Metal", "Metal below the coil. Sweep a cross to pin it down."
            if p < 85:
                return 3, "Strong metal", "Big or shallow metal right under the coil."
            return 4, "Very strong", "Large metal very close to the coil."
        if d < 10:
            return 1, "Faint", "A small iron or steel piece close by, or a bigger one a little further."
        if d < 40:
            return 2, "Iron or steel close", "Something magnetic within a few cm. Move back and forth to find the Peak."
        if d < 200:
            return 3, "Strong iron or steel", "A big iron or steel object, or one very close to the top of the phone."
        return 4, "Magnet or large steel", "A magnet (speaker, phone case, fridge) or a large steel object right here."

    def trend(self):
        h = self.hist
        if len(h) < 12:
            return 0
        now = sum(h[-4:]) / 4
        before = sum(h[-12:-8]) / 4
        if now > before * 1.25 + 0.6:
            return 1
        if now < before * 0.8 - 0.6:
            return -1
        return 0


class _MagSource:
    """Live readings from the phone's magnetic sensor (or a coil detector over Wi-Fi)."""

    def __init__(self):
        self.ok = False
        self.kind = ""
        self.info = ""
        self.vec = None
        self.bias = None
        self.grav = None
        self.accuracy = 3
        self.count = 0
        self._sm = None
        self._lis = None
        self._plyer = None
        self._coil_on = False
        self.coil_err = ""

    def start_phone(self):
        try:
            from jnius import autoclass, cast, PythonJavaClass, java_method
        except Exception:
            return self._start_plyer()
        src = self

        class _MdListener(PythonJavaClass):
            __javainterfaces__ = ["android/hardware/SensorEventListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/hardware/SensorEvent;)V")
            def onSensorChanged(self, ev):
                try:
                    t = ev.sensor.getType()
                    v = ev.values
                    if t == 1:
                        src.grav = (v[0], v[1], v[2])
                    else:
                        src.vec = (v[0], v[1], v[2])
                        src.count += 1
                        if t == 14 and len(v) >= 6:
                            src.bias = (v[3], v[4], v[5])
                except Exception:
                    pass

            @java_method("(Landroid/hardware/Sensor;I)V")
            def onAccuracyChanged(self, sensor, acc):
                src.accuracy = acc

        try:
            PA = autoclass("org.kivy.android.PythonActivity")
            Ctx = autoclass("android.content.Context")
            sm = cast("android.hardware.SensorManager", PA.mActivity.getSystemService(Ctx.SENSOR_SERVICE))
            s = sm.getDefaultSensor(14)                  # raw sensor: Android can't "auto-correct" a find away
            kind = "raw"
            if s is None:
                s = sm.getDefaultSensor(2)
                kind = "calibrated"
            self._sm = sm
            self._lis = _MdListener()
            acc = sm.getDefaultSensor(1)
            if acc is not None:
                sm.registerListener(self._lis, acc, 2)
            if s is None:
                self.ok = False
                return False
            sm.registerListener(self._lis, s, 1)
            self.ok, self.kind = True, kind
            try:
                self.info = f"{s.getName()} ({s.getVendor()}), up to {s.getMaximumRange():.0f} uT"
            except Exception:
                self.info = "Phone magnetic sensor"
            log(f"METAL: sensor {kind} {self.info}")
            return True
        except Exception as e:
            log(f"METAL: sensor start failed: {type(e).__name__}: {e}")
            return self._start_plyer()

    def _start_plyer(self):
        try:
            from plyer import compass
            compass.enable()
            self._plyer = compass
            self.ok, self.kind, self.info = True, "plyer", "Phone magnetic sensor"
            return True
        except Exception:
            self.ok = False
            return False

    def poll(self):
        if self._plyer is not None:
            try:
                f = self._plyer.field
                if f and f[0] is not None:
                    self.vec = (f[0], f[1], f[2])
                    self.count += 1
            except Exception:
                pass

    def start_coil(self, url=MD_COIL_URL):
        self._coil_on = True
        self.kind, self.info, self.ok = "coil", "Coil detector on Wi-Fi Genius-Detector", True

        def run():
            fails = 0
            while self._coil_on:
                try:
                    with urllib.request.urlopen(url, timeout=1.5) as r:
                        d = json.loads(r.read().decode("utf-8", "ignore"))
                    self.vec = (float(d.get("v", 0)), 0.0, 0.0)
                    self.count += 1
                    self.coil_err = ""
                    fails = 0
                    time.sleep(0.06)
                except Exception as e:
                    fails += 1
                    self.coil_err = ("Can't reach the coil detector. Join the Wi-Fi Genius-Detector, "
                                     "and turn mobile data off if it still can't connect.")
                    time.sleep(0.5 if fails < 10 else 1.5)
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        self._coil_on = False
        try:
            if self._sm is not None and self._lis is not None:
                self._sm.unregisterListener(self._lis)
        except Exception:
            pass
        try:
            if self._plyer is not None:
                self._plyer.disable()
        except Exception:
            pass
        self._sm = self._lis = self._plyer = None


class _MdBeeper:
    def __init__(self):
        self.tg = None
        try:
            from jnius import autoclass
            TG = autoclass("android.media.ToneGenerator")
            self.tg = TG(3, 85)                      # music stream, 85% volume
            self.tone = TG.TONE_PROP_BEEP
        except Exception:
            self.tg = None

    def beep(self, ms=45):
        try:
            if self.tg is not None:
                self.tg.startTone(self.tone, ms)
        except Exception:
            pass

    def release(self):
        try:
            if self.tg is not None:
                self.tg.release()
        except Exception:
            pass
        self.tg = None


def md_finds_load():
    try:
        return json.load(open(MD_FINDS))
    except Exception:
        return []


def md_finds_save(lst):
    try:
        json.dump(lst[-200:], open(MD_FINDS, "w"))
    except Exception as e:
        log(f"METAL: save failed {e}")


class _MdGauge(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.pct, self.col = 0.0, MD_GREEN
        self.big = Label(text="--", font_size="44sp", bold=True, color=TEXTCOL, markup=True)
        self.small = Label(text="uT", font_size="15sp", color=HINT)
        self.add_widget(self.big)
        self.add_widget(self.small)
        self.bind(pos=self.draw, size=self.draw)

    def set(self, pct, col, big, small):
        self.pct, self.col = pct, col
        self.big.text, self.small.text = big, small
        self.draw()

    def draw(self, *_):
        cx, cy = self.center_x, self.center_y
        r = min(self.width, self.height) / 2 - dp(14)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(1, 1, 1, 0.10)
            Line(circle=(cx, cy, r, -135, 135), width=dp(9), cap="round")
            if self.pct > 0.5:
                Color(*self.col)
                Line(circle=(cx, cy, r, -135, -135 + 270 * self.pct / 100.0), width=dp(9), cap="round")
                Color(self.col[0], self.col[1], self.col[2], 0.18)
                Line(circle=(cx, cy, r + dp(10), -135, -135 + 270 * self.pct / 100.0), width=dp(4), cap="round")
        self.big.size = (self.width, dp(60))
        self.big.center = (cx, cy + dp(8))
        self.small.size = (self.width, dp(24))
        self.small.center = (cx, cy - dp(30))


class _MdGraph(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=lambda *_: self.draw([], 1), size=lambda *_: self.draw([], 1))

    def draw(self, hist, thr):
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            if not hist:
                return
            top = max(max(hist), thr * 4, 5.0)
            ty = self.y + dp(6) + (self.height - dp(12)) * min(1.0, thr / top)
            Color(1, 1, 1, 0.25)
            Line(points=[self.x + dp(6), ty, self.right - dp(6), ty], width=1, dash_length=6, dash_offset=4)
            pts = []
            n = len(hist)
            for i, v in enumerate(hist):
                pts += [self.x + dp(6) + (self.width - dp(12)) * i / max(1, 159),
                        self.y + dp(6) + (self.height - dp(12)) * min(1.0, v / top)]
            Color(*GOLD)
            if len(pts) >= 4:
                Line(points=pts, width=dp(1.6))


def _md_close_all(st):
    st["open"] = False
    for ev in (st.get("tick"), st.get("beep_ev")):
        try:
            ev.cancel()
        except Exception:
            pass
    try:
        st["src"].stop()
    except Exception:
        pass
    try:
        st["beeper"].release()
    except Exception:
        pass


def metal_finder(screen, coil=False):
    """Full-screen Metal Finder."""
    src = _MagSource()
    started = src.start_coil() or True if coil else src.start_phone()
    root = BoxLayout(orientation="vertical", spacing=dp(6), padding=[dp(8), dp(6)])
    pop = Popup(title="Metal Finder" + (" - coil" if coil else ""), content=root, size_hint=(1, 1),
                separator_color=GOLD, title_color=GOLD, title_size="20sp")
    st = {"open": True, "src": src}

    def btn(text, col, fn, **kw):
        b = RoundButton(text=text, bg=col, fg=(0.1, 0.1, 0.1, 1) if col in (GOLD, MD_GREEN) else TEXTCOL,
                        font_size="15sp", bold=True, **kw)
        b.bind(on_press=lambda *_: fn())
        return b

    def reopen(c):
        pop.dismiss()
        Clock.schedule_once(lambda *_: metal_finder(screen, coil=c), 0.2)

    if not started:
        msg = Label(text="[b]This phone has no magnetic sensor.[/b]\n\nMany budget phones are made without one "
                         "(it's the part a compass app uses), so Genius can't sense metal with this phone alone.\n\n"
                         "You can still find metal with a [b]coil detector[/b]: a small ESP32 kit with a coil that "
                         "sends its signal to Genius over Wi-Fi. A coil finds ALL metals, gold and coins too, "
                         "and much deeper than any phone.",
                    markup=True, color=TEXTCOL, font_size="16sp", halign="center", valign="middle")
        msg.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - dp(10), None)))
        root.add_widget(msg)
        row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        row.add_widget(btn("Coil detector", GOLD, lambda: reopen(True)))
        row.add_widget(btn("Guide", BLUE, lambda: screen.show("AI", MD_GUIDE)))
        root.add_widget(row)
        root.add_widget(btn("Close", GREY, pop.dismiss, size_hint_y=None, height=dp(50)))
        pop.bind(on_dismiss=lambda *_: _md_close_all(st))
        pop.open()
        log("METAL: no magnetometer on this phone")
        return

    brain = MetalBrain(coil=coil)
    beeper = _MdBeeper()
    st.update(brain=brain, beeper=beeper, sound=True, lvl=0, rate=0.0, grav0=None)

    status = Label(text=src.info, color=HINT, font_size="13sp", size_hint_y=None, height=dp(22))
    root.add_widget(status)
    gauge = _MdGauge(size_hint_y=None, height=dp(230))
    root.add_widget(gauge)
    title = Label(text="Zeroing...", markup=True, color=GOLD, font_size="22sp", bold=True,
                  size_hint_y=None, height=dp(34))
    root.add_widget(title)
    expl = Label(text="Hold still, away from metal.", color=TEXTCOL, font_size="15sp",
                 halign="center", valign="middle", size_hint_y=None, height=dp(46))
    expl.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - dp(10), None)))
    root.add_widget(expl)
    trend = Label(text="", markup=True, color=HINT, font_size="15sp", size_hint_y=None, height=dp(26))
    root.add_widget(trend)
    graph = _MdGraph(size_hint_y=None, height=dp(96))
    root.add_widget(graph)

    sens_names = {1.6: "Low", 1.0: "Normal", 0.6: "High"}

    def do_zero():
        brain.reset()
        st["grav0"] = src.grav
        beeper.beep(30)

    def toggle_sound():
        st["sound"] = not st["sound"]
        b_sound.text = "Sound: " + ("on" if st["sound"] else "off")

    def cycle_sens():
        order = [1.0, 0.6, 1.6]
        brain.sens = order[(order.index(brain.sens) + 1) % 3]
        b_sens.text = "Sensitivity: " + sens_names[brain.sens]

    def save_spot():
        if brain.calibrating or not brain.hist:
            screen.say("Let it finish zeroing, then find a spot first.")
            return
        d = brain.hist[-1]
        lvl = brain.level(d)
        lst = md_finds_load()
        lst.append({"t": time.strftime("%Y-%m-%d %H:%M"), "uT": round(d, 1), "peak": round(brain.peak, 1),
                    "what": lvl[1], "coil": coil})
        md_finds_save(lst)
        beeper.beep(120)
        title.text = "Spot saved"

    def show_finds():
        lst = md_finds_load()
        if not lst:
            screen.show("AI", "No saved spots yet. When the finder beeps, tap Save spot.")
            return
        lines = [f"{i + 1}. {f['t']}  {f['what']}  ({f['uT']} uT, peak {f['peak']}){'  coil' if f.get('coil') else ''}"
                 for i, f in enumerate(lst[-30:])]
        screen.show("AI", "[b]My metal spots[/b]\n" + "\n".join(lines) + "\n\nSay 'metal clear' to delete them.")

    row1 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
    row1.add_widget(btn("Zero", GOLD, do_zero))
    b_sound = btn("Sound: on", BLUE, toggle_sound)
    row1.add_widget(b_sound)
    b_sens = btn("Sensitivity: Normal", BLUE, cycle_sens)
    row1.add_widget(b_sens)
    root.add_widget(row1)
    row2 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
    row2.add_widget(btn("Save spot", MD_GREEN, save_spot))
    row2.add_widget(btn("My spots", GREY, show_finds))
    row2.add_widget(btn("Guide", GREY, lambda: screen.show("AI", MD_GUIDE)))
    root.add_widget(row2)
    row3 = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
    row3.add_widget(btn("Phone sensor" if coil else "Coil detector", GREY, lambda: reopen(not coil)))
    row3.add_widget(btn("Close", RED, pop.dismiss))
    root.add_widget(row3)

    def tick(dt):
        if not st["open"]:
            return False
        src.poll()
        if coil and src.coil_err and src.count == 0:
            title.text = "Waiting for the coil"
            expl.text = src.coil_err
            return
        if src.vec is None:
            if src.count == 0 and time.time() - st.setdefault("t0", time.time()) > 4:
                title.text = "No readings"
                expl.text = ("No numbers from a magnetic sensor. This phone most likely doesn't have one "
                             "(many budget phones don't). Use Coil detector instead.")
            return
        d = brain.feed(src.vec, src.bias if src.kind == "raw" else None)
        if brain.calibrating:
            gauge.set(0, MD_GREEN, "--", "zeroing")
            title.text = "Zeroing..."
            expl.text = "Hold still, away from metal."
            if st["grav0"] is None:
                st["grav0"] = src.grav
            return
        p = brain.pct(d)
        lvl, head, words = brain.level(d)
        col = [MD_GREEN, MD_GREEN, GOLD, MD_ORANGE, RED][lvl]
        gauge.set(p, col, f"{d:.1f}" if d < 100 else f"{d:.0f}",
                  ("signal" if coil else "uT change") + f"  |  {p:.0f}%")
        title.text = head
        title.color = col if lvl else HINT
        expl.text = words
        tr = brain.trend()
        arrow = "[color=7CFFA0]Stronger: keep going this way[/color]" if tr > 0 else \
            ("[color=FF9F5A]Weaker: go back[/color]" if tr < 0 and lvl else "")
        pk = f"Peak {brain.peak:.1f}" + ("" if coil else " uT")
        trend.text = (arrow + "   " if arrow else "") + pk
        if src.kind == "calibrated" and src.accuracy == 0:
            status.text = "Sensor needs calibrating: wave the phone in a figure 8, then tap Zero"
        elif not coil and st["grav0"] and src.grav:
            a, b = st["grav0"], src.grav
            na = _md_math.sqrt(sum(x * x for x in a)) or 1
            nb = _md_math.sqrt(sum(x * x for x in b)) or 1
            cos = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (na * nb)))
            status.text = ("Phone turned a lot: tap Zero again for a true reading"
                           if _md_math.degrees(_md_math.acos(cos)) > 35 else src.info)
        if lvl >= 3 and st["lvl"] < 3:
            try:
                from plyer import vibrator
                vibrator.vibrate(0.12)
            except Exception:
                pass
        st["lvl"] = lvl
        st["rate"] = [0, 0.55, 0.28, 0.13, 0.07][lvl]
        st["n"] = st.get("n", 0) + 1
        if st["n"] % 3 == 0:                 # 112.5: keep the graph moving after it fills up
            graph.draw(brain.hist, brain.thr())

    def beep_loop(dt):
        if not st["open"]:
            return False
        r = st["rate"]
        now = time.time()
        if st["sound"] and r and now - st.get("last_beep", 0) >= r:
            st["last_beep"] = now
            beeper.beep(35 if r > 0.1 else 25)

    st["tick"] = Clock.schedule_interval(tick, 1 / 15.0)
    st["beep_ev"] = Clock.schedule_interval(beep_loop, 0.03)
    pop.bind(on_dismiss=lambda *_: _md_close_all(st))
    pop.open()


def metal_handle(screen, line, action, arg, low):
    lw = low.strip(" .!?")
    words = ("metal detector", "metal finder", "detect metal", "find metal", "treasure", "find gold",
             "detect gold", "gold detector", "coil detector", "tressure")
    if action in ("metal", "detector", "metaldetector", "treasure", "tressure", "finder", "coil") or \
            any(w in lw for w in words) and len(lw.split()) <= 6:
        a = arg.lower().strip()
        if a in ("guide", "help", "how", "info") or lw in ("metal guide",):
            screen.show("AI", MD_GUIDE)
            return True
        if a in ("spots", "finds", "list"):
            lst = md_finds_load()
            screen.show("AI", "[b]My metal spots[/b]\n" + ("\n".join(
                f"{i + 1}. {f['t']}  {f['what']}  ({f['uT']} uT)" for i, f in enumerate(lst[-30:])) or "None yet."))
            return True
        if a in ("clear", "delete", "reset"):
            md_finds_save([])
            screen.say("Deleted your saved metal spots.")
            return True
        use_coil = action == "coil" or "coil" in lw
        if ("gold" in lw or "treasure" in lw or "tressure" in lw) and not use_coil:
            screen.show("AI", "Opening the Metal Finder. Honest note: the phone sensor finds iron, steel and "
                              "magnets close by. For gold and coins you need the coil detector (see Guide).")
        Clock.schedule_once(lambda *_: metal_finder(screen, coil=use_coil), 0.1)
        return True
    return False
# =================== end Metal Finder ===================


class GeniusApp(App):
    title = "Genius"

    def build(self):
        self.root_box = BoxLayout()
        # doodle wallpaper behind every screen (cover-fit, keeps aspect)
        bgp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bg.jpg")
        if os.path.exists(bgp):
            try:
                from kivy.core.image import Image as CoreImage
                tex = CoreImage(bgp).texture
                with self.root_box.canvas.before:
                    Color(1, 1, 1, 1)
                    self._bg = Rectangle(texture=tex)
                def _fit(w, *_):
                    tw, th = tex.size
                    sc = max(w.width / float(tw), w.height / float(th))
                    dw, dh = tw * sc, th * sc
                    self._bg.size = (dw, dh)
                    self._bg.pos = (w.x + (w.width - dw) / 2.0, w.y + (w.height - dh) / 2.0)
                self.root_box.bind(size=_fit, pos=_fit)
            except Exception:
                pass
        self.root_box.add_widget(CodeScreen(self))
        return self.root_box

    def open_account_login(self):
        self.root_box.clear_widgets()
        self.root_box.add_widget(LoginScreen(self))

    def build_login(self):
        self.chat = None
        safe(bubble_hide)
        try:
            switch_user(OWNER)          # leave the guest's space; next sign-in picks the account
        except Exception:
            pass
        self.root_box.clear_widgets()
        self.root_box.add_widget(CodeScreen(self))

    def open_decoy(self, tried=""):
        self.root_box.clear_widgets()
        self.root_box.add_widget(DecoyScreen(self, tried))

    def on_start(self):
        live_started_ok()
        everywhere_load()
        threading.Thread(target=lambda: brain_self_review(), daemon=True).start()
        threading.Thread(target=lambda: (time.sleep(60), daily_problem_report()), daemon=True).start()
        def check_update():
            # Auto-update: after unlock, then every 6 hours, Genius fetches the new
            # version by itself and opens Android's Update screen (one tap).
            if PLAY_BUILD:
                return                     # the Play Store updates this build
            while getattr(self, "chat", None) is None:
                time.sleep(5)              # wait until the owner has unlocked Genius
            first = True
            while True:
                if first or update_due():
                    first = False
                    if fetch_live_update() != "apk":
                        time.sleep(3600)
                        continue
                    found, _ = online_update()
                    if found and _vt(found[0]) > _vt(SHIP_VERSION) and CURRENT.get("owner"):
                        def tell(t):
                            def go(*_):
                                chat = getattr(self, "chat", None)
                                if chat is not None:
                                    chat.say(t)
                                else:
                                    Clock.schedule_once(go, 5)
                            Clock.schedule_once(go, 1)
                        install_online_update(found[0], found[1], tell)
                time.sleep(3600)
        threading.Thread(target=check_update, daemon=True).start()
        EVERYWHERE["pending"] = intent_action()
        try:
            from android import activity
            activity.bind(on_new_intent=self._new_intent)
        except Exception:
            pass

    def _new_intent(self, intent):
        a = intent_action(intent)
        chat = getattr(self, "chat", None)
        if a and chat is not None:
            Clock.schedule_once(lambda *_: chat.run_action(a), 0.5)
        elif a:
            EVERYWHERE["pending"] = a

    def on_pause(self):
        if getattr(self, "chat", None) is not None:
            safe(bubble_show)
        return True

    def on_resume(self):
        safe(bubble_hide)

    def open_home(self):
        if EVERYWHERE.get("pending"):
            return self.open_chat()
        self.root_box.clear_widgets()
        self.chat = None
        self.root_box.add_widget(HomeScreen(self))

    def open_chat(self):
        self.root_box.clear_widgets()
        chat = ChatScreen(self)
        self.chat = chat
        self.root_box.add_widget(chat)
        if EVERYWHERE.get("pending"):
            a, EVERYWHERE["pending"] = EVERYWHERE["pending"], None
            Clock.schedule_once(lambda *_: chat.run_action(a), 0.6)
        Clock.schedule_once(lambda *_: chat.life_start(), 2)
        Clock.schedule_once(lambda *_: chat.security_alert(), 1)


if __name__ == "__main__":
    GeniusApp().run()
