"""Orax core: everything that is not screen code. Made by Ssali Muto.
Pure Python (standard library + certifi when present) so it can be tested off the phone.
Every network function returns None / [] on any problem instead of raising.
"""
import ast
import difflib
import html
import json
import math
import os
import re
import ssl
import threading
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (Linux; Android 11; Mobile) Orax/1.0"
WIKI_H = {"User-Agent": "Orax/1.0 (Android app; https://github.com/ssalimuto/Genius-app)"}
_SSL = []
LOG_FILE = None          # set by the app to a private file


def log(msg):
    """Private log line (never shown to the user)."""
    try:
        if LOG_FILE:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(msg).replace("\n", " | ")[:2000] + "\n")
    except Exception:
        pass


def ssl_ctx():
    if not _SSL:
        try:
            import certifi
            _SSL.append(ssl.create_default_context(cafile=certifi.where()))
        except Exception:
            _SSL.append(ssl.create_default_context())
    return _SSL[0]


# ------------------------------------------------------------------ network (never raises)
OFFLINE = {"force": False}     # tests switch the network off with this


def http_get(url, timeout=20, headers=None, data=None, max_bytes=3_000_000):
    """Returns bytes or None."""
    if OFFLINE["force"]:
        return None
    try:
        h = {"User-Agent": UA, "Accept": "*/*"}
        h.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=h)
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx()) as r:
            return r.read(max_bytes)
    except Exception as e:
        log("GET %s: %s" % (url.split("?")[0][:80], type(e).__name__))
        return None


def get_json(url, timeout=20, headers=None, data=None):
    b = http_get(url, timeout, headers, data)
    if not b:
        return None
    try:
        return json.loads(b.decode("utf-8", "ignore"))
    except Exception:
        return None


def post_json(url, payload, timeout=30, headers=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    return get_json(url, timeout, h, json.dumps(payload).encode())


def online(timeout=4):
    if OFFLINE["force"]:
        return False
    import socket
    for host in (("1.1.1.1", 443), ("8.8.8.8", 53)):
        try:
            socket.create_connection(host, timeout=timeout).close()
            return True
        except Exception:
            pass
    return False


# ------------------------------------------------------------------ small JSON stores
class Store:
    def __init__(self, path, default):
        self.path = path
        self.default = default
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, type(self.default)):
                return d
        except Exception:
            pass
        return json.loads(json.dumps(self.default))

    def save(self):
        with self.lock:
            try:
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except Exception as e:
                log("save %s: %s" % (os.path.basename(self.path), e))


def new_id():
    return "%x%04x" % (int(time.time() * 1000), int.from_bytes(os.urandom(2), "big"))


def norm(t):
    return re.sub(r"[^a-z0-9 ]+", "", str(t).lower()).strip()


# ------------------------------------------------------------------ memory
KINDS = ("fact", "skill", "location", "goal", "correction")


class Memory(Store):
    def __init__(self, path):
        super().__init__(path, {"facts": []})

    @property
    def facts(self):
        return self.data.setdefault("facts", [])

    def add(self, text, kind="fact"):
        text = re.sub(r"\s+", " ", str(text)).strip(" .,!;:")
        if len(text) < 2:
            return None
        kind = kind if kind in KINDS else "fact"
        n = norm(text)
        for f in self.facts:
            if norm(f["text"]) == n and f["kind"] == kind:
                return None
        f = {"id": new_id(), "text": text[:300], "kind": kind, "ts": int(time.time())}
        self.facts.append(f)
        del self.facts[:-200]
        self.save()
        return f

    def delete(self, fid):
        before = len(self.facts)
        self.data["facts"] = [f for f in self.facts if f["id"] != fid]
        self.save()
        return len(self.facts) < before

    def clear(self):
        self.data["facts"] = []
        self.save()

    def of(self, kind):
        return [f["text"] for f in self.facts if f["kind"] == kind]

    def skills_text(self):
        return " ".join(self.of("skill")) or "Android apps, Python"

    def context(self):
        lines = []
        for kind, label in (("correction", "Corrections the user gave (always follow these)"),
                            ("skill", "Skills"), ("location", "Location"), ("goal", "Goals"), ("fact", "Other facts")):
            items = self.of(kind)[-15:]
            if items:
                lines.append(label + ": " + "; ".join(items))
        return "\n".join(lines)


_SKILL_WORDS = r"(build|make|code|program|write|design|fix|repair|teach|edit|draw|sell|speak|use|develop|create)"
_RX_REMEMBER = re.compile(r"^\s*(?:please\s+)?remember(?:\s+that)?[\s,:]+(.{2,300})$", re.I)
_RX_SKILLS = [
    re.compile(r"\bi\s+(?:can|know how to)\s+(" + _SKILL_WORDS + r"\b[^.!?\n]{2,70})", re.I),
    re.compile(r"\bi(?:'m| am)\s+good at\s+([^.!?\n]{2,60})", re.I),
    re.compile(r"\bmy skills? (?:is|are|include)\s+([^.!?\n]{2,80})", re.I),
    re.compile(r"\bi know\s+((?:python|java|kotlin|kivy|flutter|html|css|javascript|php|excel|graphic design|"
               r"video editing|photoshop|canva)[^.!?\n]{0,50})", re.I),
]
_RX_LOC = [re.compile(r"\b[Ii]\s+(?:live|stay)\s+in\s+([A-Z][A-Za-z' -]{1,40}(?:,\s*[A-Z][A-Za-z' -]{1,30})?)"),
           re.compile(r"\b[Ii](?:'m| am)\s+(?:from|based in)\s+([A-Z][A-Za-z' -]{1,40}(?:,\s*[A-Z][A-Za-z' -]{1,30})?)")]
_RX_GOAL = [re.compile(r"\bmy goal is(?: to)?\s+([^.!?\n]{3,120})", re.I),
            re.compile(r"\bi want to\s+((?:earn|make|save|get|become|learn|build|start|buy)\b[^.!?\n]{3,120})", re.I)]


def extract_facts(text):
    """Things worth remembering in a message: list of (kind, text)."""
    out = []
    t = str(text or "").strip()
    m = _RX_REMEMBER.match(t)
    if m:
        out.append(("fact", m.group(1)))
        return out
    for rx in _RX_SKILLS:
        for m in rx.finditer(t):
            out.append(("skill", m.group(1)))
    for rx in _RX_LOC:
        m = rx.search(t)
        if m:
            out.append(("location", m.group(1)))
    for rx in _RX_GOAL:
        m = rx.search(t)
        if m:
            out.append(("goal", m.group(1)))
    return [(k, v.strip(" .,")) for k, v in out]


_RX_CORR = re.compile(r"^\s*(?:no[,.!]?\s+)?(?:that'?s|that is|this is|you'?re|you are|it'?s)\s+"
                      r"(?:wrong|incorrect|not right|not true|false)\b[\s,.!:;-]*"
                      r"(?:(?:it'?s|it is|the answer is|actually|the right answer is|correct is)\b[\s:,-]*)?(.*)$", re.I)
_RX_CORR2 = re.compile(r"^\s*(?:correction|actually)\s*[:,-]\s*(.{2,})$", re.I)


def detect_correction(text):
    """Returns the corrected fact ('' when the user only said it was wrong) or None."""
    t = str(text or "").strip()
    m = _RX_CORR.match(t) or _RX_CORR2.match(t)
    if not m:
        return None
    return m.group(1).strip(" .") if m.lastindex else ""


# ------------------------------------------------------------------ settings
DEFAULT_SETTINGS = {"key_fast": "", "key_g": "", "lang": "en", "low_data": False,
                    "brief_day": "", "seen_jobs": [], "notify_asked": False}


class Settings(Store):
    def __init__(self, path):
        super().__init__(path, dict(DEFAULT_SETTINGS))
        for k, v in DEFAULT_SETTINGS.items():
            self.data.setdefault(k, v)

    def get(self, k):
        return self.data.get(k, DEFAULT_SETTINGS.get(k))

    def set(self, k, v):
        self.data[k] = v
        self.save()


# ------------------------------------------------------------------ AI (free first, keys optional)
FREE_URL = "https://text.pollinations.ai/" + "open" + "ai"
FREE_GET = "https://text.pollinations.ai/"
FREE_MODEL = "open" + "ai"
FAST_URL = "https://api." + "gr" + "oq.com/" + "open" + "ai/v1/chat/completions"
FAST_MODELS = ["lla" + "ma-3.3-70b-versatile", "lla" + "ma-3.1-8b-instant"]
G_BASE = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s"
G_MODELS = ["gem" + "ini-flash-latest", "gem" + "ini-2.5-flash"]

NO_ANSWER = "I couldn't get an answer right now. Check your internet and try again in a moment."

_VENDOR = re.compile(r"\b(Chat ?GPT|Open ?AI|GPT-?\d[\w.-]*|Anthro" r"pic|Cla" r"ude|Gem" r"ini|Lla" r"ma|Meta AI|"
                     r"Gro" r"q|Mis" r"tral|Deep" r"Seek|Polli" r"nations(?:\.ai)?|Qw" r"en)\b", re.I)
_IDENT = re.compile(r"\b(i am|i'm|my name|made by|created by|developed by|trained by|built by|powered by|"
                    r"language model|ai model|assistant)\b", re.I)


def clean_reply(t):
    """Removes ads, reasoning leftovers and vendor self-descriptions."""
    if not t:
        return ""
    t = str(t).replace("\r", "")
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    keep = []
    for line in t.split("\n"):
        if re.search(r"polli" r"nations", line, re.I) and re.search(r"(support|powered|ad\b|sponsor|free text|\.ai)", line, re.I):
            continue
        if _VENDOR.search(line) and _IDENT.search(line):
            line = _VENDOR.sub("Orax", line)
        keep.append(line)
    t = "\n".join(keep).strip()
    t = re.sub(r"\n?-{3,}\s*$", "", t).strip()
    return t


def system_prompt(memory=None, lang="en", extra=""):
    today = time.strftime("%A %d %B %Y")
    s = ("You are Orax, a personal helper app made by Ssali Muto in Uganda. You help a young student developer "
         "in Uganda find real, free ways to earn money and plan them step by step. Today is %s.\n"
         "Rules: be honest and practical; never promise income or guaranteed money; prefer free options that work "
         "in Uganda (Mobile Money, local shops, schools, online gigs); warn about scams and upfront fees; no trading "
         "or crypto schemes. If you are not sure of a fact, say so plainly. If a request is unclear, ask ONE short "
         "question instead of guessing. Keep answers short and clear, with numbered steps when useful. "
         "If asked who made you, say you are Orax, made by Ssali Muto. Never name the company or model behind you." % today)
    if lang == "lg":
        s += ("\nReply in simple everyday Luganda. Keep app names, links, numbers and technical words in English. "
              "If you can't say something well in Luganda, add a short English line.")
    else:
        s += "\nReply in simple, clear English."
    if memory is not None:
        ctx = memory.context()
        if ctx:
            s += "\nWhat you know about the user (use it; corrections override everything else):\n" + ctx
    if extra:
        s += "\n" + extra
    return s


def _free_post(messages, max_tokens):
    d = post_json(FREE_URL, {"model": FREE_MODEL, "messages": messages, "max_tokens": max_tokens + 400,
                             "private": True}, timeout=45, headers={"User-Agent": UA})
    try:
        return clean_reply(d["choices"][0]["message"].get("content") or "")
    except Exception:
        return ""


def _free_get(messages):
    sysm = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = messages[-1]["content"]
    q = urllib.parse.quote(user[:1500])
    url = FREE_GET + q + "?" + urllib.parse.urlencode({"system": sysm[:1200], "private": "true"})
    b = http_get(url, timeout=45)
    if not b:
        return ""
    t = b.decode("utf-8", "ignore")
    if t.lstrip().startswith("{"):
        return ""
    return clean_reply(t)


_FREE_LOCK = threading.Lock()   # the free service allows one request at a time per phone


def ask_free(messages, max_tokens=700):
    with _FREE_LOCK:
        if OFFLINE["force"]:
            return ""
        for attempt in range(2):
            for fn in (lambda: _free_post(messages, max_tokens), lambda: _free_get(messages)):
                try:
                    t = fn()
                    if t:
                        return t
                except Exception as e:
                    log("free: %s" % type(e).__name__)
            if attempt == 0:
                time.sleep(2.5)
    return ""


def ask_fast(messages, key, max_tokens=700):
    for m in FAST_MODELS:
        d = post_json(FAST_URL, {"model": m, "messages": messages, "max_tokens": max_tokens, "temperature": 0.5},
                      timeout=30, headers={"Authorization": "Bearer " + key, "User-Agent": UA})
        try:
            t = clean_reply(d["choices"][0]["message"]["content"])
            if t:
                return t
        except Exception:
            pass
    return ""


def ask_g(messages, key, max_tokens=700):
    sysm = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] != "system"]
    body = {"contents": contents, "systemInstruction": {"parts": [{"text": sysm}]},
            "generationConfig": {"maxOutputTokens": max_tokens + 1200, "temperature": 0.5}}
    for m in G_MODELS:
        d = post_json(G_BASE % (m, urllib.parse.quote(key)), body, timeout=35)
        try:
            t = clean_reply("".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]))
            if t:
                return t
        except Exception:
            pass
    return ""


def ask_ai(prompt, settings=None, memory=None, history=None, system=None, max_tokens=700,
           hedge_after=6.0, deadline=50.0):
    """Asks the user's keyed AIs first; if they are slow or fail, the free one joins; first good answer wins.
    Returns text, or '' when nothing answered (the caller shows NO_ANSWER)."""
    import queue
    lang = settings.get("lang") if settings else "en"
    msgs = [{"role": "system", "content": system or system_prompt(memory, lang)}]
    for h in (history or [])[-8:]:
        if h.get("text"):
            msgs.append({"role": "assistant" if h.get("who") == "orax" else "user", "content": h["text"][:2500]})
    msgs.append({"role": "user", "content": str(prompt)[:8000]})
    jobs = []
    if settings:
        if (settings.get("key_fast") or "").strip():
            k = settings.get("key_fast").strip()
            jobs.append(lambda: ask_fast(msgs, k, max_tokens))
        if (settings.get("key_g") or "").strip():
            k2 = settings.get("key_g").strip()
            jobs.append(lambda: ask_g(msgs, k2, max_tokens))
    q = queue.Queue()

    def run(fn):
        try:
            q.put(fn() or "")
        except Exception as e:
            log("ai: %s" % type(e).__name__)
            q.put("")
    for fn in jobs:
        threading.Thread(target=run, args=(fn,), daemon=True).start()
    waiting = len(jobs)
    free_on = False
    if not jobs:
        free_on = True
        waiting += 1
        threading.Thread(target=run, args=(lambda: ask_free(msgs, max_tokens),), daemon=True).start()
    start = time.time()
    while waiting and time.time() - start < deadline:
        try:
            r = q.get(timeout=0.25)
            waiting -= 1
            if r:
                return r
        except Exception:
            pass
        if not free_on and (waiting == 0 or time.time() - start > hedge_after):
            free_on = True
            waiting += 1
            threading.Thread(target=run, args=(lambda: ask_free(msgs, max_tokens),), daemon=True).start()
    return ""


# ------------------------------------------------------------------ answer cache (offline / low data)
class AnswerCache(Store):
    def __init__(self, path):
        super().__init__(path, {"items": []})

    def put(self, q, a):
        if not a or a == NO_ANSWER:
            return
        items = [i for i in self.data["items"] if norm(i["q"]) != norm(q)]
        items.append({"q": q[:400], "a": a[:6000], "ts": int(time.time())})
        self.data["items"] = items[-40:]
        self.save()

    def find(self, q):
        n = norm(q)
        best, score = None, 0.0
        for i in self.data["items"]:
            s = difflib.SequenceMatcher(None, n, norm(i["q"])).ratio()
            if s > score:
                best, score = i, s
        return best if score >= 0.86 else None


# ------------------------------------------------------------------ opportunities
OPPORTUNITIES = [
    {"id": "fiverr", "title": "Sell an app-building gig on Fiverr",
     "tags": ["android", "python", "apps", "online", "dev"],
     "summary": "Offer a small, clear service such as 'I will build a simple Android app' or 'fix bugs in your Python "
                "script'. Free to join; Fiverr keeps 20% of each order and pays out through Payoneer or PayPal.",
     "steps": ["Write one clear gig: what you build, how long it takes, one starter price.",
               "Add 3 screenshots of an app you already made as your portfolio.",
               "Answer every message within a few hours; first orders often come slowly.",
               "Deliver on time and ask happy buyers for a review."],
     "link": "https://www.fiverr.com/start_selling", "pay": "Starter gigs often begin around $5-$30 each."},
    {"id": "upwork", "title": "Bid for small jobs on Upwork",
     "tags": ["android", "python", "dev", "writing", "online"],
     "summary": "Clients post small fixed-price tasks. You get some free 'Connects' to apply each month; more cost money, "
                "so apply only to jobs that fit your skills exactly.",
     "steps": ["Make a profile focused on one skill (for example Android bug fixes).",
               "Apply only to small, clear jobs posted in the last day.",
               "Write short proposals that mention the client's exact problem.",
               "Never pay anyone outside Upwork to 'unlock' a job."],
     "link": "https://www.upwork.com/nx/signup/?dest=home", "pay": "Varies by job; first jobs are usually small."},
    {"id": "shop_apps", "title": "Build simple apps or menus for local shops and schools",
     "tags": ["android", "apps", "local", "dev", "python"],
     "summary": "Many shops, salons, clinics and schools near you want a simple price list app, booking form, "
                "or a results page. Show a working demo on your phone and agree a small fee.",
     "steps": ["Pick one type of business (for example schools) and build one demo.",
               "Visit 5 places near you and show the demo on your phone.",
               "Agree the price and what is included before you start; ask for part payment on delivery.",
               "Offer monthly updates for a small fee."],
     "link": "", "pay": "You set the price with each client."},
    {"id": "wa_business", "title": "Set up WhatsApp Business for local shops",
     "tags": ["local", "phone", "marketing"],
     "summary": "Help shop owners set up WhatsApp Business: catalogue with photos and prices, greeting and away "
                "messages, and quick replies. Uses only a phone, so it is free to start.",
     "steps": ["Set up your own WhatsApp Business as an example.",
               "Offer 2 shops a free setup in exchange for a review or referral.",
               "Then charge a small fee per setup and offer weekly catalogue updates."],
     "link": "https://business.whatsapp.com/", "pay": "Small fee per shop; repeat work from updates."},
    {"id": "repair", "title": "Phone and computer help and repair",
     "tags": ["repair", "local", "phone"],
     "summary": "Software help is the easiest start: setting up phones, freeing storage, installing apps, removing "
                "malware, backing up photos. Hardware repair needs training and tools, so start with software.",
     "steps": ["List the software fixes you can already do well.",
               "Tell friends, family and school mates; ask for referrals.",
               "Learn one new fix each week from free videos.",
               "Never ask for or keep anyone's passwords or Mobile Money PIN."],
     "link": "", "pay": "Per job; depends on the fix."},
    {"id": "tutoring", "title": "Tutor computer skills or school subjects",
     "tags": ["teaching", "local", "python"],
     "summary": "Teach younger students or adults basic computer skills, typing, coding with Python, or a subject "
                "you are strong in. Start with small groups to save time.",
     "steps": ["Choose one subject and make a 4-week simple plan.",
               "Ask parents or your school about students who need help.",
               "Charge per session or per month; agree the times clearly."],
     "link": "", "pay": "Per session or per month."},
    {"id": "jiji", "title": "Sell things you no longer need on Jiji",
     "tags": ["selling", "local", "phone"],
     "summary": "List items with clear photos and an honest price. Meet buyers in safe public places and never "
                "send items before you are paid.",
     "steps": ["Take clear photos in daylight.", "Write an honest title and description with the price.",
               "Meet buyers in a public place; check payment before handing over."],
     "link": "https://jiji.ug/", "pay": "Depends on what you sell."},
    {"id": "content", "title": "Make how-to videos on YouTube or TikTok",
     "tags": ["content", "writing", "online", "android", "phone"],
     "summary": "Short videos that teach one thing (how to build an app, phone tips, school tips). Income from "
                "platforms needs many followers and takes months, so treat it as a long-term project.",
     "steps": ["Pick one topic you know well.", "Post short videos regularly (for example 3 per week).",
               "Reply to comments; use them for new video ideas.",
               "Use your channel to find clients for your other services."],
     "link": "https://www.youtube.com/", "pay": "Slow to start; no income is certain."},
    {"id": "writing", "title": "Write articles or app descriptions for clients",
     "tags": ["writing", "online"],
     "summary": "Businesses and app makers need short articles, product descriptions and app store text. "
                "Build 3 sample pieces first.",
     "steps": ["Write 3 short samples on topics you know.", "Offer the service on Fiverr or to local businesses.",
               "Always write your own words; copied text gets accounts closed."],
     "link": "", "pay": "Per article; small to start."},
    {"id": "hackathons", "title": "Enter hackathons and coding competitions",
     "tags": ["android", "python", "dev", "competition"],
     "summary": "Online hackathons are free to enter; some give prizes, mentors or internships. Prizes are never "
                "certain, but every project grows your portfolio.",
     "steps": ["Check Devpost and local tech hubs for open events.", "Join a team or go solo with a small idea.",
               "Finish a working demo, even if simple.", "Put the project on GitHub for your portfolio."],
     "link": "https://devpost.com/hackathons", "pay": "Prizes only for winners; not guaranteed."},
    {"id": "dev_programs", "title": "Learn mobile money and SMS APIs (Africa's Talking, MTN MoMo sandbox)",
     "tags": ["dev", "python", "android", "apps"],
     "summary": "Both offer free sandbox accounts for developers. Learning SMS and mobile money payments lets you "
                "build paid features for local businesses.",
     "steps": ["Create a free sandbox account.", "Send a test SMS or test payment from a small Python script.",
               "Add this skill to your portfolio and offers."],
     "link": "https://developers.africastalking.com/", "pay": "A skill that raises what you can charge."},
    {"id": "grants", "title": "Apply for student scholarships, grants and fellowships",
     "tags": ["student", "competition", "online"],
     "summary": "Many programmes for young African tech students are free to apply. Read the official page only; "
                "real programmes never ask you to pay an application or 'processing' fee.",
     "steps": ["Search for programmes open to students in Uganda.",
               "Read the official page and the deadline.",
               "Prepare a short CV and a project you built.",
               "Apply early; never pay any fee to apply."],
     "link": "", "pay": "Competitive; not guaranteed."},
]

DEFAULT_SKILLS = "android apps python dev"


def match_opportunities(skills_text, opps=None):
    """Ranks offline opportunities by how well their tags fit the user's skills."""
    words = set(re.findall(r"[a-z]+", (skills_text or "").lower())) | set(DEFAULT_SKILLS.split())
    synonyms = {"kivy": "python", "kotlin": "android", "java": "android", "code": "dev", "coding": "dev",
                "programming": "dev", "write": "writing", "writer": "writing", "teach": "teaching",
                "repair": "repair", "fix": "repair", "video": "content", "sell": "selling", "app": "apps"}
    words |= {synonyms[w] for w in list(words) if w in synonyms}
    ranked = []
    for i, o in enumerate(opps or OPPORTUNITIES):
        score = sum(2 for t in o["tags"] if t in words) + (1 if "local" in o["tags"] else 0)
        ranked.append((-score, i, o))
    ranked.sort()
    return [o for _, _, o in ranked]


SENIOR = re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager|director|head|architect|vp|chief|expert|"
                    r"\d+\+?\s*years)\b", re.I)
DEV = re.compile(r"\b(developer|engineer|python|android|mobile|flutter|kotlin|java|frontend|front-end|backend|"
                 r"back-end|full.?stack|web|software|javascript|react|django|qa|tester|programmer|devops)\b", re.I)
WRITE = re.compile(r"\b(writer|writing|content|copywriter|copy|editor|blog|documentation|proofread|translator)\b", re.I)
JUNIOR = re.compile(r"\b(junior|jr\.?|entry|intern|internship|graduate|trainee|associate|beginner)\b", re.I)
WORLD = re.compile(r"(worldwide|anywhere|global|africa|uganda|emea|international|remote$)", re.I)


def _date10(s):
    s = str(s or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(s)))
    except Exception:
        return ""


def keep_job(j):
    title = j.get("title", "")
    if SENIOR.search(title):
        return False
    return bool(DEV.search(title) or WRITE.search(title) or JUNIOR.search(title)) and not SENIOR.search(title)


def job_kind(j):
    return "Writing" if WRITE.search(j.get("title", "")) else "Dev"


def fetch_remotive():
    out, seen = [], set()
    for qs in ("search=junior", "search=python", "search=android", "category=writing"):
        d = get_json("https://remotive.com/api/remote-jobs?" + qs + "&limit=60", timeout=25)
        for x in (d or {}).get("jobs", []) if isinstance(d, dict) else []:
            try:
                if x["url"] in seen:
                    continue
                seen.add(x["url"])
                out.append({"id": "rv%s" % x.get("id"), "title": html.unescape(x.get("title", "")).strip(),
                            "company": html.unescape(x.get("company_name", "")).strip(), "url": x["url"],
                            "salary": (x.get("salary") or "").strip(), "date": _date10(x.get("publication_date")),
                            "where": (x.get("candidate_required_location") or "").strip(), "source": "Remotive"})
            except Exception:
                pass
    return out


def fetch_remoteok():
    d = get_json("https://remoteok.com/api", timeout=25)
    out = []
    for x in d or [] if isinstance(d, list) else []:
        try:
            if not isinstance(x, dict) or not x.get("position"):
                continue
            sal = ""
            if x.get("salary_min") or x.get("salary_max"):
                sal = "$%s - $%s a year" % (format(int(x.get("salary_min") or 0), ","), format(int(x.get("salary_max") or 0), ","))
            out.append({"id": "ok%s" % x.get("id"), "title": html.unescape(x.get("position", "")).strip(),
                        "company": html.unescape(x.get("company", "")).strip(),
                        "url": x.get("url") or ("https://remoteok.com/remote-jobs/%s" % x.get("slug")),
                        "salary": sal, "date": _date10(x.get("date") or x.get("epoch")),
                        "where": (x.get("location") or "").strip(), "source": "Remote OK"})
        except Exception:
            pass
    return out


def filter_jobs(jobs):
    kept = [j for j in jobs if keep_job(j)]
    for j in kept:
        j["kind"] = job_kind(j)
        j["open_to_you"] = (not j.get("where")) or bool(WORLD.search(j["where"]))
    kept.sort(key=lambda j: (not j["open_to_you"], not JUNIOR.search(j["title"]), ""), reverse=False)
    kept.sort(key=lambda j: j.get("date", ""), reverse=True)
    kept.sort(key=lambda j: not j["open_to_you"])
    return kept


class JobCache(Store):
    def __init__(self, path):
        super().__init__(path, {"ts": 0, "jobs": []})

    def fresh(self, max_age=6 * 3600):
        return self.data["jobs"] and time.time() - self.data["ts"] < max_age


def get_jobs(cache, force=False, search=""):
    """Live jobs (cached 6 h so the free APIs are not hammered). Returns (jobs, from_cache)."""
    if search:
        d = get_json("https://remotive.com/api/remote-jobs?search=%s&limit=40" % urllib.parse.quote(search), timeout=25)
        jobs = []
        for x in (d or {}).get("jobs", []) if isinstance(d, dict) else []:
            jobs.append({"id": "rv%s" % x.get("id"), "title": html.unescape(x.get("title", "")), "url": x.get("url", ""),
                         "company": html.unescape(x.get("company_name", "")), "salary": x.get("salary") or "",
                         "date": _date10(x.get("publication_date")), "source": "Remotive",
                         "where": x.get("candidate_required_location") or ""})
        return filter_jobs(jobs), False
    if cache and not force and cache.fresh():
        return cache.data["jobs"], True
    jobs = filter_jobs(fetch_remotive() + fetch_remoteok())
    if jobs:
        if cache:
            cache.data = {"ts": int(time.time()), "jobs": jobs[:150]}
            cache.save()
        return jobs, False
    return (cache.data["jobs"] if cache else []), True


# ------------------------------------------------------------------ plans and tasks
def plan_prompt(title, detail=""):
    return ("Make a practical step-by-step plan for this way to earn money: %s.\n%s\n"
            "Give 5 to 8 short numbered steps the user can do this week with no money. Each step one line, starting "
            "with a verb. No intro, no closing text, no promises of income." % (title, detail))


def parse_steps(text):
    steps = []
    for line in str(text or "").split("\n"):
        m = re.match(r"^\s*(?:step\s*)?(\d{1,2})[.):\-]\s*(.+)$", line, re.I) or re.match(r"^\s*[-*\u2022]\s+(.+)$", line)
        if m:
            s = re.sub(r"\*\*|__", "", m.group(m.lastindex)).strip()
            if len(s) > 3:
                steps.append(s[:240])
    return steps[:10]


def offline_plan(opp):
    if opp and opp.get("steps"):
        return list(opp["steps"])
    return ["Read the full job post and note what it asks for.", "Check the company's own website.",
            "Prepare a short CV or portfolio link that matches the post.",
            "Write a short, personal application.", "Apply and note the date here.",
            "Never pay any fee to apply."]


class Tasks(Store):
    def __init__(self, path):
        super().__init__(path, {"plans": [], "reminders": []})

    @property
    def plans(self):
        return self.data.setdefault("plans", [])

    @property
    def reminders(self):
        return self.data.setdefault("reminders", [])

    def add_plan(self, title, steps, source=""):
        p = {"id": new_id(), "title": title[:120], "source": source,
             "steps": [{"text": s, "done": False} for s in steps if s], "created": int(time.time())}
        self.plans.insert(0, p)
        self.save()
        return p

    def toggle(self, pid, i, done=None):
        for p in self.plans:
            if p["id"] == pid and 0 <= i < len(p["steps"]):
                p["steps"][i]["done"] = (not p["steps"][i]["done"]) if done is None else bool(done)
                self.save()
                return p["steps"][i]["done"]
        return None

    def delete_plan(self, pid):
        self.data["plans"] = [p for p in self.plans if p["id"] != pid]
        self.data["reminders"] = [r for r in self.reminders if r.get("plan") != pid]
        self.save()

    def add_reminder(self, text, at, plan=""):
        r = {"id": new_id(), "text": text[:200], "at": int(at), "plan": plan, "fired": False}
        self.reminders.append(r)
        self.save()
        return r

    def delete_reminder(self, rid):
        self.data["reminders"] = [r for r in self.reminders if r["id"] != rid]
        self.save()

    def due(self, now=None):
        now = now or time.time()
        out = [r for r in self.reminders if not r["fired"] and r["at"] <= now]
        for r in out:
            r["fired"] = True
        if out:
            self.save()
        return out

    def open_steps(self):
        return [(p["title"], s["text"]) for p in self.plans for s in p["steps"] if not s["done"]]


_UNITS_T = {"min": 60, "mins": 60, "minute": 60, "minutes": 60, "m": 60, "hour": 3600, "hours": 3600, "hr": 3600,
            "hrs": 3600, "h": 3600, "day": 86400, "days": 86400, "sec": 1, "secs": 1, "seconds": 1, "second": 1}


def parse_reminder(text, now=None):
    """'remind me to call Sam in 20 minutes' / 'at 5pm' / 'tomorrow at 8'. Returns (what, timestamp) or None."""
    now = now or time.time()
    t = str(text or "").strip()
    m = re.match(r"^\s*(?:please\s+)?remind me(?:\s+to)?\s+(.+)$", t, re.I)
    if not m:
        return None
    body = m.group(1)
    mm = re.search(r"\bin\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|m|hours?|hrs?|h|days?)\b", body, re.I)
    if mm:
        at = now + float(mm.group(1)) * _UNITS_T[mm.group(2).lower()]
        what = (body[:mm.start()] + body[mm.end():]).strip(" ,.")
        return (what or "Reminder", int(at))
    mm = re.search(r"\b(tomorrow\s+)?(?:at\s+)(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b(\s+tomorrow)?", body, re.I)
    if mm:
        h, mi = int(mm.group(2)), int(mm.group(3) or 0)
        ap = (mm.group(4) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        if h > 23 or mi > 59:
            return None
        lt = time.localtime(now)
        at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, mi, 0, 0, 0, -1))
        if mm.group(1) or mm.group(5):
            at += 86400
        elif at <= now:
            at += 86400
        what = (body[:mm.start()] + body[mm.end():]).strip(" ,.")
        return (what or "Reminder", int(at))
    return None


# ------------------------------------------------------------------ earnings
class Earnings(Store):
    def __init__(self, path):
        super().__init__(path, {"items": []})

    @property
    def items(self):
        return self.data.setdefault("items", [])

    def add(self, amount, kind="earn", opp="", note="", ts=None):
        try:
            a = float(str(amount).replace(",", "").strip())
        except Exception:
            return None
        if not (a > 0) or a > 1e12:
            return None
        e = {"id": new_id(), "amount": round(a, 2), "kind": "spend" if kind == "spend" else "earn",
             "opp": (opp or "Other").strip()[:80] or "Other", "note": (note or "").strip()[:200],
             "ts": int(ts or time.time())}
        self.items.insert(0, e)
        self.save()
        return e

    def delete(self, eid):
        self.data["items"] = [e for e in self.items if e["id"] != eid]
        self.save()


def week_start(now=None):
    lt = time.localtime(now or time.time())
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    return midnight - lt.tm_wday * 86400


def week_totals(items, now=None):
    start = week_start(now)
    earned = sum(e["amount"] for e in items if e["kind"] == "earn" and e["ts"] >= start)
    spent = sum(e["amount"] for e in items if e["kind"] == "spend" and e["ts"] >= start)
    return {"earned": earned, "spent": spent, "net": earned - spent}


def by_opportunity(items):
    out = {}
    for e in items:
        d = out.setdefault(e["opp"], {"earned": 0.0, "spent": 0.0})
        d["earned" if e["kind"] == "earn" else "spent"] += e["amount"]
    return out


def ugx(x):
    x = float(x or 0)
    s = "UGX " + format(int(round(abs(x))), ",")
    return "-" + s if x < 0 else s


# ------------------------------------------------------------------ scam check
SCAM_RULES = [
    ("fee", "Asks you to pay first (registration, training, activation or 'processing' fee)",
     r"(registration|joining|training|activation|processing|application|membership|starter|kit|clearance|"
     r"verification|unlock)\s*(fee|fees|charge|payment)|pay (?:a |the )?(?:small )?fee|pay (?:first|before|to (?:start|join|get|receive|unlock))|"
     r"send (?:us )?(?:ugx|shs|\$)?\s*\d[\d,]*\s*(?:ugx|shs|shillings)?\s*(?:to|for)\s*(?:register|start|join|activate)|deposit (?:to|before)"),
    ("guarantee", "Promises guaranteed or risk-free profit",
     r"guarante\w*|risk[- ]free|no risk|100\s*% (?:profit|sure|safe)|sure (?:profit|income|money)|never lose"),
    ("doubling", "Crypto, forex or 'double your money' scheme",
     r"double your (?:money|investment|cash)|\bdoubl\w* (?:in|within)|bitcoin|crypto|usdt|forex|binary option|"
     r"\b\d{2,4}\s*% (?:daily|weekly|per day|a day|returns?|roi|profit)|daily (?:returns?|profit|interest)|invest(?:ment)? plan"),
    ("secret", "Asks for your PIN, OTP, password or verification code",
     r"\bpin\b|\botp\b|one[- ]time (?:password|code)|verification code|password|security code|mobile money code|"
     r"send (?:me|us) the code"),
    ("urgent", "Pushes you to hurry (today only, limited slots)",
     r"urgent|act (?:now|fast)|today only|limited (?:slots?|spaces?|time)|only \d+ (?:slots?|spaces?|people) left|"
     r"before midnight|expires? (?:today|tonight)"),
    ("too_good", "Very high pay for very little work",
     r"(?:earn|make|get)\s+(?:ugx|shs|\$|usd)?\s*\d[\d,]{2,}\s*(?:ugx|shs|usd|\$)?\s*(?:per|a|every)\s*(?:day|hour)|"
     r"no experience (?:needed|required).{0,40}(?:\$|ugx|shs)\s*\d|work (?:from home|2 hours).{0,30}(?:earn|make)|easy money|quick money"),
    ("chat_only", "Only talks on WhatsApp or Telegram and skips a real interview",
     r"(?:contact|message|chat|text)\s+(?:me|us|hr)?\s*(?:only\s+)?(?:on|via)\s+(?:whatsapp|telegram)|telegram|"
     r"no interview|hired immediately"),
    ("personal_pay", "Wants money sent to a personal Mobile Money number",
     r"(?:send|pay|deposit)\b.{0,40}(?:mobile money|momo|airtel money|mm)\b|(?:mobile money|momo|airtel money)\s*(?:number|no\.?)\s*[:\-]?\s*\+?\d"),
    ("ids", "Asks for ID photos or bank card details before any contract",
     r"(?:national id|passport|id card|nin)\b.{0,30}(?:photo|copy|picture|send)|(?:send|share).{0,20}(?:national id|passport|card number|cvv)|\bcvv\b"),
    ("recruit", "Pays you mainly for bringing other people (pyramid)",
     r"recruit|refer (?:\d+|friends|people) (?:to|and) earn|downline|referral (?:bonus|income)|pyramid|multi[- ]level|mlm"),
]
_SCAM_RX = [(k, d, re.compile(p, re.I)) for k, d, p in SCAM_RULES]


def scam_check(text):
    """Returns {'flags': [(key, description)], 'level': 'high'|'medium'|'low', 'summary': str}."""
    t = str(text or "")
    flags = [(k, d) for k, d, rx in _SCAM_RX if rx.search(t)]
    keys = {k for k, _ in flags}
    serious = keys & {"fee", "secret", "doubling", "guarantee", "personal_pay"}
    if serious or len(flags) >= 3:
        level, summary = "high", "High risk: this has clear scam signs. Do not pay, and never share a PIN or code."
    elif flags:
        level, summary = "medium", "Be careful: check the company on its own website before you go further."
    else:
        level, summary = "low", ("No common scam signs found by the built-in rules. That does not prove it is safe: "
                                 "never pay to get a job, and check the company yourself.")
    return {"flags": flags, "level": level, "summary": summary}


def scam_prompt(text, result):
    return ("Is this job or money offer likely a scam? Message:\n\"\"\"%s\"\"\"\nBuilt-in checks found: %s.\n"
            "Answer in 3-5 short lines: start with 'Verdict: Likely scam', 'Verdict: Be careful' or "
            "'Verdict: Looks normal, still check', then the main reasons, then what to do next. "
            "Remember real employers never charge fees to hire." % (text[:3000], ", ".join(d for _, d in result["flags"]) or "none"))


# ------------------------------------------------------------------ web tools
def _strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def ddg_search(q, n=5):
    out = []
    for url in ("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q),
                "https://lite.duckduckgo.com/lite/?q=" + urllib.parse.quote(q)):
        b = http_get(url, timeout=15, headers={"Accept": "text/html"})
        if not b:
            continue
        page = b.decode("utf-8", "ignore")
        for m in re.finditer(r'<a[^>]+class="result(?:__a|-link)"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
            href, title = m.group(1), _strip_tags(m.group(2))
            if "uddg=" in href:
                href = urllib.parse.unquote(re.search(r"uddg=([^&]+)", href).group(1))
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith("http") or "duckduckgo.com/y.js" in href or not title:
                continue
            snip = ""
            sm = re.search(r'class="result(?:__snippet|-snippet)"[^>]*>(.*?)</(?:a|td)>', page[m.end():m.end() + 3000], re.S)
            if sm:
                snip = _strip_tags(sm.group(1))
            out.append({"title": title[:150], "url": href, "snippet": snip[:300]})
            if len(out) >= n:
                return out
        if out:
            return out
    return out


def wiki_search(q, n=3):
    d = get_json("https://en.wikipedia.org/w/api.php?action=query&list=search&format=json&utf8=1&srlimit=%d&srsearch=%s"
                 % (n, urllib.parse.quote(q)), timeout=15, headers=WIKI_H)
    out = []
    try:
        for x in d["query"]["search"]:
            out.append({"title": x["title"], "snippet": _strip_tags(x.get("snippet", "")),
                        "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(x["title"].replace(" ", "_"))})
    except Exception:
        pass
    return out


def wiki_summary(title):
    d = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title.replace(" ", "_")), timeout=15, headers=WIKI_H)
    try:
        if d.get("type") == "disambiguation" or not d.get("extract"):
            return None
        return {"title": d["title"], "text": d["extract"], "url": d["content_urls"]["mobile"]["page"]}
    except Exception:
        return None


def ddg_instant(q):
    d = get_json("https://api.duckduckgo.com/?format=json&no_html=1&skip_disambig=1&q=" + urllib.parse.quote(q), timeout=15)
    try:
        if d.get("AbstractText"):
            return {"title": d.get("Heading") or q, "url": d.get("AbstractURL") or "", "snippet": d["AbstractText"][:500]}
    except Exception:
        pass
    return None


def web_search(q, n=5):
    """Free web search: results with title, url, snippet. Falls back to an instant answer and Wikipedia."""
    res = ddg_search(q, n)
    if len(res) < 3:
        ia = ddg_instant(q)
        if ia and ia["url"]:
            res.append(ia)
        for w in wiki_search(q, 3):
            if w["url"] not in [r["url"] for r in res]:
                s = wiki_summary(w["title"])
                if s:
                    w["snippet"] = s["text"][:400]
                res.append(w)
    return res[:n]


def fetch_page_text(url, limit=12000):
    if not re.match(r"^https?://", url or ""):
        return ""
    b = http_get(url, timeout=25, headers={"Accept": "text/html,text/plain"}, max_bytes=2_000_000)
    if not b:
        return ""
    t = b.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style|noscript|svg|head|nav|footer)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</li>", "\n", t)
    t = _strip_tags(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()[:limit]


def sources_prompt(question, results):
    lines = ["Sources:"]
    for i, r in enumerate(results, 1):
        lines.append("[%d] %s - %s\n%s" % (i, r["title"], r["url"], r.get("snippet", "")))
    return ("%s\n\nUsing only these sources, answer: %s\nKeep it short. Cite sources like [1]. If the sources don't "
            "answer it, say so plainly." % ("\n".join(lines), question))


def check_prompt(question, answer, results):
    lines = ["[%d] %s: %s" % (i, r["title"], r.get("snippet", "")) for i, r in enumerate(results, 1)]
    return ("Question: %s\nAnswer given: %s\nSources:\n%s\n\nDo the sources support the answer? Reply with exactly one "
            "first word: MATCHES, UNSURE or CONFLICTS. Then one short sentence why." % (question, answer[:2500], "\n".join(lines)))


def check_verdict(ai_text, results):
    """Never marks an answer as matching without sources."""
    if not results:
        return "unsure", "Unsure: no sources found to check this."
    w = (ai_text or "").strip().split()
    first = re.sub(r"[^A-Z]", "", w[0].upper()) if w else ""
    reason = " ".join(w[1:])[:300]
    if first == "MATCHES":
        return "matches", "Matches sources. " + reason
    if first == "CONFLICTS":
        return "conflicts", "Sources disagree: " + (reason or "check the links below.")
    return "unsure", "Unsure. " + (reason or "The sources don't clearly confirm it.")


# ------------------------------------------------------------------ maths, units, currency
_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b}
_FUNCS = {"sqrt": math.sqrt, "sin": lambda x: math.sin(math.radians(x)), "cos": lambda x: math.cos(math.radians(x)),
          "tan": lambda x: math.tan(math.radians(x)), "log": math.log10, "ln": math.log, "abs": abs, "round": round}
_CONSTS = {"pi": math.pi, "e": math.e}


def _ev(n):
    if isinstance(n, ast.Expression):
        return _ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
            raise ValueError("too big")
        return _OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
        v = _ev(n.operand)
        return v if isinstance(n.op, ast.UAdd) else -v
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and len(n.args) == 1:
        return _FUNCS[n.func.id](_ev(n.args[0]))
    if isinstance(n, ast.Name) and n.id in _CONSTS:
        return _CONSTS[n.id]
    raise ValueError("not allowed")


def fmt_num(v):
    if isinstance(v, float):
        if v.is_integer() and abs(v) < 1e15:
            return format(int(v), ",")
        return format(round(v, 6), ",.6f").rstrip("0").rstrip(".")
    return format(v, ",")


def calculate(expr):
    """Safe maths. Returns a string answer or None."""
    s = str(expr or "").lower().strip().rstrip("?=. ")
    s = re.sub(r"^(?:calculate|calc|what is|what's|whats|compute|solve)\s+", "", s)
    m = re.match(r"^([\d.,]+)\s*%\s*of\s*([\d.,]+)$", s)
    if m:
        try:
            a, b = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
            return fmt_num(a * b / 100.0)
        except Exception:
            return None
    s = s.replace(",", "").replace("x", "*").replace("\u00d7", "*").replace("\u00f7", "/").replace("^", "**")
    s = re.sub(r"(\d)\s*%", r"(\1/100)", s)
    if not re.search(r"\d", s) or not re.fullmatch(r"[\d\s.+\-*/()%a-z]*", s):
        return None
    try:
        v = _ev(ast.parse(s, mode="eval"))
        if isinstance(v, complex):
            return None
        return fmt_num(v)
    except Exception:
        return None


_U = {  # unit -> (dimension, factor to base)
    "mm": ("len", 0.001), "cm": ("len", 0.01), "m": ("len", 1), "km": ("len", 1000), "in": ("len", 0.0254),
    "inch": ("len", 0.0254), "inches": ("len", 0.0254), "ft": ("len", 0.3048), "foot": ("len", 0.3048),
    "feet": ("len", 0.3048), "yd": ("len", 0.9144), "yard": ("len", 0.9144), "yards": ("len", 0.9144),
    "mi": ("len", 1609.344), "mile": ("len", 1609.344), "miles": ("len", 1609.344), "metre": ("len", 1),
    "meter": ("len", 1), "metres": ("len", 1), "meters": ("len", 1), "kilometres": ("len", 1000), "kilometers": ("len", 1000),
    "g": ("mass", 0.001), "gram": ("mass", 0.001), "grams": ("mass", 0.001), "kg": ("mass", 1), "kgs": ("mass", 1),
    "kilo": ("mass", 1), "kilos": ("mass", 1), "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237),
    "pound": ("mass", 0.45359237), "pounds": ("mass", 0.45359237), "oz": ("mass", 0.0283495), "tonne": ("mass", 1000), "tonnes": ("mass", 1000),
    "ml": ("vol", 0.001), "l": ("vol", 1), "litre": ("vol", 1), "liter": ("vol", 1), "litres": ("vol", 1),
    "liters": ("vol", 1), "gallon": ("vol", 3.78541), "gallons": ("vol", 3.78541),
    "acre": ("area", 4046.86), "acres": ("area", 4046.86), "hectare": ("area", 10000), "hectares": ("area", 10000),
    "ha": ("area", 10000), "m2": ("area", 1), "sqm": ("area", 1), "km2": ("area", 1e6), "sqft": ("area", 0.092903),
    "kmh": ("speed", 1 / 3.6), "km/h": ("speed", 1 / 3.6), "mph": ("speed", 0.44704), "m/s": ("speed", 1),
    "kb": ("data", 1e3), "mb": ("data", 1e6), "gb": ("data", 1e9), "tb": ("data", 1e12),
    "c": ("temp", None), "celsius": ("temp", None), "f": ("temp", None), "fahrenheit": ("temp", None),
    "k": ("temp", None), "kelvin": ("temp", None),
}
CUR = {"usd": "USD", "dollar": "USD", "dollars": "USD", "$": "USD", "ugx": "UGX", "ush": "UGX", "shs": "UGX",
       "shillings": "UGX", "shilling": "UGX", "kes": "KES", "ksh": "KES", "tzs": "TZS", "rwf": "RWF", "eur": "EUR",
       "euro": "EUR", "euros": "EUR", "gbp": "GBP", "sterling": "GBP", "ngn": "NGN", "naira": "NGN", "zar": "ZAR",
       "rand": "ZAR", "cny": "CNY", "yuan": "CNY", "inr": "INR", "rupees": "INR", "aed": "AED", "dirham": "AED",
       "cad": "CAD", "aud": "AUD", "jpy": "JPY", "yen": "JPY", "ssp": "SSP", "cdf": "CDF"}
_RX_CONV = re.compile(r"^(?:convert\s+|how much is\s+|what is\s+|what's\s+)?([$]?\s*[\d.,]+)(?:\s*([a-z$/0-9]+(?:\s+shillings?)?))?"
                      r"\s+(?:to|in|into)\s+([a-z$/0-9]+(?:\s+shillings?)?)\s*\??$", re.I)


def _temp(v, a, b):
    a, b = a[0], b[0]
    c = v if a == "c" else (v - 32) * 5 / 9 if a == "f" else v - 273.15
    return c if b == "c" else c * 9 / 5 + 32 if b == "f" else c + 273.15


def _cur_code(u):
    u = u.lower().strip()
    if u in ("kenyan shillings", "kenya shillings"):
        return "KES"
    if u.endswith("shillings") or u.endswith("shilling"):
        u = u.split()[-1]
    return CUR.get(u) or (u.upper() if re.fullmatch(r"[a-z]{3}", u) and u not in _U else None)


def parse_conversion(text):
    m = _RX_CONV.match(str(text or "").strip())
    if not m:
        return None
    try:
        v = float(m.group(1).replace("$", "").replace(",", "").strip())
    except Exception:
        return None
    a, b = (m.group(2) or "").lower().strip(), m.group(3).lower().strip()
    if m.group(1).strip().startswith("$"):
        a = "usd" if a in ("", "usd") else a
    if not a:
        return None
    return v, a, b


def convert_units(v, a, b):
    ua, ub = _U.get(a), _U.get(b)
    if not ua or not ub or ua[0] != ub[0]:
        return None
    if ua[0] == "temp":
        return _temp(v, a, b)
    return v * ua[1] / ub[1]


class Rates(Store):
    def __init__(self, path):
        super().__init__(path, {"ts": 0, "rates": {}})

    def get(self, max_age=12 * 3600):
        if self.data["rates"] and time.time() - self.data["ts"] < max_age:
            return self.data["rates"], self.data["ts"]
        d = get_json("https://open.er-api.com/v6/latest/USD", timeout=15)
        if isinstance(d, dict) and d.get("result") == "success" and d.get("rates"):
            self.data = {"ts": int(d.get("time_last_update_unix") or time.time()), "rates": d["rates"]}
            self.save()
        return self.data["rates"], self.data["ts"]


def convert(text, rates_store=None):
    """Units or currency. Returns an answer string or None if it isn't a conversion."""
    p = parse_conversion(text)
    if not p:
        return None
    v, a, b = p
    r = convert_units(v, a, b)
    if r is not None:
        return "%s %s = %s %s" % (fmt_num(v), a, fmt_num(round(r, 4)), b)
    ca, cb = _cur_code(a), _cur_code(b)
    if not ca or not cb:
        return None
    rates, ts = (rates_store.get() if rates_store else ({}, 0))
    if ca not in rates or cb not in rates:
        return ("I can't get exchange rates right now. Connect to the internet once and I'll keep them for offline use."
                if not rates else "I don't have a rate for that currency.")
    out = v / rates[ca] * rates[cb]
    when = time.strftime("%d %b %Y", time.localtime(ts)) if ts else ""
    return "%s %s = %s %s (rate from %s; banks and Mobile Money may give a slightly different rate)" % (
        fmt_num(v), ca, fmt_num(round(out, 2)), cb, when)


# ------------------------------------------------------------------ apps: names, packages, store links
APP_MAP = {  # verified Google Play ids (checked 2026-11-27)
    "whatsapp": ["com.whatsapp", "com.whatsapp.w4b"],
    "whatsapp business": ["com.whatsapp.w4b"],
    "fiverr": ["com.fiverr.fiverr"],
    "upwork": ["com.upwork.android.apps.main"],
    "momo": ["mtnft.momo.consumer", "com.consumerug"],
    "mtn momo": ["mtnft.momo.consumer", "com.consumerug"],
    "mobile money": ["mtnft.momo.consumer", "com.consumerug"],
    "airtel": ["com.airtel.africa.selfcare"],
    "airtel money": ["com.airtel.africa.selfcare"],
    "my airtel": ["com.airtel.africa.selfcare"],
    "telegram": ["org.telegram.messenger"],
    "youtube": ["com.google.android.youtube"],
    "tiktok": ["com.zhiliaoapp.musically"],
    "jiji": ["com.olx.ssa.ug"],
    "gmail": ["com.google.android.gm"],
    "chrome": ["com.android.chrome"],
    "facebook": ["com.facebook.katana"],
    "instagram": ["com.instagram.android"],
    "linkedin": ["com.linkedin.android"],
}


def store_links(pkg=None, query=None):
    """Play Store links to try in order: the app's own page, then the web page (or a search)."""
    if pkg:
        return ["market://details?id=" + pkg, "https://play.google.com/store/apps/details?id=" + pkg]
    q = urllib.parse.quote(query or "")
    return ["market://search?q=" + q + "&c=apps", "https://play.google.com/store/search?q=" + q + "&c=apps"]


def _clean_app_name(name):
    n = re.sub(r"[^a-z0-9 ]+", " ", str(name).lower())
    n = re.sub(r"\b(the|app|application|my)\b", " ", n) if norm(name) not in ("my airtel",) else n
    return re.sub(r"\s+", " ", n).strip()


def match_app(name, installed):
    """installed: list of (label, package). Returns the best (label, package) or None."""
    want = _clean_app_name(name)
    if not want or not installed:
        return None
    pkgs = APP_MAP.get(want) or APP_MAP.get(norm(name)) or []
    for p in pkgs:
        for lab, pk in installed:
            if pk == p:
                return (lab, pk)
    best, score = None, 0.0
    for lab, pk in installed:
        l2 = _clean_app_name(lab)
        if not l2:
            continue
        if l2 == want:
            return (lab, pk)
        s = difflib.SequenceMatcher(None, want, l2).ratio()
        if want in l2.split() or (len(want) >= 4 and l2.startswith(want)):
            s = max(s, 0.9)
        if len(want) >= 4 and want in l2:
            s = max(s, 0.82)
        if want in pk.lower().split("."):
            s = max(s, 0.8)
        if s > score:
            best, score = (lab, pk), s
    return best if score >= 0.75 else None


def known_package(name):
    want = _clean_app_name(name)
    p = APP_MAP.get(want) or APP_MAP.get(norm(name))
    if p:
        return p[0]
    close = difflib.get_close_matches(want, list(APP_MAP), n=1, cutoff=0.8)
    return APP_MAP[close[0]][0] if close else None


def safe_filename(url, ctype=""):
    path = urllib.parse.urlparse(url).path
    name = os.path.basename(urllib.parse.unquote(path)) or "download"
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")[:80] or "download"
    if "." not in name:
        ext = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png", "text/plain": ".txt",
               "application/vnd.android.package-archive": ".apk", "audio/mpeg": ".mp3", "video/mp4": ".mp4",
               "application/zip": ".zip"}.get((ctype or "").split(";")[0].strip(), "")
        name += ext
    return name


def download_file(url, folder, progress=None, cancel=None, timeout=30):
    """Streams a file to folder. progress(done, total). Returns (path, '') or (None, plain reason)."""
    if OFFLINE["force"]:
        return None, "No internet connection."
    if not re.match(r"^https?://", url or "", re.I):
        return None, "That doesn't look like a web link."
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        return None, "I can't save to the Download folder."
    part = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx()) as r:
            ctype = r.headers.get("Content-Type", "")
            if "text/html" in ctype.lower():
                return None, "That link opens a web page, not a file. Open it in the browser instead."
            total = int(r.headers.get("Content-Length") or 0)
            cd = r.headers.get("Content-Disposition") or ""
            m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd, re.I)
            name = safe_filename("/" + urllib.parse.unquote(m.group(1)) if m else r.geturl(), ctype)
            path = os.path.join(folder, name)
            base, ext = os.path.splitext(path)
            i = 1
            while os.path.exists(path):
                path = "%s (%d)%s" % (base, i, ext)
                i += 1
            part = path + ".part"
            done = 0
            with open(part, "wb") as f:
                while True:
                    if cancel and cancel():
                        raise InterruptedError()
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        if total and done < total:
            raise IOError("short")
        os.replace(part, path)
        return path, ""
    except InterruptedError:
        reason = "Download stopped."
    except Exception as e:
        log("download: %s" % type(e).__name__)
        reason = "The download didn't finish. Check your internet and try again."
    try:
        if part and os.path.exists(part):
            os.remove(part)
    except Exception:
        pass
    return None, reason


# ------------------------------------------------------------------ reading files
def read_text_file(path, limit=20000):
    """Text from a .txt/.md/.csv/.pdf file. Returns (text, '') or ('', plain reason)."""
    try:
        with open(path, "rb") as f:
            head = f.read(5)
        if head.startswith(b"%PDF"):
            try:
                from pypdf import PdfReader
            except Exception:
                return "", "I can't read PDF files on this phone yet. Try a text file."
            try:
                r = PdfReader(path)
                parts = []
                for pg in r.pages[:40]:
                    parts.append(pg.extract_text() or "")
                    if sum(len(p) for p in parts) > limit:
                        break
                t = "\n".join(parts).strip()
                return (t[:limit], "") if t else ("", "This PDF has no readable text (it may be scanned pictures).")
            except Exception:
                return "", "I couldn't open that PDF."
        with open(path, "rb") as f:
            b = f.read(limit * 4)
        if b.count(b"\x00") > 10:
            return "", "That file isn't text. Pick a .txt or .pdf file."
        t = b.decode("utf-8", "ignore").strip()
        return (t[:limit], "") if t else ("", "That file is empty.")
    except Exception:
        return "", "I couldn't open that file."


# ------------------------------------------------------------------ intent detection (chat tools)
URL_RX = re.compile(r"https?://[^\s<>\"']+", re.I)


def detect_intent(text):
    """Returns (tool, arg). tool in: chat, remember, correction, open_app, apps, store, download, open_url,
    summarize_url, search, wiki, draft, dial, maps, calc, convert, plan, scam, jobs, remind, read_file, teach, help."""
    t = str(text or "").strip()
    low = t.lower().rstrip(" ?.!")
    if not t:
        return ("chat", "")
    if _RX_REMEMBER.match(t):
        return ("remember", _RX_REMEMBER.match(t).group(1))
    c = detect_correction(t)
    if c is not None:
        return ("correction", c)
    m = re.match(r"^\s*teach(?:\s+orax)?\s*[:,-]\s*(.+)$", t, re.I | re.S)
    if m:
        return ("teach", m.group(1).strip())
    if low in ("help", "what can you do", "commands", "how do i use you"):
        return ("help", "")
    if low in ("apps", "my apps", "show apps", "list apps", "show my apps"):
        return ("apps", "")
    if re.match(r"^remind me\b", low):
        return ("remind", t)
    m = re.match(r"^(?:download|save)\s+(?:this\s+|the\s+)?(?:file\s+)?(https?://\S+)", t, re.I)
    if m:
        return ("download", m.group(1))
    m = re.match(r"^(?:download|install|get)\s+(?:the\s+)?(.+?)(?:\s+app)?$", low)
    if m and not URL_RX.search(t):
        return ("store", m.group(1).strip())
    m = re.match(r"^(?:open|launch|start|run|go to)\s+(?:the\s+|my\s+)?(.+?)(?:\s+app)?$", low)
    if m:
        target = m.group(1).strip()
        u = URL_RX.search(t)
        if u:
            return ("open_url", u.group(0))
        if re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?$", target) and not re.match(r"^[a-z]+\.[a-z]+\.[a-z]+\.", target):
            return ("open_url", "https://" + target)
        return ("open_app", target)
    u = URL_RX.search(t)
    if u and (re.search(r"\b(summar|explain|read|what does|tl;?dr|about)\w*", low) or low == u.group(0).lower()):
        return ("summarize_url", u.group(0))
    if re.match(r"^(?:read|summari[sz]e|open)\s+(?:a\s+|my\s+|this\s+)?(?:file|document|pdf)\b", low):
        return ("read_file", "")
    m = re.match(r"^(?:call|dial|phone)\s+(\+?[\d\s-]{3,20})$", low)
    if m:
        return ("dial", re.sub(r"[^\d+]", "", m.group(1)))
    m = re.match(r"^(?:directions to|map of|show (?:me )?on (?:the )?map|where is|find on map|map)\s+(.+)$", low)
    if m and not re.match(r"^(my|the) (money|task|plan)", m.group(1)):
        return ("maps", m.group(1))
    m = re.match(r"^(?:search(?: the web)?(?: for)?|google|look up|lookup|find online|web search)\s+(.+)$", low)
    if m:
        return ("search", m.group(1))
    m = re.match(r"^(?:wiki|wikipedia)\s+(.+)$", low)
    if m:
        return ("wiki", m.group(1))
    m = re.match(r"^(?:draft|write|compose)\s+(?:a\s+|an\s+|me\s+a\s+)?(?:short\s+|polite\s+|formal\s+)?"
                 r"(message|email|e-mail|whatsapp(?: message)?|sms|text|letter|reply|proposal)\b(.*)$", low)
    if m:
        return ("draft", t)
    if re.match(r"^(?:is this (?:a )?scam|scam check|check (?:this|if this is a) scam)", low):
        return ("scam", re.sub(r"^[^:\n]*[:\n]", "", t, count=1).strip() if re.search(r"[:\n]", t) else "")
    m = re.match(r"^(?:find|show|search|get)\s+(?:me\s+)?(?:remote\s+|online\s+)?jobs?(?:\s+(?:for|in|as|on))?\s*(.*)$", low)
    if m:
        return ("jobs", m.group(1).strip())
    m = re.match(r"^(?:plan|make a plan for|help me plan|plan how to|plan to)\s+(.+)$", low)
    if m:
        return ("plan", t.split(None, 1)[1] if len(t.split(None, 1)) > 1 else m.group(1))
    if parse_conversion(t):
        return ("convert", t)
    if re.match(r"^(?:calculate|calc|compute)\s+", low) or (re.fullmatch(r"[\d\s.,+\-*/x()^%=?]+", low or "x")
                                                             and re.search(r"\d\s*[-+*/x^%]\s*\d", low)) \
            or re.match(r"^(?:what is|what's|whats)\s+[\d.,]+\s*(?:%\s*of|[-+*/x^])\s*[\d.,(]", low):
        return ("calc", t)
    return ("chat", t)


DRAFT_KIND = re.compile(r"\b(email|e-mail|whatsapp|sms|text)\b", re.I)


def draft_prompt(text):
    return ("Write the message the user asks for below. Output ONLY the message text the user will send (and for an "
            "email, a first line 'Subject: ...'). Keep it short, polite and natural for Uganda. Request: %s" % text)


def split_subject(draft):
    m = re.match(r"^\s*subject\s*:\s*(.+?)\n+(.*)$", draft or "", re.I | re.S)
    return (m.group(1).strip(), m.group(2).strip()) if m else ("", (draft or "").strip())


# ------------------------------------------------------------------ Teach Orax: safe skills (JSON recipes, no code)
SKILL_TOOLS = {
    "web_search": "search the web; arg = search words",
    "summarize_url": "fetch a web page and summarise it; arg = https link",
    "jobs": "find live remote jobs; arg = search words (may be empty)",
    "open_app": "open an installed app; arg = app name",
    "play_store": "open the Play Store page of an app; arg = app name",
    "draft": "write a message for the user to send; arg = what the message is about",
    "add_task": "save a plan with steps; arg = the goal",
    "remind": "set a reminder; arg = 'in 30 minutes <what>' or 'at 8am <what>'",
    "ask_ai": "ask the AI; arg = prompt; may use {input} (what the user said) and {last} (previous step's result)",
    "calculate": "maths; arg = expression",
    "convert": "currency or unit conversion; arg like '100 usd to ugx'",
}
_SK_KEYS = {"name", "triggers", "time", "steps", "about"}


def skill_prompt(request):
    tools = "\n".join("- %s: %s" % (k, v) for k, v in SKILL_TOOLS.items())
    return ("Turn the user's request into an Orax skill recipe. Use ONLY these tools:\n%s\n\n"
            "Return ONLY JSON, no other text, in this form:\n"
            '{"name": "short name", "about": "one line", "triggers": ["2-4 short phrases the user might say"], '
            '"time": "HH:MM 24h or empty", "steps": [{"tool": "one of the tools", "arg": "text"}]}\n'
            "At most 5 steps. Use {last} to pass the previous step's result to ask_ai. Request: %s" % (tools, request))


def parse_skill_json(text):
    """Finds the JSON object in an AI reply."""
    t = str(text or "")
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except Exception:
        return None


def validate_skill(d):
    """Strict check. Returns (clean_skill, '') or (None, plain reason)."""
    if not isinstance(d, dict):
        return None, "That isn't a skill recipe I can use."
    extra = set(d) - _SK_KEYS - {"id", "created", "last_run"}
    if extra:
        return None, "The recipe has parts I don't allow: %s." % ", ".join(sorted(extra))[:80]
    name = d.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 60:
        return None, "The skill needs a short name."
    trig = d.get("triggers") or []
    if not isinstance(trig, list) or not all(isinstance(x, str) for x in trig) or len(trig) > 8:
        return None, "Trigger words must be a short list of phrases."
    trig = [re.sub(r"\s+", " ", x.strip().lower())[:60] for x in trig if len(x.strip()) >= 3]
    tm = d.get("time") or ""
    if not isinstance(tm, str) or (tm and not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", tm.strip())):
        return None, "The time must look like 08:00."
    steps = d.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= 6:
        return None, "A skill needs 1 to 6 steps."
    clean = []
    for s in steps:
        if not isinstance(s, dict) or set(s) - {"tool", "arg"}:
            return None, "Each step may only have a tool and an arg."
        tool, arg = s.get("tool"), s.get("arg", "")
        if tool not in SKILL_TOOLS:
            return None, "'%s' isn't one of Orax's tools." % str(tool)[:30]
        if not isinstance(arg, str) or len(arg) > 600:
            return None, "Each step's arg must be short text."
        if tool == "summarize_url" and arg and "{" not in arg and not URL_RX.match(arg):
            return None, "summarize_url needs a web link."
        clean.append({"tool": tool, "arg": arg.strip()})
    if not trig and not tm:
        return None, "Give the skill trigger words or a time."
    about = d.get("about") if isinstance(d.get("about"), str) else ""
    return {"id": d.get("id") or new_id(), "name": name.strip(), "about": about.strip()[:160], "triggers": trig,
            "time": tm.strip(), "steps": clean, "created": d.get("created") or int(time.time()),
            "last_run": d.get("last_run") or ""}, ""


class Skills(Store):
    def __init__(self, path):
        super().__init__(path, {"skills": []})

    @property
    def items(self):
        return self.data.setdefault("skills", [])

    def put(self, sk):
        self.data["skills"] = [s for s in self.items if s["id"] != sk["id"]] + [sk]
        self.save()

    def delete(self, sid):
        self.data["skills"] = [s for s in self.items if s["id"] != sid]
        self.save()

    def match(self, text):
        n = " " + norm(text) + " "
        for s in self.items:
            for t in s.get("triggers", []):
                tn = norm(t)
                if tn and (" " + tn + " ") in n:
                    return s
        return None

    def due_now(self, now=None):
        """Skills whose daily time has come today and haven't run today."""
        lt = time.localtime(now or time.time())
        today, hm = time.strftime("%Y-%m-%d", lt), lt.tm_hour * 60 + lt.tm_min
        out = []
        for s in self.items:
            if not s.get("time") or s.get("last_run") == today:
                continue
            h, m = map(int, s["time"].split(":"))
            if hm >= h * 60 + m:
                out.append(s)
        return out

    def mark_ran(self, sid, now=None):
        for s in self.items:
            if s["id"] == sid:
                s["last_run"] = time.strftime("%Y-%m-%d", time.localtime(now or time.time()))
        self.save()


# ------------------------------------------------------------------ morning brief
def morning_brief(jobs, seen_ids, tasks, earnings, now=None):
    new = [j for j in jobs if j.get("id") not in set(seen_ids or [])]
    open_steps = tasks.open_steps() if tasks else []
    lt = time.localtime(now or time.time())
    day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    today_rem = [r for r in (tasks.reminders if tasks else []) if day0 <= r["at"] < day0 + 86400 and not r["fired"]]
    wk = week_totals(earnings.items if earnings else [], now)
    lines = []
    if jobs:
        lines.append("%d new matching job%s since last time." % (len(new), "" if len(new) == 1 else "s")
                     if seen_ids else "%d matching remote jobs to look at." % len(jobs))
    if open_steps:
        lines.append("Next step: %s (%s)." % (open_steps[0][1], open_steps[0][0]))
        if len(open_steps) > 1:
            lines.append("%d steps still open in your plans." % len(open_steps))
    else:
        lines.append("No open steps. Tap Plan it on an opportunity to start one.")
    if today_rem:
        lines.append("%d reminder%s today." % (len(today_rem), "" if len(today_rem) == 1 else "s"))
    lines.append("This week: earned %s, spent %s." % (ugx(wk["earned"]), ugx(wk["spent"])))
    return {"lines": lines, "new_ids": [j["id"] for j in new]}
