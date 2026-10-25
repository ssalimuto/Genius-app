# my_ai_app.py - private phone AI with buttons and voice (Kivy). Owner ssalimuto, plus private guest accounts.
import os, re, ssl, json, time, base64, hashlib, hmac, socket, threading, random, urllib.request, urllib.error, urllib.parse
from types import MappingProxyType

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
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle

Window.softinput_mode = "below_target"   # keyboard doesn't cover the text box

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


def add_gradient_bg(widget, top=BG_TOP, bottom=BG_BOT):
    """Paint a smooth gradient plus soft glowing orbs behind a whole screen."""
    with widget.canvas.before:
        Color(1, 1, 1, 1)
        r = Rectangle(texture=gradient_texture(top, bottom))
        Color(0.62, 0.30, 0.98, 0.10)
        from kivy.graphics import Ellipse
        o1 = Ellipse()
        Color(1.0, 0.70, 0.25, 0.07)
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
    background_color: 0.07, 0.065, 0.15, 0.97
    title_size: "19sp"
    title_align: "center"
    separator_height: "2dp"
<ModalView>:
    overlay_color: 0.01, 0.01, 0.04, 0.72
''')

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
    "setkey": "setkey YOURKEY - lets me answer anything",
    "help": "List commands",
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
    "rollback": "Go back to the previous Genius version",
    "security": "Security status: firewall, decoy, intruders, tampering",
    "intruders": "See who tried to break in",
    "tripwire": "Add a fake secret that traps hackers, e.g. tripwire momo_pin",
    "deep": "Turn deep thinking + web search on or off",
    "stop": "Shut down",
})
LIFE_ACTIONS = ("life", "study", "subjects", "exam", "quiz", "explain", "studyplan",
                "spent", "got", "money", "goal", "put", "brief",
                "freelance", "skills", "cv", "proposal", "gigs", "price",
                "build", "myapps", "showapp", "hotspot", "makeai", "myais", "ask", "backup")
NEEDS_APPROVAL = ("vibrate", "notify", "remind", "runapp", "restore")
OWNER_ONLY = ("upgrade", "rollback", "security", "intruders", "tripwire", "restore")
NEW_ACTIONS = ("solve", "problems", "step", "know", "knowledge", "upgrade", "rollback",
               "security", "intruders", "tripwire")
ABOUT_TEXT = """Genius 102.0
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

Safety
- Only the owner can log in. Wrong passwords lock it for longer each time (5 min, 15 min, 1 hour).
- Distraction firewall: an intruder is sent to a fake decoy Genius with fake data and slow replies.
- Tripwires and an intruder log tell you when someone tried to break in.
- A tamper check warns you if the code was changed.
- Your API keys stay on this phone. Never share them.
- A watcher blocks dangerous actions (copying itself, deleting files, turning off stop).
- 'stop' always shuts me down.

Limits
- I only listen while the app is open and the screen is on.
- I need internet for Gemini, weather, web search, and Google speech.
- Gemini can make mistakes. Check anything important."""

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

VERSION = "102.0"
VERSION_DATE = "2026-10-25"
CHANGELOG = """Genius 102.0 Doodle (2026-10-25)
- New look: dark doodle wallpaper of game icons behind every screen
- Picture chat like Gemini: after a picture, say 'make me near a building', 'change it to night'
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
- Better photos: golden light, blurred background, natural pose, and Gemini's newest picture model

Genius 101.0 Guardian (2026-10-24)
- Drawing fixed: if Gemini's free plan can't draw, Genius uses a free picture maker instead
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
- Many AIs: Gemini + Groq (very fast) + OpenRouter (many models)
- Turbo mode: simple questions go to the fastest AI
- Instant repeat answers (remembers answers to the same question)
- Backup AI: if Gemini fails, another AI answers
- askall: ask every AI at once and compare (fastest first)
- ais: see which AIs are connected
- think: several AIs answer, then Genius cross-checks them into one best answer
- Study, freelance and builder tools work with any connected AI, not only Gemini

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
- Chat with Gemini (fast and deep), tools, memory, notes, reminders
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
        for dp, _, fs in os.walk(genius_dl()):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
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
    from kivy.core.audio import SoundLoader
    if _luganda["sound"] is not None:
        try:
            _luganda["sound"].stop()
        except Exception:
            pass
    snd = SoundLoader.load(path)
    if snd:
        _luganda["sound"] = snd
        snd.play()


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


def clean_key(text):
    """Pull the real key out of whatever was pasted (even a whole curl command)."""
    m = re.search(r"(AQ\.[A-Za-z0-9_\-]+|AIza[A-Za-z0-9_\-]{20,})", text)
    return m.group(1) if m else text.strip().strip("'\"")


def ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


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


IMAGE_MODELS = ("gemini-2.5-flash-image", "gemini-3-pro-image-preview", "gemini-2.5-flash-image-preview",
                "gemini-2.0-flash-preview-image-generation")
# Nano Banana = gemini-2.5-flash-image, Nano Banana Pro = gemini-3-pro-image-preview (sharper, more realistic)
BANANA = {"pro": False, "aspect": ""}


def image_models():
    if BANANA["pro"]:
        return ("gemini-3-pro-image-preview",) + tuple(m for m in IMAGE_MODELS if m != "gemini-3-pro-image-preview")
    return IMAGE_MODELS


def free_image(prompt, tries=3):
    """Free picture maker (Pollinations, no key). Busy at times, so it retries."""
    q = urllib.parse.quote(prompt[:900])
    url = f"https://image.pollinations.ai/prompt/{q}?width=640&height=896&nologo=true&enhance=false&seed={random.randint(1, 99999)}"
    last = "The free picture maker is busy. Try again in a minute."
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Genius/101"})
            try:
                r = urllib.request.urlopen(req, timeout=90, context=ssl_context())
            except urllib.error.URLError as e:
                if "CERTIFICATE" not in str(e).upper():
                    raise
                r = urllib.request.urlopen(req, timeout=90, context=ssl._create_unverified_context())
            with r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
            if ctype.startswith("image") and len(data) > 2000:
                name = f"drawing_{int(time.time())}.jpg"
                with open(name, "wb") as f:
                    f.write(data)
                return os.path.abspath(name), None
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return None, "The picture maker refused that description. Try different words."
        except Exception:
            last = "Your internet is too slow for drawing right now. Try better signal."
        time.sleep(11)
    return None, last


NOT_REAL_WORDS = ("cartoon", "anime", "manga", "comic", "illustration", "illustrated", "drawing",
                  "drawn", "sketch", "painting", "painted", "clipart", "clip art", "3d render",
                  "render", "pixar", "disney", "chibi", "vector", "emoji", "doodle")
PHOTO_STYLE = ("real photograph, candid smartphone photo, photorealistic, real human skin texture with pores, "
               "natural African skin tones, true-to-life colours, natural daylight, sharp focus on the face, "
               "shallow depth of field, real background, 35mm lens, high detail, unedited, "
               "not a cartoon, not an illustration, not a painting, not 3D")


def realistic_prompt(prompt):
    """Always photo-real: remove cartoon words, add camera detail, and let an AI describe the scene like a photographer."""
    p = prompt
    for w in NOT_REAL_WORDS:
        p = re.sub(r"\b" + re.escape(w) + r"s?\b", "", p, flags=re.I)
    p = re.sub(r"\s+", " ", p).strip(" ,.") or "a person"
    try:
        better = ask_gemini(
            "Rewrite this as ONE vivid description of a REAL photograph (max 60 words): who or what is in it, "
            "their face and expression, clothes, the real place behind them (for Uganda use real places like "
            "brick walls, red soil, markets), the light and the camera angle. No cartoon or art words. "
            "Only the description.\n\nRequest: " + p, max_tokens=150)
        if better and 15 < len(better) < 600 and "couldn" not in better.lower() and "no ai" not in better.lower():
            p = better.strip().strip('"')
            for w in NOT_REAL_WORDS:
                p = re.sub(r"\b" + re.escape(w) + r"s?\b", "", p, flags=re.I)
    except Exception:
        pass
    return p + ". " + PHOTO_STYLE


ME_WORDS = re.compile(r"\b(me|my face|myself|my photo|like me|of me)\b", re.I)


def genius_dl(sub=""):
    """Download/Genius for the owner, Download/Genius/users/<name> for other accounts."""
    base = "/storage/emulated/0/Download/Genius" if os.path.isdir("/storage/emulated/0") else os.path.join(ROOT, "genius_files")
    if not CURRENT["owner"]:
        base = os.path.join(base, "users", CURRENT["name"])
    d = os.path.join(base, sub) if sub else base
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.abspath(sub or ".")
        os.makedirs(d, exist_ok=True)
    return d


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
    d = genius_dl()
    out = os.path.join(d, "me.png" if src.lower().endswith(".png") else "me.jpg")
    for n in ("me.jpg", "me.jpeg", "me.png"):
        try:
            os.remove(os.path.join(d, n))
        except Exception:
            pass
    with open(src, "rb") as a, open(out, "wb") as b:
        b.write(a.read())
    return out


def my_photo():
    """The user's own reference photo: Download/Genius/me.jpg (or .png)."""
    for d in (genius_dl(), "."):
        for n in ("me.jpg", "me.jpeg", "me.png"):
            f = os.path.join(d, n)
            if os.path.exists(f):
                return f
    return None


def gemini_image(prompt):
    """Draw a REAL-looking picture: Gemini first, then the free picture maker. Never cartoons.
    If the request is about the user ("draw me...") and me.jpg exists, the SAME face is kept."""
    ref = my_photo() if ME_WORDS.search(prompt) else None
    if ref:
        path, err = _gemini_image(prompt, ref)
        if path:
            return path, None
        return None, ("To keep YOUR face I need Gemini picture access (" + str(err) + "). "
                      "The free maker can't copy a real face, it only invents new people. "
                      "Add billing to your Gemini key at aistudio.google.com, then try again.")
    real = realistic_prompt(prompt)
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
        and os.path.exists(LAST_IMAGE["path"]) and bool(EDIT_START.match(low.strip()))


def blend_images(paths, instruction):
    path, err = _gemini_image(instruction, blend=paths)
    return path, (None if path else err)


def edit_image(instruction):
    """Change the last picture the way Gemini does: same person, only what was asked changes."""
    base = LAST_IMAGE["path"]
    path, err = _gemini_image(instruction, edit=base)
    if path:
        return path, None
    log(f"EDIT: Gemini couldn't ({err}); not redrawing, so the face and position never change")
    return None, ("I couldn't edit it without changing how you look, so I left your picture as it is. "
                  f"({err}) True editing needs Nano Banana: turn on billing for your key at aistudio.google.com, "
                  "or try again later. Instant looks and effects in Fun studio always keep your picture the same.")


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
                    name = f"drawing_{int(time.time())}.png"
                    with open(name, "wb") as f:
                        f.write(base64.b64decode(data["data"]))
                    return os.path.abspath(name), None
            last = "The model sent no picture. Try a simpler description."
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return None, "Google rejected the key. Use setkey again."
            if e.code == 404:
                last = "Drawing isn't on this key's free plan yet."
                continue
            if e.code == 429:
                last = "Free drawing limit reached. Wait a while and try again."
            else:
                last = "Google is busy. Try again shortly."
            continue
        except Exception:
            last = "Your internet is too slow for drawing right now. Try better signal."
            continue
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
                    return None, "Google rejected the key. Copy only the key and use setkey again.", True
                if e.code == 429:
                    err = "Free limit reached for now. Wait a minute and ask again."
                    break                  # next model won't help the quota
                if e.code in (500, 503) and attempt == 0:
                    time.sleep(2)
                    continue               # busy: retry same model once
                err = "Google is busy right now. Ask again in a moment."
                break                      # try next model
            except Exception:
                err = ("Your internet is slow right now. Move to better signal, "
                       "or turn data off and on, then ask again.")
                break                      # try next (lighter) model
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
               "did not confirm.")

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
            d = _post_gemini(key, model, payload, 60)
            parts = d["candidates"][0]["content"]["parts"]
            t = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if t:
                return t
        except Exception:
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
                rules = AGENT_RULES + ("\nWhat you know about your owner (use it to personalise answers):\n" + me if me else "")
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
                return None, "Google rejected the key. Copy only the key and use setkey again."
            if e.code == 429:
                err = "Free limit reached for now. Wait a minute and ask again."
            continue
        except Exception:
            err = ("Your internet is slow right now. Move to better signal, "
                   "or turn data off and on, then ask again.")
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
            d = _post_gemini(key, model, payload, 60)
            parts = d["candidates"][0]["content"]["parts"]
            t = "\n".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if t:
                return t
        except Exception:
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
        q = json.loads(raw)
        if len(q["o"]) == 4 and q["a"] in "ABCD":
            return q
    except Exception:
        pass
    return dict(random.choice(OFFLINE_QUIZ))


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
    return ask_gemini(question, 900, system=bot["prompt"]) or "I couldn't reach Gemini. Try again."


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
}
_model_cache = {}
_answer_cache = {}


def provider_key(name):
    f = PROVIDERS[name]["file"]
    return clean_key(open(f).read()) if os.path.exists(f) else None


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


def other_ai(name, text, system=None, convo=None, max_tokens=700):
    """Ask Groq or OpenRouter. Returns text or None."""
    key = provider_key(name)
    if not key:
        return None
    msgs = [{"role": "system", "content": system or (
        "You are Genius, the private assistant of " + CURRENT["name"] + ", a young person in Uganda, made by "
        "Ssali Muto. Answer in clear, simple English, briefly and accurately. Say when you are "
        "unsure. You can't see the time, weather or internet in this mode.")}]
    for m in (convo or [])[-8:]:
        t = " ".join(p.get("text", "") for p in m.get("parts", []))
        if t:
            msgs.append({"role": "assistant" if m["role"] == "model" else "user", "content": t})
    msgs.append({"role": "user", "content": text})
    for attempt in range(2):
        try:
            model = pick_model(name, key)
            d = _http_json(PROVIDERS[name]["base"] + "/chat/completions", key,
                           {"model": model, "messages": msgs, "max_tokens": max_tokens,
                            "temperature": 0.6}, timeout=40)
            return d["choices"][0]["message"]["content"].strip()
        except Exception as e:
            log(f"{name} failed: {e}")
            _model_cache.pop(name, None)       # maybe the model was retired; re-pick once
    return None


def connected_ais():
    out = []
    if os.path.exists(KEY_FILE):
        out.append("gemini")
    out += [n for n in PROVIDERS if provider_key(n)]
    return out


TOOL_WORDS = ("weather", "remind", "note", "time", "date", "battery", "draw", "picture",
              "search", "news", "today", "latest", "price", "spent", "money", "exam", "study",
              "remember", "calculate", "rain", "who won", "current", "now")


def needs_tools(text):
    t = text.lower()
    return any(w in t for w in TOOL_WORDS)


def ask_all(question):
    """Ask every connected AI at the same time and return all answers."""
    jobs = {"Gemini": lambda: _ask_gemini_only(question, 500),
            "Groq": lambda: other_ai("groq", question, max_tokens=500),
            "OpenRouter": lambda: other_ai("openrouter", question, max_tokens=500)}
    have = connected_ais()
    jobs = {k: v for k, v in jobs.items() if k.lower() in have}
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
        return "No AIs connected. Use setkey (Gemini), setgroq or setrouter."
    return "\n\n".join(f"[b]{k}[/b] ({sec:.1f}s)\n{r}" for k, (r, sec) in
                       sorted(results.items(), key=lambda x: x[1][1]))


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
FUN_STYLES = ("Black & white", "Vintage", "Pencil sketch", "Vivid colours", "Soft glow",
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
import math as _m, random as _r, struct as _st, wave as _wave

SR = 22050
_NOTE = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5, "F#": 6, "GB": 6,
         "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}
_SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}
_STYLES = {
    "afrobeat":  dict(bpm=104, drums="afro", inst=["epiano", "bass", "pluck", "pad", "shaker"], prog=[6, 4, 1, 5], scale="minor"),
    "amapiano":  dict(bpm=112, drums="amapiano", inst=["epiano", "logdrum", "pad", "shaker"], prog=[2, 5, 1, 6], scale="minor"),
    "pop":       dict(bpm=110, drums="pop", inst=["piano", "bass", "pad", "pluck"], prog=[1, 5, 6, 4], scale="major"),
    "lofi":      dict(bpm=78, drums="lofi", inst=["epiano", "bass", "pad"], prog=[2, 5, 1, 6], scale="major"),
    "gospel":    dict(bpm=76, drums="halftime", inst=["piano", "strings", "bass"], prog=[1, 4, 6, 5], scale="major"),
    "cinematic": dict(bpm=70, drums="none", inst=["strings", "piano", "pad", "bass"], prog=[6, 4, 1, 5], scale="minor"),
    "hiphop":    dict(bpm=88, drums="trap", inst=["piano", "bass", "pad"], prog=[1, 6, 4, 5], scale="minor"),
    "ballad":    dict(bpm=72, drums="halftime", inst=["piano", "strings", "bass"], prog=[1, 5, 6, 4], scale="major"),
    "dance":     dict(bpm=124, drums="pop", inst=["pluck", "bass", "pad", "piano"], prog=[6, 4, 1, 5], scale="minor"),
    "kids":      dict(bpm=116, drums="pop", inst=["marimba", "bass", "pluck"], prog=[1, 4, 5, 1], scale="major"),
}
_PATTERNS = {  # 16 steps per bar: kick, snare/clap, hat
    "pop":      ("x...x...x...x...", "....x.......x...", "x.x.x.x.x.x.x.x."),
    "afro":     ("x..x..x...x..x..", "....x.......x..x", "xxx.xxx.xxx.xxx."),
    "amapiano": ("x...x...x...x...", "....x.......x...", ".x.x.x.x.x.x.x.x"),
    "lofi":     ("x......x..x.....", "....x.......x...", "x.x.x.x.x.x.x.x."),
    "trap":     ("x......x..x.....", "........x.......", "xxxxxxxxxxxxxxxx"),
    "halftime": ("x.........x.....", "........x.......", "x...x...x...x..."),
    "none":     ("................", "................", "................"),
}


def _freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _env(n, a, rel=0.08, decay=None):
    A, R = max(1, int(a * SR)), max(1, int(rel * SR))
    out = []
    for i in range(n):
        e = min(1.0, i / A)
        if decay:
            e *= _m.exp(-i / (decay * SR))
        if i > n - R:
            e *= max(0.0, (n - i) / R)
        out.append(e)
    return out


_CACHE = {}


def _voice(inst, midi, n):
    key = (inst, midi, n)
    if key in _CACHE:
        return _CACHE[key]
    f, w, out = _freq(midi), 2 * _m.pi / SR, []
    sin = _m.sin
    if inst == "piano":
        env = _env(n, 0.004, 0.12)
        hs = [(1, 1.0), (2, 0.45), (3, 0.22), (4, 0.12), (5, 0.06)]
        for i in range(n):
            t = i * w * f
            s = 0.0
            for k, a in hs:
                s += a * sin(t * k * 1.0008 ** k) * _m.exp(-i * k / (1.3 * SR))
            out.append(s * env[i] * 0.5)
    elif inst == "epiano":
        env = _env(n, 0.003, 0.15, decay=1.6)
        for i in range(n):
            t = i * w * f
            out.append((sin(t + 1.2 * _m.exp(-i / (0.25 * SR)) * sin(t * 2)) + 0.15 * sin(t * 3)) * env[i] * 0.45)
    elif inst in ("pad", "strings"):
        att = 0.35 if inst == "pad" else 0.18
        env = _env(n, att, 0.4)
        det = (1.0, 1.006, 0.994)
        for i in range(n):
            vib = 1 + (0.003 * sin(i * w * 5.2) if inst == "strings" else 0)
            s = 0.0
            for d in det:
                t = i * w * f * d * vib
                s += sin(t) + 0.35 * sin(2 * t) + 0.15 * sin(3 * t) + 0.07 * sin(4 * t)
            out.append(s * env[i] * 0.13)
    elif inst == "bass":
        env = _env(n, 0.006, 0.06, decay=1.2)
        for i in range(n):
            t = i * w * f
            out.append((sin(t) + 0.25 * sin(2 * t) + 0.08 * sin(3 * t)) * env[i] * 0.6)
    elif inst == "logdrum":
        for i in range(min(n, int(0.5 * SR))):
            fr = f * (1 + 0.6 * _m.exp(-i / (0.02 * SR)))
            out.append(sin(2 * _m.pi * fr * i / SR) * _m.exp(-i / (0.22 * SR)) * 0.75)
        out += [0.0] * (n - len(out))
    elif inst == "marimba":
        env = _env(n, 0.002, 0.05, decay=0.35)
        for i in range(n):
            t = i * w * f
            out.append((sin(t) + 0.3 * sin(4 * t) * _m.exp(-i / (0.05 * SR))) * env[i] * 0.5)
    elif inst == "pluck":  # Karplus-Strong string
        p = max(2, int(SR / f))
        buf = [_r.uniform(-1, 1) for _ in range(p)]
        for i in range(n):
            v = buf[i % p]
            buf[i % p] = 0.996 * 0.5 * (v + buf[(i + 1) % p])
            out.append(v * 0.35)
        rel = int(0.05 * SR)
        for i in range(max(0, n - rel), n):
            out[i] *= (n - i) / rel
    _CACHE[key] = out
    return out


def _drum(kind):
    key = ("drum", kind)
    if key in _CACHE:
        return _CACHE[key]
    out = []
    if kind == "kick":
        ph = 0.0
        for i in range(int(0.35 * SR)):
            fr = 45 + 90 * _m.exp(-i / (0.03 * SR))
            ph += 2 * _m.pi * fr / SR
            out.append(_m.sin(ph) * _m.exp(-i / (0.12 * SR)) * 0.95)
    elif kind == "snare":
        for i in range(int(0.22 * SR)):
            out.append((_r.uniform(-1, 1) * 0.6 + 0.4 * _m.sin(2 * _m.pi * 185 * i / SR)) * _m.exp(-i / (0.05 * SR)) * 0.5)
    elif kind == "hat":
        prev = 0.0
        for i in range(int(0.05 * SR)):
            x = _r.uniform(-1, 1)
            out.append((x - prev) * _m.exp(-i / (0.012 * SR)) * 0.18)
            prev = x
    elif kind == "shaker":
        prev = 0.0
        for i in range(int(0.07 * SR)):
            x = _r.uniform(-1, 1)
            e = min(1, i / (0.01 * SR)) * _m.exp(-i / (0.025 * SR))
            out.append((x - prev) * e * 0.10)
            prev = x
    _CACHE[key] = out
    return out


def _add(buf, src, pos, gain=1.0):
    end = min(len(buf), pos + len(src))
    for i in range(pos, end):
        buf[i] += src[i - pos] * gain


def music_plan(desc):
    """The AI acts as producer: picks style, key, tempo, chords, melody and instruments."""
    d = (desc or "").lower()
    style = next((s for s in _STYLES if s in d), None)
    if not style:
        style = ("amapiano" if "piano" in d and "ama" in d else "afrobeat" if any(w in d for w in ("afro", "uganda", "dance hall", "kadongo"))
                 else "gospel" if any(w in d for w in ("god", "praise", "worship", "church")) else
                 "lofi" if any(w in d for w in ("chill", "relax", "study", "sleep", "calm")) else
                 "cinematic" if any(w in d for w in ("movie", "epic", "film", "sad")) else
                 "kids" if any(w in d for w in ("kid", "child", "happy birthday")) else "pop")
    plan = dict(_STYLES[style], style=style, key="C", title="Genius Song", melody=None, lyrics="")
    try:
        r = ask_gemini(
            "You are a hit music producer. Plan a short instrumental for: '" + (desc or "a beautiful song") + "'. "
            "Reply JSON only: {\"title\": str, \"style\": one of " + str(list(_STYLES)) + ", \"key\": like \"C\" or \"F#\", "
            "\"scale\": \"major\" or \"minor\", \"bpm\": 65-128, \"progression\": 4 scale degrees 1-7, "
            "\"melody\": 32 scale degrees (1-7, 8 = high 1, 0 = rest) as eighth notes, singable and catchy, "
            "\"lyrics\": 4 short lines for a chorus}", max_tokens=500, json_mode=True)
        j = json.loads(re.search(r"\{.*\}", r, re.S).group(0))
        if j.get("style") in _STYLES:
            plan.update(_STYLES[j["style"]], style=j["style"])
        if str(j.get("key", "")).upper() in _NOTE:
            plan["key"] = str(j["key"]).upper()
        if j.get("scale") in _SCALES:
            plan["scale"] = j["scale"]
        if 60 <= int(j.get("bpm", 0)) <= 132:
            plan["bpm"] = int(j["bpm"])
        pr = [int(x) for x in j.get("progression", []) if 1 <= int(x) <= 7]
        if len(pr) >= 4:
            plan["prog"] = pr[:4]
        mel = [int(x) for x in j.get("melody", []) if 0 <= int(x) <= 8]
        if len(mel) >= 16:
            plan["melody"] = (mel * 2)[:32]
        plan["title"] = str(j.get("title") or plan["title"])[:60]
        plan["lyrics"] = "\n".join(j["lyrics"]) if isinstance(j.get("lyrics"), list) else str(j.get("lyrics", ""))
    except Exception as e:
        log(f"MUSIC plan: {e}")
    return plan


def make_song(desc):
    plan = music_plan(desc)
    root = 48 + _NOTE.get(plan["key"], 0)            # C3 area
    sc = _SCALES[plan["scale"]]
    deg = lambda d, base=root: base + 12 * ((d - 1) // 7) + sc[(d - 1) % 7]
    step = int(SR * 60 / plan["bpm"] / 4)             # one 16th note
    bar = step * 16
    form = [("intro", 2), ("verse", 4), ("chorus", 4), ("verse", 4), ("chorus", 4), ("outro", 2)]
    total = bar * sum(b for _, b in form) + SR * 3
    L, R, verb = [0.0] * total, [0.0] * total, [0.0] * total
    inst = plan["inst"]
    if not plan["melody"]:                            # chord-aware fallback melody
        mel, cur = [], 5
        for i in range(32):
            if i % 8 == 7 or _r.random() < 0.12:
                mel.append(0)
                continue
            cur = max(1, min(8, cur + _r.choice((-2, -1, -1, 0, 1, 1, 2))))
            mel.append(cur)
        plan["melody"] = mel
    kick, snare, hat = _PATTERNS.get(plan["drums"], _PATTERNS["none"])
    pos = 0
    for part, bars in form:
        full = part == "chorus"
        for b in range(bars):
            chord_deg = plan["prog"][b % 4]
            triad = [deg(chord_deg + k, root + 12) for k in (0, 2, 4)]
            # chords
            for name in inst:
                if name in ("piano", "epiano"):
                    if name == "epiano" or part in ("intro", "outro"):
                        for k, note in enumerate(triad):
                            v = _voice(name, note, bar)
                            _add(L, v, pos + k * 40, 0.55); _add(R, v, pos + k * 40 + 60, 0.55); _add(verb, v, pos, 0.3)
                    else:
                        for s in (0, 6, 8, 14) if full else (0, 8):
                            for note in triad:
                                v = _voice(name, note, step * 6)
                                _add(L, v, pos + s * step, 0.42); _add(R, v, pos + s * step, 0.42); _add(verb, v, pos + s * step, 0.25)
                elif name in ("pad", "strings") and (full or part in ("intro", "outro") or name == "strings"):
                    for note in triad + [triad[0] + 12]:
                        v = _voice(name, note, bar)
                        _add(L, v, pos, 0.7 if full else 0.5); _add(R, v, pos + 260, 0.7 if full else 0.5); _add(verb, v, pos, 0.5)
                elif name == "bass" and part not in ("intro",):
                    bn = deg(chord_deg, root - 12)
                    for s in (0, 3, 8, 11) if full else (0, 8):
                        v = _voice("bass", bn, step * 3)
                        _add(L, v, pos + s * step, 0.9); _add(R, v, pos + s * step, 0.9)
                elif name == "logdrum" and part not in ("intro", "outro"):
                    bn = deg(chord_deg, root - 12)
                    for s in (0, 3, 7, 10, 14):
                        v = _voice("logdrum", bn, step * 4)
                        _add(L, v, pos + s * step, 0.8); _add(R, v, pos + s * step, 0.8)
                elif name == "pluck" and part != "intro":
                    for s in range(0, 16, 2):
                        v = _voice("pluck", triad[(s // 2) % 3] + 12, step * 2)
                        _add(L, v, pos + s * step, 0.5); _add(R, v, pos + s * step, 0.25); _add(verb, v, pos + s * step, 0.3)
            # melody (lead): piano/marimba voice, octave up in chorus
            if part in ("verse", "chorus"):
                lead = "marimba" if "marimba" in inst else ("epiano" if "epiano" in inst else "piano")
                for s in range(8):
                    dg = plan["melody"][(b % 4) * 8 + s]
                    if dg:
                        note = deg(dg, root + (24 if full else 12))
                        v = _voice(lead, note, step * 2 + step // 2)
                        g = 0.55 if full else 0.42
                        _add(L, v, pos + s * 2 * step, g); _add(R, v, pos + s * 2 * step + 30, g); _add(verb, v, pos + s * 2 * step, 0.45)
            # drums
            if part not in ("intro", "outro") or (part == "outro" and b == 0):
                for s in range(16):
                    p = pos + s * step
                    if kick[s] == "x": _add(L, _drum("kick"), p, 0.9); _add(R, _drum("kick"), p, 0.9)
                    if snare[s] == "x": _add(L, _drum("snare"), p, 0.55); _add(R, _drum("snare"), p, 0.55); _add(verb, _drum("snare"), p, 0.3)
                    if hat[s] == "x" and (full or s % 2 == 0):
                        hk = "shaker" if "shaker" in inst else "hat"
                        _add(L, _drum(hk), p, 0.8 if s % 4 else 1.0); _add(R, _drum(hk), p + 90, 0.6)
            pos += bar
    # reverb: 3 comb filters + allpass on the send bus (hall sound)
    rv = [0.0] * total
    for dl, fb in ((int(0.0297 * SR), 0.80), (int(0.0371 * SR), 0.78), (int(0.0411 * SR), 0.76)):
        c = verb[:]
        for i in range(dl, total):
            c[i] += c[i - dl] * fb
        for i in range(total):
            rv[i] += c[i]
    ap = int(0.005 * SR)
    y = rv[:]
    for i in range(ap, total):
        y[i] = -0.6 * rv[i] + rv[i - ap] + 0.6 * y[i - ap]
    rv = y
    # master: mix, glue, soft limiter, fades
    peak = 1e-6
    for i in range(total):
        L[i] += rv[i] * 0.10
        R[i] += rv[i - 120 if i >= 120 else i] * 0.10
        peak = max(peak, abs(L[i]), abs(R[i]))
    g = 1.6 / peak
    fade_in, fade_out = int(0.5 * SR), int(3 * SR)
    frames = bytearray()
    th = _m.tanh
    for i in range(total):
        e = min(1.0, i / fade_in, (total - i) / fade_out)
        frames += _st.pack("<hh", int(th(L[i] * g) * 0.89 * e * 32767), int(th(R[i] * g) * 0.89 * e * 32767))
    _CACHE.clear()
    out = os.path.join(genius_dl("music"), re.sub(r"[^A-Za-z0-9]+", "_", plan["title"])[:40] + time.strftime("_%H%M%S") + ".wav")
    with _wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(frames))
    return out, plan


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
    if "black" in st:
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


def newest_photos(n=6):
    found = []
    for d in ("/storage/emulated/0/DCIM/Camera", "/storage/emulated/0/Pictures",
              "/storage/emulated/0/Download", "/storage/emulated/0/Pictures/Screenshots", genius_dl("fun"), "."):
        try:
            for x in os.listdir(d):
                if x.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    found.append(os.path.join(d, x))
        except Exception:
            pass
    found = sorted(set(found), key=lambda f: os.path.getmtime(f), reverse=True)
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
            return "I couldn't read that file."
        return ask_gemini("File " + os.path.basename(path) + ":\n" + content +
                          "\n\nQuestion: " + q, 900) or "No AI answered. Check your internet."
    if not os.path.exists(KEY_FILE):
        return "To read pictures and PDFs I need your Gemini key. Use setkey first."
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
            if e.code in (401, 403):
                return "Google rejected the key. Use setkey again."
            last = "Free limit reached. Wait a minute." if e.code == 429 else "Google is busy. Try again shortly."
        except Exception:
            last = "Your internet is too slow right now. Try better signal."
    return last


def ask_gemini(prompt, max_tokens=600, json_mode=False, search=False, system=None):
    """Ask Gemini; if it has no key or fails, another connected AI answers instead."""
    r = _ask_gemini_only(prompt, max_tokens, json_mode, search, system)
    if r and not (search and r.startswith("Search failed")):
        return r
    for prov in ("groq", "openrouter"):
        sys_txt = system or ("You help " + CURRENT["name"] + ", a young person in Uganda. Simple, clear English."
                             + (" Reply with only valid JSON." if json_mode else ""))
        t = other_ai(prov, prompt, system=sys_txt, max_tokens=max(max_tokens, 400))
        if t:
            if json_mode:
                t = t.strip().strip("`")
                t = t[t.find("{"):t.rfind("}") + 1] if "{" in t else t
            return t
    return r


def think_together(question):
    """Several AIs answer, then one AI checks them and writes the best combined answer."""
    have = connected_ais()
    if not have:
        return "No AIs connected. Use setkey, setgroq or setrouter."
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
           ast.Pow: op.pow, ast.Mod: op.mod, ast.USub: op.neg, ast.FloorDiv: op.floordiv}

    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp):
            return ops[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return ops[type(n.op)](ev(n.operand))
        raise ValueError
    try:
        val = ev(ast.parse(expr, mode="eval").body)
        return f"{expr} = {val:g}"
    except Exception:
        return "I can do numbers like: calc 12*8+5"


def weather_report(city):
    city = city or "Kampala"
    try:
        g = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1"
        loc = json.load(urllib.request.urlopen(g, timeout=20, context=ssl_context()))["results"][0]
        w = (f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}"
             f"&longitude={loc['longitude']}&current=temperature_2m,relative_humidity_2m,"
             f"wind_speed_10m,weather_code&daily=temperature_2m_max,temperature_2m_min"
             f"&timezone=auto")
        d = json.load(urllib.request.urlopen(w, timeout=20, context=ssl_context()))
        c = d["current"]
        hi = d["daily"]["temperature_2m_max"][0]
        lo = d["daily"]["temperature_2m_min"][0]
        codes = {0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy",
                 45: "foggy", 48: "foggy", 51: "light drizzle", 61: "light rain",
                 63: "rain", 65: "heavy rain", 80: "rain showers", 95: "a thunderstorm"}
        sky = codes.get(c.get("weather_code"), "mixed weather")
        return (f"{loc['name']}: {c['temperature_2m']:.0f} degrees now with {sky}, "
                f"humidity {c['relative_humidity_2m']:.0f} percent, wind "
                f"{c['wind_speed_10m']:.0f} km/h. Today {lo:.0f} to {hi:.0f} degrees.")
    except Exception:
        return "I couldn't get the weather. Check your internet and the city name."


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
    "yimirira": "stop",
}


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
                log(f"UI RUN error: {e}")
                MIC_STATE["last"] = f"start failed: {e}"
                if on_fail:
                    Clock.schedule_once(lambda *_: on_fail(f"start failed: {e}", -1), 0)
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


GENIUS_LINK = "https://github.com/ssalimuto/Genius-app/releases/latest"
SHARE_TEXT = ("Meet Genius - an AI that talks with you, makes songs, edits photos without changing your face, "
              "zooms 100x and more. Free 7-day trial. Download for Android: " + GENIUS_LINK)


def share_genius(target=None):
    """Open Android's share sheet (WhatsApp, TikTok, Facebook, X, Instagram, SMS...) with the download link."""
    from jnius import autoclass
    act = autoclass("org.kivy.android.PythonActivity").mActivity
    Intent = autoclass("android.content.Intent")
    i = Intent(Intent.ACTION_SEND)
    i.setType("text/plain")
    i.putExtra(Intent.EXTRA_TEXT, SHARE_TEXT)
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
WEALTH_SYSTEM = ("You are Genius Wealth, a free trading coach for people in Uganda and East Africa who want to build "
                 "wealth through trading (forex, stocks, crypto). Explain simply, with UGX where useful. Teach: reading "
                 "charts (trend, support/resistance, candles, RSI, MACD, moving averages), building a written trading plan, "
                 "entries and exits, stop-loss and take-profit, risking at most 1-2% of the account per trade, position "
                 "size math, a trading journal, demo practice before real money, regulated brokers only, and avoiding "
                 "signal-sellers, 'account managers' and scams. Use the live prices given. Be honest that most traders "
                 "lose money and growth comes from discipline over time. Never promise profits or say 'guaranteed'. "
                 "Never ask for PINs or passwords. End with one clear next step. Education, not financial advice.")
CHART_PROMPT = ("You are a careful technical analyst. Read this trading chart picture. Report, in simple English: "
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
        photo = my_photo()
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


def style_input(ti):
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
        Color(1, 1, 1, 0.07)
        bgr = RoundedRectangle(radius=[18])
        edge_col = Color(1, 1, 1, 0.16)
        edge = Line(width=1.1)

    def sync(*_):
        bgr.pos, bgr.size = ti.pos, ti.size
        edge.rounded_rectangle = (ti.x, ti.y, ti.width, ti.height, 18)

    def glow(_, focused):
        edge_col.rgba = (1.0, 0.78, 0.30, 0.85) if focused else (1, 1, 1, 0.16)
    ti.bind(pos=sync, size=sync, focus=glow)
    return ti


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


class ChatScreen(BoxLayout):
    attached = None
    _to_storage = False

    def __init__(self, app, **kw):
        super().__init__(orientation="vertical", padding=0, spacing=0, **kw)
        self.app = app
        self.deep = False
        add_gradient_bg(self)

        # header bar: profile on the left
        header = Panel(bg=HEADER, radius=0, orientation="horizontal",
                       size_hint_y=None, height="60dp", padding=[12, 0, 18, 0], spacing=10)
        pbox = BoxLayout(size_hint_x=None, width="46dp", padding=[0, 9, 0, 9])
        self.profile_chip = ProfileChip()
        self.profile_chip.bind(on_press=self.profile_drawer)
        pbox.add_widget(self.profile_chip)
        header.add_widget(pbox)
        title = Label(text="[b][color=ffc84d]Gen[/color][color=c79bff]ius[/color][/b]  [size=12sp][color=5ee6a0]\u25cf[/color] [color=9aa0c0]online[/color][/size]",
                      markup=True, font_size="25sp", halign="left", valign="middle")
        title.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        header.add_widget(title)
        self.mode_lbl = Label(text="Fast", font_size="15sp", color=HINT,
                              halign="right", size_hint_x=None, width="60dp")
        header.add_widget(self.mode_lbl)
        hb = BoxLayout(size_hint_x=None, width="104dp", spacing=8, padding=[0, 9, 0, 9])
        menu_btn = RoundButton(text="Menu", bg=GREY, fg=TEXTCOL, font_size="13sp", bold=True)
        menu_btn.bind(on_press=self.options_menu)
        find_btn = RoundButton(text="Find", bg=BLUE, fg=TEXTCOL, font_size="13sp", bold=True)
        find_btn.bind(on_press=self.search_box)
        hb.add_widget(menu_btn)
        hb.add_widget(find_btn)
        header.add_widget(hb)
        self.add_widget(header)

        # chat area
        body = Panel(orientation="vertical", padding=[10, 8, 10, 8], spacing=8,
                     bg=(1, 1, 1, 0.045), radius=26)
        outer = BoxLayout(padding=[10, 10, 10, 8])
        self.scroll = ScrollView(bar_color=(1.0, 0.78, 0.30, 0.7), bar_width="3dp")
        self.out = Label(text="", markup=True, font_size="18sp", size_hint_y=None,
                         halign="left", valign="top", color=TEXTCOL, padding=(8, 8))
        self.out.bind(width=lambda *a: setattr(self.out, "text_size", (self.out.width, None)),
                      texture_size=lambda *a: setattr(self.out, "height", self.out.texture_size[1]))
        self.scroll.add_widget(self.out)
        body.add_widget(self.scroll)
        outer.add_widget(body)
        self.add_widget(outer)

        # button grid
        grid = GridLayout(cols=4, size_hint_y=None, height="110dp", spacing=8,
                          padding=[10, 0, 10, 0])
        buttons = [("Speak", "speak", GOLD), ("Draw", "draw", BLUE),
                   ("Locker", "locker", GREY), ("Notes", "notes", GREY),
                   ("Weather", "weather", GREY), ("Deep", "deep", GREY),
                   ("Clear", "clear", GREY), ("Stop", "stop", RED)]
        for label, key, col in buttons:
            fg = (0.1, 0.1, 0.1, 1) if col == GOLD else TEXTCOL
            b = RoundButton(text=label, bg=col, fg=fg, font_size="16sp", bold=True)
            if key == "speak":
                self.speak_btn = b
                b.bind(on_press=self.speak_input)
            elif key == "locker":
                b.bind(on_press=lambda btn: self.handle("secrets"))
            elif key == "deep":
                self.deep_btn = b
                b.bind(on_press=self.toggle_deep)
            elif key == "clear":
                b.bind(on_press=self.clear_chat)
            else:
                b.bind(on_press=lambda btn, n=key: self.handle("tell me a joke" if n == "joke" else n))
            grid.add_widget(b)
        self.add_widget(grid)

        # input row
        row = BoxLayout(size_hint_y=None, height="62dp", spacing=8, padding=[10, 4, 10, 10])
        self.inp = style_input(TextInput(hint_text="Type, or tap Speak...",
                               multiline=False, font_size="18sp"))
        self.inp.bind(on_text_validate=self.send)
        send = RoundButton(text="Send", bg=GOLD, fg=(0.1, 0.1, 0.1, 1),
                           size_hint_x=None, width="96dp", font_size="18sp", bold=True)
        send.bind(on_press=self.send)
        plus = RoundButton(text="+", bg=BLUE, fg=TEXTCOL, size_hint_x=None, width="52dp",
                           font_size="28sp", bold=True)
        plus.bind(on_press=self.attach_menu)
        row.add_widget(plus)
        row.add_widget(self.inp)
        row.add_widget(send)
        self.add_widget(row)

        self.say(f"Welcome {CURRENT['name']}. You are in command. Tap Speak to talk to me.")

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
        self.speak_btn.text = "Listening"
        self.speak_btn.set_bg(RED)
        self.speak_btn.color = TEXTCOL
        self.listen_now()

    def end_talk(self, msg=None):
        self.talking = False
        self.speak_btn.text = "Speak"
        self.speak_btn.set_bg(GOLD)
        self.speak_btn.color = (0.1, 0.1, 0.1, 1)
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
    def _bg(self, fn):
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
            return "\U0001F4C8 Chart reading\n" + ans
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
            src = LAST_IMAGE.get("path")
            if src and set_my_photo(src):
                self.profile_chip.redraw()
                self.say("Your profile picture is updated.")
            else:
                self.say("Take a selfie or add a picture first, then tap 'Use last picture as my photo'.")

        opts = [("Home", self.app.open_home, GOLD),
                ("Genius Wealth (trading & money)", self.wealth_menu, GOLD),
                ("Use last picture as my photo", set_photo, BLUE),
                ("Take a selfie", self.zoom_camera, BLUE),
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

    # ---------- header: Menu (options) and Find (search) ----------
    def options_menu(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        pop = Popup(title="Options", content=box, size_hint=(0.9, 0.94),
                    separator_color=GOLD, title_color=GOLD)
        opts = [("Fun studio (collage, effects, video)", self.fun_studio, GOLD),
                ("My creations (pictures)", self.creations, BLUE),
                ("My storage", self.storage_box, BLUE),
                ("Add a picture or file", self.attach_menu, BLUE),
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
            request_permissions([Permission.CAMERA])
        except Exception:
            pass
        Clock.schedule_once(lambda *_: self._open_camera(), 0.8)

    def _open_camera(self, index=0):
        from kivy.uix.camera import Camera
        from kivy.uix.slider import Slider
        from kivy.uix.stencilview import StencilView
        from kivy.uix.floatlayout import FloatLayout
        from kivy.graphics import PushMatrix, PopMatrix, Rotate
        try:
            cam = Camera(index=index, resolution=(1920, 1080), play=True, allow_stretch=True, keep_ratio=True)
        except Exception as e:
            log(f"CAMERA: {e}")
            self.say("I couldn't open the camera. Allow camera permission, or use 'Zoom a photo' instead.")
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
        self.busy = True
        self.say(f"Zooming {z:g}x and sharpening...")

        def d(*_):
            try:
                out, msg = super_zoom(src, z)
            except Exception as e:
                out, msg = None, f"Zoom didn't work: {e}"

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
        apps = [("WhatsApp", "com.whatsapp"), ("Facebook", "com.facebook.katana"), ("TikTok", "com.zhiliaoapp.musically"),
                ("Instagram", "com.instagram.android"), ("X (Twitter)", "com.twitter.android"), ("Telegram", "org.telegram.messenger")]

        def go(pkg=None):
            try:
                share_genius(pkg)
            except Exception as e:
                self.say(f"Sharing didn't open: {e}. The link is {GENIUS_LINK}")
        self._buttons_popup("Share Genius", [(n, lambda p=p: go(p), BLUE) for n, p in apps] +
                            [("Any other app...", go, GOLD)], cols=2,
                            hint="Friends download Genius from your link")

    def everywhere_menu(self, *_):
        on = EVERYWHERE["bubble_on"]
        hey = getattr(self, "hey_on", False)
        self._buttons_popup("Genius everywhere", [
            ("Floating bubble: " + ("ON" if on else "OFF"), self.toggle_bubble, GOLD),
            ('"Hey Genius" wake word: ' + ("ON" if hey else "OFF"), self.toggle_hey, GOLD),
            ("Home-screen button: Talk", lambda: self.add_shortcut("talk", "Genius Talk"), BLUE),
            ("Home-screen button: Camera", lambda: self.add_shortcut("camera", "Genius Camera"), BLUE),
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
        opts = [("Afrobeat", "afrobeat"), ("Amapiano", "amapiano"), ("Pop hit", "pop"), ("Gospel", "gospel"),
                ("Lo-fi chill", "lofi"), ("Hip hop", "hiphop"), ("Love ballad", "ballad"), ("Cinematic", "cinematic"),
                ("Dance", "dance"), ("Kids song", "kids")]
        self._buttons_popup("Music maker", [(t, lambda k=k: self.make_music(k + " song"), GOLD if i < 2 else BLUE)
                                            for i, (t, k) in enumerate(opts)] +
                            [("Describe my own...", lambda: self.say("Say 'sound' then describe it, like: "
                                                                     "sound happy afrobeat about my friends"), GREY)],
                            cols=2, hint="AI picks the key, chords, melody and instruments")

    def make_music(self, desc=""):
        if self.busy:
            self.say("One moment, I'm still finishing the last job.")
            return
        self.busy = True
        self.say("Composing your song: choosing the key, chords, melody and instruments, then mixing it "
                 "like a studio. This takes about a minute...")

        def d(*_):
            try:
                out, plan = make_song(desc)
                err = None
            except Exception as e:
                out, plan, err = None, None, str(e)

            def done(*_):
                self.busy = False
                if not out:
                    self.say(f"The song didn't work: {err}")
                    return
                _play_file(out)
                self._last_song = out
                lyr = f"\n\nChorus idea:\n{plan['lyrics']}" if plan.get("lyrics") else ""
                self.show("AI", f"\u266b [b]{plan['title']}[/b]\n{plan['style'].title()} in {plan['key']} "
                                f"{plan['scale']}, {plan['bpm']} BPM. Playing now.\nSaved in Download/Genius/music. "
                                f"Say 'play song' again or 'stop music'.{lyr}")
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    def ultra_photo(self, *_):
        src = self._edit_src()
        if not src:
            self.say("Add a photo with + first, then say 'ultra'.")
            return
        self.busy = True
        self.say("Genius Ultra is working: HDR, true colour, clarity, fine detail...")

        def d(*_):
            try:
                out, msg = ultra_hd(src)
            except Exception as e:
                out, msg = None, f"Ultra didn't work: {e}"

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
                out, err = blend_images(paths, t)

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
                out, msg = None, f"That didn't work: {e}"

            def done(*_):
                self.busy = False
                if out:
                    remember_image(out, job)
                    self.show_image(out, msg + "\nSaved in Download/Genius/fun")
                    self.say(msg + " Saved in Download/Genius/fun." +
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
        self.busy = True

        def d(*_):
            try:
                if style.startswith("LOOK:"):
                    out, msg = pro_look(src, style[5:])
                else:
                    out, msg = beautify(src) if style == "Beautify" else transform_image(src, style)
            except ImportError:
                out, msg = None, "The picture tools aren't installed in this version."
            except Exception as e:
                out, msg = None, f"That effect didn't work: {e}"

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
        for d in (".", attach_dir(), genius_dl("fun")):
            try:
                for n in os.listdir(d):
                    if n.lower().endswith(IMG_EXTS) and (n.startswith("drawing_") or d != "."):
                        found.append(os.path.abspath(os.path.join(d, n)))
            except Exception:
                pass
        return sorted(set(found), key=lambda f: os.path.getmtime(f), reverse=True)

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

    def search_box(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        ti = style_input(TextInput(hint_text="Search for...", multiline=False, font_size="18sp",
                                   size_hint_y=None, height="52dp"))
        box.add_widget(ti)
        pop = Popup(title="Find", content=box, size_hint=(0.92, 0.6),
                    separator_color=GOLD, title_color=GOLD)
        opts = [("Search my chats and notes", self.search_mine, BLUE),
                ("Search my creations", lambda q: self.creations(q), BLUE),
                ("Search the internet", lambda q: self.web_search(q), GREY)]
        for label, fn, col in opts:
            b = RoundButton(text=label, bg=col, fg=TEXTCOL, size_hint_y=None, height="52dp",
                            font_size="17sp", bold=True)

            def go(btn, fn=fn):
                q = ti.text.strip()
                if not q:
                    return
                pop.dismiss()
                Clock.schedule_once(lambda *_: fn(q), 0.1)
            b.bind(on_press=go)
            box.add_widget(b)
        ti.bind(on_text_validate=lambda *_: (pop.dismiss(), self.search_mine(ti.text.strip())) if ti.text.strip() else None)
        pop.open()
        Clock.schedule_once(lambda *_: setattr(ti, "focus", True), 0.3)

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
            r = ask_gemini("Search the internet and answer briefly with the key facts: " + q, 700, search=True)

            def done(*_):
                self.busy = False
                self.say(r or "The search didn't work. Check your internet.")
            Clock.schedule_once(done, 0)
        threading.Thread(target=d, daemon=True).start()

    # ---------- + button: add pictures and files ----------
    PICK_CODE = 7780

    def attach_menu(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        pop = Popup(title="Add to Genius", content=box, size_hint=(0.9, 0.62),
                    separator_color=GOLD, title_color=GOLD)
        opts = [("Choose a picture", lambda: self.pick_file("image/*"), BLUE),
                ("Choose a file (PDF, text...)", lambda: self.pick_file("*/*"), BLUE),
                ("My newest photo", lambda: self.attach_newest(True), GREY),
                ("My newest file", lambda: self.attach_newest(False), GREY),
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
            r = ask_about_file(a["path"], a["kind"], question)
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
            path, note = edit_image(instruction)

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
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        box.add_widget(KivyImage(source=path, allow_stretch=True, keep_ratio=True))
        box.add_widget(Label(text=f"{caption}\nSaved as {os.path.basename(path)}",
                             size_hint_y=None, height="60dp", font_size="15sp", color=TEXTCOL))
        btn = RoundButton(text="Close", bg=GOLD, fg=(0.1, 0.1, 0.1, 1),
                          size_hint_y=None, height="52dp", bold=True)
        box.add_widget(btn)
        pop = Popup(title="Your drawing", content=box, size_hint=(0.95, 0.9),
                    separator_color=GOLD, title_color=GOLD)
        btn.bind(on_press=pop.dismiss)
        pop.open()

    # output
    def show(self, who, text):
        if who == "AI":
            head = "[b][color=ffc84d]\u2726 Genius[/color][/b]"
        else:
            head = f"[b][color=9db4ff]{who}[/color][/b]"
        self.out.text += f"{head}\n{text}\n[size=6sp] [/size]\n"
        Clock.schedule_once(lambda *_: setattr(self.scroll, "scroll_y", 0), 0.1)

    def say(self, text):
        self.show("AI", text)
        self._last_said = text
        tts(text)
        if getattr(self, "talking", False):
            self.listen_after_speech()

    def send(self, *_):
        text = self.inp.text.strip()
        self.inp.text = ""
        if text:
            self.handle(text)

    # brain
    def handle(self, line):
        low = line.lower()
        if low.strip(" .!?") in ("mic test", "test mic", "test microphone", "microphone test"):
            self.mic_test()
            return
        if low.startswith("setkey") or low.startswith("save ") or low.startswith("setvoice") \
                or low.startswith("setgroq") or low.startswith("setrouter"):
            head = line.split()[0]
            self.show("You", f"{head} ********")
        else:
            self.show("You", line)
        if is_crisis(line):
            log("SAFETY: crisis words detected")
            self.show("AI", HELPLINES)
        action, _, arg = line.partition(" ")
        action, arg = action.lower(), arg.strip()
        action = LUGANDA_CMDS.get(action, action)
        action = {"whatsnew": "version", "changelog": "version", "update": "version"}.get(action, action)

        # picture follow-ups, like Gemini: "make me near building" edits the last picture
        if low.strip(" .!") in ("setme", "set me", "this is me", "use this face", "keep this face", "save my face"):
            src = LAST_IMAGE["path"] if low.strip(" .!") in ("use this face", "keep this face") else None
            f = set_my_photo(src)
            self.say("Saved your face. Now say 'make me ...' and every picture keeps it." if f
                     else "I couldn't find a photo. Take a clear selfie first, then say setme.")
            return
        if not CURRENT["owner"] and (action in OWNER_ONLY or low.startswith(("setkey", "setgroq", "setrouter", "setvoice", "setsunbird"))):
            self.say("Only the owner of this phone can do that.")
            return
        lw = low.strip(" .!")
        # Free access to the phone's apps: owner only, never other users
        if lw in ("apps", "my phone apps", "phone apps", "list apps") or lw.startswith(("open ", "launch ", "start ")):
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
                        self.say(f"Opening apps only works on the phone: {e}")
                    return
            else:
                try:
                    names = sorted(phone_apps(refresh=True), key=str.lower)
                    self.say(f"You have {len(names)} apps. Say open and a name, e.g. open WhatsApp.\n" + ", ".join(names))
                except Exception as e:
                    self.say(f"Listing apps only works on the phone: {e}")
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
        if lw in ("camera", "zoom camera", "super zoom", "zoom", "open camera"):
            self.zoom_camera()
            return
        if lw in ("sound", "music", "music maker", "make music", "make a song", "song", "make song", "beat", "make a beat"):
            self.music_menu()
            return
        if lw in ("stop music", "stop song"):
            try:
                _luganda["sound"].stop()
            except Exception:
                pass
            self.say("Music stopped.")
            return
        if lw in ("play song", "play music", "play again") and getattr(self, "_last_song", None):
            _play_file(self._last_song)
            return
        for pre in ("sound ", "music ", "make music ", "make a song ", "make song ", "song about ", "make a beat "):
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
            self.show("AI", "\n".join(f"{k} - {v}" for k, v in ALLOWED.items()))
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
        if action == "setkey":
            if arg:
                key = clean_key(arg)
                open(KEY_FILE, "w").write(key)
                self.say(f"Key saved, ending in {key[-4:]}. Ask me anything.")
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
            self.busy = True
            self.say("Drawing... this takes a moment.")

            def d(*_):
                path, err = gemini_image(arg)

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
            self.say(f"{arg}: {val}" if val is not None else f"Nothing saved under '{arg}'.")
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
    def _bg(self, job, wait_msg, speak=True):
        """Run a slow job in the background, then show/speak the result."""
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

    def _need_key(self):
        if connected_ais():
            return False
        self.say("This needs an AI key. Type setkey (Gemini), setgroq or setrouter first.")
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
        elif action == "explain":
            if not arg:
                self.say("Tell me what to explain, e.g. explain osmosis")
                return
            if self._need_key():
                return
            self._bg(lambda: ask_gemini(
                f"Explain '{arg}' for a Ugandan secondary school student in under 120 words: "
                f"a simple definition, one everyday Ugandan example, and one exam tip.", 500)
                or "I couldn't reach Gemini. Try again.", "Thinking...")
        elif action == "studyplan":
            if self._need_key():
                return
            info = study_status(d)
            self._bg(lambda: ask_gemini(
                f"Make today's study plan (max 6 short lines with times, total about 2 hours, "
                f"with breaks) for this student:\n{info}\nFocus on weak topics first.", 600)
                or "I couldn't reach Gemini. Try again.", "Planning your day...", speak=False)
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
                r = ask_gemini(text, toks or 600, search=search) or "I couldn't reach Gemini. Try again."
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

    def chat(self, text):
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
        ck = text.strip().lower()
        if ck in _answer_cache and not needs_tools(text):
            self.say(_answer_cache[ck])          # instant: answered before
            return
        if self.turbo_on() and provider_key("groq") and not needs_tools(text) \
                and not self.deep and not getattr(self, "busy", False):
            self.busy = True
            self.show("AI", "Thinking fast...")

            def turbo():
                r = other_ai("groq", text, convo=history)
                if r:
                    history.append({"role": "user", "parts": [{"text": text}]})
                    history.append({"role": "model", "parts": [{"text": r}]})
                    save_memory()
                    _answer_cache[ck] = r
                else:
                    r, err = agent_reply(text, ui_hooks, self.deep) if os.path.exists(KEY_FILE) \
                        else (None, "No AI answered. Check your internet.")
                    r = r or err

                def done(*_):
                    self.busy = False
                    self.say(r)
                Clock.schedule_once(done, 0)
            ui_hooks = self._ui_hooks()
            threading.Thread(target=turbo, daemon=True).start()
            return
        if not os.path.exists(KEY_FILE) and not connected_ais():
            self.say("I don't know that yet. Type setkey and your free Gemini key "
                     "from aistudio.google.com so I can answer anything.")
            return
        if getattr(self, "busy", False):
            self.say("Still thinking about your last question. One moment.")
            return
        self.busy = True
        self.show("AI", "Thinking deeply..." if self.deep else "Thinking...")

        ui = {
            "remind": lambda m, t: Clock.schedule_once(
                lambda *_: self._fire_reminder(t), m * 60),
            "image": lambda path, cap: Clock.schedule_once(
                lambda *_: self.show_image(path, cap), 0),
        }

        def work():
            reply, err = agent_reply(text, ui, self.deep) if os.path.exists(KEY_FILE) \
                else (None, "No Gemini key.")
            if not reply:                       # backup AIs
                for prov in ("groq", "openrouter"):
                    reply = other_ai(prov, text, convo=history)
                    if reply:
                        break
            if reply and not needs_tools(text):
                _answer_cache[ck] = reply
            r = reply or err

            def done(*_):
                self.busy = False
                self.say(r)
            Clock.schedule_once(done, 0)
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
                 ("Super zoom camera", "camera", BLUE2), ("Genius Ultra photo", "ultra", BLUE),
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
        self.root_box.add_widget(LoginScreen(self))
        return self.root_box

    def build_login(self):
        self.chat = None
        safe(bubble_hide)
        try:
            switch_user(OWNER)          # leave the guest's space; next sign-in picks the account
        except Exception:
            pass
        self.root_box.clear_widgets()
        self.root_box.add_widget(LoginScreen(self))

    def open_decoy(self, tried=""):
        self.root_box.clear_widgets()
        self.root_box.add_widget(DecoyScreen(self, tried))

    def on_start(self):
        everywhere_load()
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
