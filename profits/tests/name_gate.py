"""Name gate: the app, the cloud bot and their workflows credit only "Made by Ssali Muto".
Fails if a banned product or vendor name appears in any text file, or if the credit line is missing."""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# Built from pieces so this file does not contain the names itself.
NAMES = ["".join(p) for p in (["H", "ark"], ["Open", "AI"], ["Anthro", "pic"], ["Cla", "ude"], ["Gem", "ini"],
                              ["Chat", "GPT"], ["G", "PT-?[0-9]"], ["Co", "pilot"], ["Mis", "tral"], ["Lla", "ma"],
                              ["Deep", "Seek"], ["Gr", "ok"], ["Bar", "d"])]
BANNED = re.compile(r"\b(" + "|".join(NAMES) + r")\b", re.I)
TEXT = (".py", ".json", ".txt", ".md", ".spec", ".yml", ".yaml", ".xml", ".cfg")
TARGETS = ["profits", "cloud_bot", ".github/workflows/profits_build.yml",
           ".github/workflows/profits_publish.yml", ".github/workflows/profits_cloud.yml"]

def files():
    for t in TARGETS:
        p = os.path.join(ROOT, t)
        if os.path.isfile(p):
            yield p
        for d, dirs, fs in os.walk(p):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", ".buildozer", "bin", "data")]
            for f in fs:
                if f.endswith(TEXT) and f != "Inter-LICENSE.txt":
                    yield os.path.join(d, f)

problems = []
for f in files():
    for n, line in enumerate(open(f, encoding="utf-8", errors="ignore"), 1):
        m = BANNED.search(line)
        if m:
            problems.append("%s:%d: banned name %r" % (os.path.relpath(f, ROOT), n, m.group(0)))
main = open(os.path.join(ROOT, "profits", "main.py"), encoding="utf-8").read()
if 'CREDIT = "Made by Ssali Muto"' not in main:
    problems.append("profits/main.py: credit line missing")
if problems:
    print("\n".join(problems)); sys.exit("NAME GATE FAIL")
print("NAME GATE PASS")
