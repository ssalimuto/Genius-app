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
BG       = (0.06, 0.07, 0.11, 1)
HEADER   = (0.12, 0.14, 0.24, 1)
PANEL    = (0.10, 0.12, 0.18, 1)
GOLD     = (0.96, 0.76, 0.26, 1)
BLUE     = (0.20, 0.45, 0.75, 1)
GREY     = (0.20, 0.22, 0.30, 1)
RED      = (0.70, 0.25, 0.28, 1)
TEXTCOL  = (0.93, 0.94, 0.97, 1)
HINT     = (0.55, 0.58, 0.66, 1)
Window.clearcolor = BG

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
- Accounts: anyone can tap "Create an account" (name, hidden password, hidden code) and gets their own private Genius. Owner manages them in Menu > Accounts
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


def create_account(name, pw, code):
    name = name.strip().lower()
    if not valid_username(name):
        return "Name must be 3-20 letters, numbers or _ (no spaces)."
    a = accounts_load()
    if name == OWNER or name in a:
        return "That name is taken. Choose another."
    if len(pw) < 6:
        return "Password must be at least 6 characters."
    if not code.isdigit() or not (4 <= len(code) <= 8):
        return "Secret code must be 4 to 8 digits."
    if len(set(code)) == 1 or code in "0123456789" or code in "9876543210":
        return "Secret code is too easy to guess."
    ps, cs = os.urandom(16), os.urandom(16)
    a[name] = {"pw_salt": ps.hex(), "pw_hash": hash_pw(pw, ps), "code_salt": cs.hex(),
               "code_hash": hash_pw(code, cs), "created": time.strftime("%Y-%m-%d %H:%M")}
    accounts_save(a)
    log(f"ACCOUNT CREATED: {name}")
    return ""


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
    uname = name.strip().lower()
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


IMAGE_MODELS = ("gemini-2.5-flash-image", "gemini-3-pro-image-preview", "gemini-2.0-flash-preview-image-generation")


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


def edit_image(instruction):
    """Change the last picture the way Gemini does: same person, only what was asked changes."""
    base = LAST_IMAGE["path"]
    path, err = _gemini_image(instruction, edit=base)
    if path:
        return path, None
    log(f"EDIT: Gemini couldn't ({err}); redrawing with the free picture maker")
    combined = (LAST_IMAGE["prompt"] + ", " + instruction).strip(", ")
    path, err2 = free_image(realistic_prompt(combined))
    if path:
        return path, ("Gemini picture editing isn't on your key's free plan, so I redrew it. "
                      "The face may look different. Add billing at aistudio.google.com for true editing.")
    return None, err2


def _img_part(path):
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(open(path, "rb").read()).decode()}}


def _gemini_image(prompt, ref=None, edit=None):
    """Draw a picture from text with Gemini, optionally keeping the face in a reference photo.
    edit = path of the last picture: change only what the user asked (like Gemini's chat editing)."""
    if not os.path.exists(KEY_FILE):
        return None, "no key"
    key = clean_key(open(KEY_FILE).read())
    if edit:
        parts = [_img_part(edit)]
        face = my_photo()
        if face:
            parts.append(_img_part(face))
        parts.append({"text":
            "Edit the FIRST photo. Change: " + prompt + ". Keep the SAME person with the exact same face, "
            "head shape, skin tone, hair and body" + (" (the second photo shows their real face)" if face else "") +
            ". Keep their clothes, pose and everything else the same unless the change asks otherwise. "
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
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"], "temperature": 0.9},
    }).encode()
    last = "I couldn't draw that. Try again."
    for model in IMAGE_MODELS:
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

# ---------------- screens ----------------
class RoundButton(Button):
    """A flat, rounded, coloured button."""
    def __init__(self, bg=GREY, fg=TEXTCOL, **kw):
        super().__init__(background_normal="", background_down="",
                         background_color=(0, 0, 0, 0), color=fg, **kw)
        self._bg = bg
        with self.canvas.before:
            self._col = Color(*bg)
            self._rect = RoundedRectangle(radius=[18])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def set_bg(self, bg):
        self._bg = bg
        self._col.rgba = bg


class Panel(BoxLayout):
    """A BoxLayout with a rounded coloured background."""
    def __init__(self, bg=PANEL, radius=22, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            self._col = Color(*bg)
            self._rect = RoundedRectangle(radius=[radius])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size


def style_input(ti):
    ti.background_normal = ""
    ti.background_active = ""
    ti.background_color = (0.15, 0.17, 0.25, 1)
    ti.foreground_color = TEXTCOL
    ti.cursor_color = GOLD
    ti.hint_text_color = HINT
    ti.padding = [16, 14, 16, 14]
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
    pop = Popup(title="Create your Genius account", content=box, size_hint=(0.94, 0.86),
                separator_color=GOLD, title_color=GOLD)

    def field(h, pw=False, digits=False):
        t = style_input(TextInput(hint_text=h, password=pw, password_mask="*", multiline=False,
                                  input_filter="int" if digits else None,
                                  size_hint_y=None, height="50dp", font_size="18sp"))
        box.add_widget(t)
        return t
    name = field("Choose a name (letters, numbers, _)")
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
            err = create_account(name.text, pw1.text, c1.text)
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
        self.add_widget(Widget(size_hint_y=0.2))

        card = Panel(orientation="vertical", padding=26, spacing=18,
                     size_hint=(1, None), height="520dp")
        card.add_widget(Label(text="[b]Genius[/b]", markup=True, font_size="34sp",
                              color=GOLD, size_hint_y=None, height="50dp"))
        card.add_widget(Label(text="Sign in to your own Genius", font_size="16sp",
                              color=HINT, size_hint_y=None, height="26dp"))
        self.name_in = style_input(TextInput(hint_text="Your name", multiline=False,
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
                self.app.open_chat()
            else:
                code_setup_popup(lambda: self.app.open_chat(), first=True)
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

        # header bar
        header = Panel(bg=HEADER, radius=0, orientation="horizontal",
                       size_hint_y=None, height="60dp", padding=[18, 0, 18, 0])
        header.add_widget(Label(text="[b]Genius[/b]", markup=True, font_size="23sp",
                                color=GOLD, halign="left"))
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
        body = BoxLayout(orientation="vertical", padding=10, spacing=8)
        self.scroll = ScrollView()
        self.out = Label(text="", markup=True, font_size="18sp", size_hint_y=None,
                         halign="left", valign="top", color=TEXTCOL, padding=(8, 8))
        self.out.bind(width=lambda *a: setattr(self.out, "text_size", (self.out.width, None)),
                      texture_size=lambda *a: setattr(self.out, "height", self.out.texture_size[1]))
        self.scroll.add_widget(self.out)
        body.add_widget(self.scroll)
        self.add_widget(body)

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

    # ---------- header: Menu (options) and Find (search) ----------
    def options_menu(self, *_):
        box = BoxLayout(orientation="vertical", spacing=10, padding=12)
        pop = Popup(title="Options", content=box, size_hint=(0.9, 0.94),
                    separator_color=GOLD, title_color=GOLD)
        opts = [("My creations (pictures)", self.creations, BLUE),
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
            line.add_widget(Label(text=f"{n}  (since {info.get('created', '?')})", color=TEXTCOL))
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

    def exit_app(self):
        log("EXIT by menu")
        self.say(f"Goodbye {CURRENT['name']}.")
        Clock.schedule_once(lambda *_: self.app.stop(), 1.5)

    def creation_files(self):
        found = []
        for d in (".", attach_dir()):
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
        color = "f2c033" if who == "AI" else "6fb7ff"
        self.out.text += f"[b][color={color}]{who}[/color][/b]\n{text}\n\n"
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



class DecoyScreen(BoxLayout):
    """Looks like Genius, but holds nothing real. Logs everything, answers slowly, then exits."""
    def __init__(self, app, tried="", **kw):
        super().__init__(orientation="vertical", **kw)
        self.app = app
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
        try:
            switch_user(OWNER)          # leave the guest's space; next sign-in picks the account
        except Exception:
            pass
        self.root_box.clear_widgets()
        self.root_box.add_widget(LoginScreen(self))

    def open_decoy(self, tried=""):
        self.root_box.clear_widgets()
        self.root_box.add_widget(DecoyScreen(self, tried))

    def open_chat(self):
        self.root_box.clear_widgets()
        chat = ChatScreen(self)
        self.root_box.add_widget(chat)
        Clock.schedule_once(lambda *_: chat.life_start(), 2)
        Clock.schedule_once(lambda *_: chat.security_alert(), 1)


if __name__ == "__main__":
    GeniusApp().run()
