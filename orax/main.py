"""Orax start-up guard. Made by Ssali Muto.
Only the standard library is imported here. The real app (orax_app.py) is imported inside try, so any error while
starting is written to Download/Orax/crash.txt (or the app's own storage) and shown on a simple screen instead of
the app closing with nothing on screen."""
import os
import sys
import time
import traceback

CREDIT = "Made by Ssali Muto"
CRASH_TITLE = "Orax couldn't start. Take a photo of this screen and send it to Ssali."


def crash_dirs():
    out = []
    for base in ("/storage/emulated/0/Download", "/sdcard/Download"):
        if os.path.isdir(base):
            out.append(os.path.join(base, "Orax"))
    priv = os.environ.get("ANDROID_PRIVATE") or os.environ.get("ANDROID_APP_PATH")
    if priv:
        out.append(priv)
    out.append(os.path.dirname(os.path.abspath(__file__)))
    out.append(os.getcwd())
    return out


def save_crash(text):
    """Writes the full error to crash.txt. Returns the path written, or ''."""
    body = "Orax crash report %s\n%s\n\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), sys.version.split()[0], text)
    for d in crash_dirs():
        try:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "crash.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
            return p
        except Exception:
            continue
    return ""


def short_error(tb_text):
    lines = [x.strip() for x in str(tb_text).strip().splitlines() if x.strip()]
    last = lines[-1] if lines else "unknown"
    where = ""
    for x in reversed(lines):
        if x.startswith("File "):
            where = x
            break
    return (last[:220] + ("\n" + where[:200] if where else ""))


def show_crash_screen(short, path):
    """Minimal Kivy screen. Built from plain widgets so it still works when the main app can't."""
    try:
        from kivy.app import App
        from kivy.uix.label import Label
        from kivy.core.window import Window

        try:
            Window.clearcolor = (0.04, 0.08, 0.19, 1)
        except Exception:
            pass
        msg = "%s\n\n%s\n\n%s" % (CRASH_TITLE, short, ("Saved to: " + path) if path else "")

        class CrashApp(App):
            title = "Orax"

            def build(self):
                if os.environ.get("ORAX_TEST_AUTOSTOP"):
                    from kivy.clock import Clock
                    Clock.schedule_once(lambda dt: (print("CRASH SCREEN SHOWN"), self.stop()), 1)
                lab = Label(text=msg, color=(1, 0.9, 0.6, 1), halign="center", valign="middle", font_size="16sp",
                            padding=(24, 24))
                lab.bind(size=lambda w, s: setattr(w, "text_size", (s[0] - 48, None)))
                return lab

        CrashApp().run()
    except Exception:
        pass


def start():
    if os.environ.get("ORAX_TEST_CRASH") == "import":
        raise RuntimeError("test crash at import")
    from orax_app import OraxApp
    OraxApp().run()


if __name__ == "__main__":
    try:
        start()
    except SystemExit:
        raise
    except BaseException:
        tb = traceback.format_exc()
        path = save_crash(tb)
        try:
            sys.stderr.write(tb)
        except Exception:
            pass
        show_crash_screen(short_error(tb), path)
