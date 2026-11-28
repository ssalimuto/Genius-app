"""Orax release gate. Fails the build when:
- a banned product, company or model name appears in any Orax file or workflow (only the two key labels
  "Gr" + "oq key" and "Gem" + "ini key" in Settings are allowed),
- the credit line or the About text is missing or changed,
- raw error text could reach the screen,
- a text box could turn the phone keyboard's suggestions back on, or isn't plain 'text' by default,
- start-up imports something heavy, or the build asks for pillow/plyer,
- the spec, version, archs, min API or manifest queries are wrong,
- the jobs source credit is missing."""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
ROOT = os.path.dirname(APP)
P = []


def fail(msg):
    P.append(msg)


def read(p):
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


# Built from pieces so this file does not contain the names itself.
NAMES = ["".join(x) for x in (["H", "ark"], ["Open", "AI"], ["Anthro", "pic"], ["Cla", "ude"], ["Gem", "ini"],
                              ["Chat", "GPT"], ["G", "PT-?[0-9]"], ["Co", "pilot"], ["Mis", "tral"], ["Lla", "ma"],
                              ["Deep", "Seek"], ["Gr", "oq"], ["Gr", "ok"], ["Bar", "d"], ["Qw", "en"])]
BANNED = re.compile(r"\b(" + "|".join(NAMES) + r")\b", re.I)
ALLOWED_LINES = (re.compile(r'WLabel\(text="(Gr' + 'oq|Gem' + 'ini) key"'),)
TEXT = (".py", ".json", ".txt", ".md", ".spec", ".yml", ".yaml", ".xml", ".cfg")

targets = [APP] + [os.path.join(ROOT, ".github", "workflows", f) for f in ("orax_build.yml", "orax_publish.yml")]
for t in targets:
    files = [t] if os.path.isfile(t) else [os.path.join(d, f) for d, ds, fs in os.walk(t)
                                          for f in fs if f.endswith(TEXT)
                                          and "__pycache__" not in d and ".buildozer" not in d and "bin" not in d.split(os.sep)
                                          and "p4a-src" not in d]
    for f in files:
        if f.endswith("LICENSE.txt"):
            continue
        for n, line in enumerate(read(f).splitlines(), 1):
            m = BANNED.search(line)
            if m and not any(a.search(line) for a in ALLOWED_LINES):
                fail("%s:%d banned name %r" % (os.path.relpath(f, ROOT), n, m.group(0)))

ui = read(os.path.join(APP, "orax_app.py"))
mainpy = read(os.path.join(APP, "main.py"))
corepy = read(os.path.join(APP, "core.py"))

# credit + About
for src, name in ((ui, "orax_app.py"), (mainpy, "main.py")):
    if 'CREDIT = "Made by Ssali Muto"' not in src:
        fail(name + ": credit line missing")
if ('ABOUT_TEXT = ("Orax helps you find and plan work. Earnings depend on your effort; no app can promise income. "\n'
        '              "Made by Ssali Muto")') not in ui:
    fail("orax_app.py: About text changed")
for need in ("can't sign in", "pay for anything", "click through websites", "Reminders work while the app is open"):
    if need not in ui:
        fail("orax_app.py: About must say %r" % need)
if "Remote OK" not in ui or "remoteok.com" not in ui or '"source": "Remote OK"' not in corepy:
    fail("RemoteOK credit missing")
if "Orax couldn't start. Take a photo of this screen and send it to Ssali." not in mainpy or "crash.txt" not in mainpy:
    fail("main.py: start-up guard text or crash.txt missing")

# raw errors never reach the screen
SHOW = re.compile(r"\b(say|toast|popup|bubble|WLabel|Label)\(")
RAWVAR = re.compile(r"(str|repr)\((e|err|exc|inst)\)|format_exc\(|\b(e|err|exc|inst)\.args|%\s*\(?(e|err|exc)\b|"
                    r"\+\s*(e|err|exc)\b|\{(e|err|exc)\}")
for n, line in enumerate(ui.splitlines(), 1):
    if SHOW.search(line) and (RAWVAR.search(line) or re.search(r"Traceback|Exception|Errno", line)):
        fail("orax_app.py:%d may show a raw error: %s" % (n, line.strip()[:100]))
if "ExceptionManager.add_handler(_Guard())" not in ui:
    fail("global ExceptionHandler not registered")

# keyboard: one text box class, suggestions off, plain text by default
if "TextInput(" in ui or ui.count("(TextInput)") != 1 or "class Field(TextInput)" not in ui:
    fail("all text boxes must use Field")
if "keyboard_suggestions=False" not in ui or re.search(r"keyboard_suggestions\s*=\s*True", ui + mainpy):
    fail("keyboard suggestions must stay off")
if 'input_type="number" if number else "text"' not in ui:
    fail("text boxes must default to input_type 'text'")

# light start: only Kivy + standard library at module top
HEAVY = {"PIL", "plyer", "pypdf", "requests", "jnius", "android", "numpy", "kivymd"}
for name, src in (("orax_app.py", ui), ("main.py", mainpy), ("core.py", corepy)):
    tree = ast.parse(src)
    for node in tree.body:
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [(node.module or "").split(".")[0]]
        for m in mods:
            if m in HEAVY or (name == "main.py" and m == "kivy"):
                fail("%s imports %s at start-up" % (name, m))
    if name == "orax_app.py":
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Call):
                fail("orax_app.py runs code at import time (line %d)" % node.lineno)

# build spec + manifest
spec = read(os.path.join(APP, "buildozer.spec"))
for need in ("package.name = orax", "package.domain = org.ssalimuto", "title = Orax", "version = 1.0.0",
             "android.numeric_version = 102500001", "android.minapi = 21", "android.archs = arm64-v8a, armeabi-v7a",
             "android.permissions = INTERNET", "android.extra_manifest_xml = ./android_extra/queries.xml"):
    if need not in spec:
        fail("buildozer.spec missing: " + need)
req = re.search(r"^requirements = (.*)$", spec, re.M)
if not req or re.search(r"pillow|plyer|pypdf|numpy", req.group(1)):
    fail("buildozer.spec requirements must stay light")
q = read(os.path.join(APP, "android_extra", "queries.xml"))
for need in ("android.intent.category.LAUNCHER", "android.intent.action.VIEW", "android.intent.action.SEND",
             "android.intent.action.DIAL", "android.speech.action.RECOGNIZE_SPEECH"):
    if need not in q:
        fail("queries.xml missing " + need)
for f in ("icon.png", "presplash.png"):
    if not os.path.exists(os.path.join(APP, f)):
        fail(f + " missing")
if 'VERSION = "1.0.0"' not in ui:
    fail("orax_app.py VERSION must be 1.0.0")

if P:
    print("\n".join(P))
    sys.exit("RELEASE GATE FAIL (%d)" % len(P))
print("RELEASE GATE PASS")
