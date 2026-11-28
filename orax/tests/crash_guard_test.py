"""Start-up guard test: a crash during import or build() must write crash.txt and show the crash screen.
python tests/crash_guard_test.py [--mock]   (runs each case in a fresh process)"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)

if len(sys.argv) > 1 and sys.argv[1] == "--child":
    if "--mock" in sys.argv:
        sys.path.insert(0, HERE)
        __import__("mockwin")
    sys.path.insert(0, APP)
    import runpy
    runpy.run_path(os.path.join(APP, "main.py"), run_name="__main__")
    sys.exit(0)

fails = []
for case in ("import", "build"):
    d = tempfile.mkdtemp(prefix="orax_crash_")
    env = dict(os.environ, ORAX_TEST_CRASH=case, ORAX_TEST_AUTOSTOP="1", ANDROID_PRIVATE=d, KIVY_NO_ARGS="1")
    cmd = [sys.executable, __file__, "--child"] + (["--mock"] if "--mock" in sys.argv else [])
    p = subprocess.run(cmd, env=env, cwd=d, capture_output=True, text=True, timeout=90)
    out = p.stdout + p.stderr
    crash = os.path.join(d, "crash.txt")
    ok_file = os.path.exists(crash) and ("test crash" in open(crash).read())
    ok_screen = "CRASH SCREEN SHOWN" in out
    print("%s: crash.txt %s, crash screen %s, exit %s" % (case, ok_file, ok_screen, p.returncode))
    if not (ok_file and ok_screen and p.returncode == 0):
        fails.append(case)
        print(out[-1500:])
if fails:
    sys.exit("CRASH GUARD FAIL: %s" % fails)
print("CRASH GUARD PASS")
