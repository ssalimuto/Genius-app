"""Offline tests for the in-app updater of both apps (a local web server stands in for the download page).

    python tests/test_updater.py          # offline: redirect, resume, HEAD refused, wrong size, bad zip, plain reasons
    python tests/test_updater.py --live   # also one real GET download of each published app, with its signing key checked
"""
import hashlib
import http.server
import io
import os
import re
import shutil
import socketserver
import sys
import tempfile
import threading
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kivy_stub  # noqa: E402
import release_gate  # noqa: E402

ROOT = os.path.dirname(HERE)
FAILS = []
for _k in ("NO_PROXY", "no_proxy"):          # the local test server must be reached directly
    os.environ[_k] = ",".join(x for x in (os.environ.get(_k, ""), "127.0.0.1", "localhost") if x)
LIVE = "--live" in sys.argv
CERT = "320faeaf8da56b8a0b98148d680af3fb2443499a00f9be853cdad18bf8b019c4"
BAD_WORDS = re.compile(r"traceback|exception|errno|error \d|urlopen|http|\bHEAD\b|" + release_gate.BANNED, re.I)


def check(name, ok, extra=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  ({extra})" if extra and not ok else ""))
    if not ok:
        FAILS.append(name)


def fake_apk(cert=b"test-certificate-bytes", dex=b"dex\n035\x00" + b"x" * 4000):
    """A small zip shaped like an APK, with a v2 signing block that carries `cert`."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", b"\x03\x00\x08\x00" + b"m" * 600)
        z.writestr("classes.dex", dex)
        z.writestr("res/raw/pad.bin", os.urandom(20000))
    data = buf.getvalue()
    e = data.rfind(b"PK\x05\x06")
    cd_off = int.from_bytes(data[e + 16:e + 20], "little")

    def lp(b):
        return len(b).to_bytes(4, "little") + b
    signed_data = lp(b"") + lp(lp(cert)) + lp(b"")          # digests, certificates, attributes
    signer = lp(signed_data) + lp(b"") + lp(b"")              # signed data, signatures, public key
    value = lp(lp(signer))
    pair = (len(value) + 4).to_bytes(8, "little") + (0x7109871A).to_bytes(4, "little") + value
    size = len(pair) + 8 + 16
    block = size.to_bytes(8, "little") + pair + size.to_bytes(8, "little") + b"APK Sig Block 42"
    out = bytearray(data[:cd_off] + block + data[cd_off:])
    e2 = out.rfind(b"PK\x05\x06")
    out[e2 + 16:e2 + 20] = (cd_off + len(block)).to_bytes(4, "little")
    return bytes(out), hashlib.sha256(cert).hexdigest()


GOOD, GOOD_CERT = fake_apk()
FILES = {"/app.apk": GOOD, "/junk.apk": os.urandom(len(GOOD)), "/short.apk": GOOD[:-500],
         "/nodex.apk": None}
_b = io.BytesIO()
with zipfile.ZipFile(_b, "w") as _z:
    _z.writestr("AndroidManifest.xml", b"m" * 3000)
FILES["/nodex.apk"] = _b.getvalue()
SEEN = []          # (method, path, range)
STATE = {"dropped": 0}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_HEAD(self):
        SEEN.append(("HEAD", self.path, ""))
        self.send_response(401)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range") or ""
        SEEN.append(("GET", self.path, rng))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/hop")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/hop":
            self.send_response(301)
            self.send_header("Location", "/app.apk")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        path = self.path
        if path == "/drop.apk":
            path = "/app.apk"
            if not rng:                          # first try: send half, then cut the line
                STATE["dropped"] += 1
                body = FILES[path]
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body[:len(body) // 2])
                self.wfile.flush()
                self.close_connection = True
                try:
                    self.connection.shutdown(2)
                except Exception:
                    pass
                return
        if path == "/forbidden.apk":
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = FILES.get(path)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        m = re.match(r"bytes=(\d+)-$", rng)
        if m:
            start = int(m.group(1))
            if start >= len(body):
                self.send_response(416)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            part = body[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(body) - 1}/{len(body)}")
            self.send_header("Content-Length", str(len(part)))
            self.end_headers()
            self.wfile.write(part)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def plain(msg):
    return bool(msg) and len(msg) < 220 and not BAD_WORDS.search(msg)


def run_app(rel, tag):
    m = kivy_stub.load_app(os.path.join(ROOT, rel), "/tmp/updater_test_" + tag)
    srv = Server(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    work = tempfile.mkdtemp(prefix="upd_")
    fast = dict(waits=(0, 0, 0), stall=10)

    def dl(path, size, name):
        dest = os.path.join(work, name)
        try:
            m.update_download(base + path, dest, size, **fast)
            return dest, ""
        except m.UpdateError as e:
            return None, str(e)

    try:
        check(f"{tag}: permanent key in the app", m.UPDATE_CERT_SHA256 == CERT)
        SEEN.clear()
        d, why = dl("/redirect", len(GOOD), "a.apk")
        check(f"{tag}: follows redirects to the file", d is not None and open(d, "rb").read() == GOOD, why)
        check(f"{tag}: redirect path used GET only", SEEN and all(s[0] == "GET" for s in SEEN))

        SEEN.clear()
        d, why = dl("/drop.apk", len(GOOD), "b.apk")
        check(f"{tag}: resumes after a dropped connection", d is not None and open(d, "rb").read() == GOOD, why)
        check(f"{tag}: the resume asked with Range", any(s[2].startswith("bytes=") and s[2] != "bytes=0-" for s in SEEN))
        check(f"{tag}: never asks with HEAD (HEAD answers 401)", not any(s[0] == "HEAD" for s in SEEN))

        d, why = dl("/app.apk", len(GOOD) + 1234, "c.apk")
        check(f"{tag}: wrong size is refused", d is None and "wrong size" in why, why)
        check(f"{tag}: wrong size reason is plain", plain(why), why)
        check(f"{tag}: a refused file leaves nothing behind",
              not os.path.exists(os.path.join(work, "c.apk")) and not os.path.exists(os.path.join(work, "c.apk.part")))

        d, why = dl("/short.apk", len(GOOD), "s.apk")
        check(f"{tag}: a file that keeps coming up short is refused", d is None and plain(why), why)

        d, why = dl("/missing.apk", 1000, "m.apk")
        check(f"{tag}: missing download gives a plain reason", d is None and plain(why) and "isn't on" in why, why)
        d, why = dl("/forbidden.apk", 1000, "f.apk")
        check(f"{tag}: refused download gives a plain reason", d is None and plain(why), why)
        d, why = dl("/app.apk", 0, "n.apk")            # no size known: still downloads
        check(f"{tag}: works without a known size", d is not None, why)
        try:
            m.update_download("http://127.0.0.1:1/x.apk", os.path.join(work, "o.apk"), 100, **fast)
            why = ""
        except m.UpdateError as e:
            why = str(e)
        check(f"{tag}: no connection gives a plain reason", plain(why) and "internet" in why, why)

        # validation
        good = os.path.join(work, "good.apk")
        open(good, "wb").write(GOOD)
        check(f"{tag}: reads the signing key from the APK", m.apk_signer_sha256(good) == GOOD_CERT)
        try:
            ok = m.validate_update_apk(good, len(GOOD), expect_cert=GOOD_CERT)
        except m.UpdateError as e:
            ok = str(e)
        check(f"{tag}: a good app passes the checks", ok is True, ok)

        def reason(path, size=0, cert=GOOD_CERT):
            try:
                m.validate_update_apk(path, size, expect_cert=cert)
                return ""
            except m.UpdateError as e:
                return str(e)
        r = reason(good, cert=CERT)
        check(f"{tag}: another key is refused", "signed" in r and plain(r), r)
        junk = os.path.join(work, "junk.apk")
        open(junk, "wb").write(FILES["/junk.apk"])
        r = reason(junk, len(GOOD))
        check(f"{tag}: a bad zip is refused", "damaged" in r and plain(r), r)
        nodex = os.path.join(work, "nodex.apk")
        open(nodex, "wb").write(FILES["/nodex.apk"])
        r = reason(nodex)
        check(f"{tag}: a zip without the app parts is refused", "complete" in r and plain(r), r)
        broken = bytearray(GOOD)
        i = broken.find(b"classes.dex") + 60
        broken[i:i + 40] = b"\x00" * 40
        bpath = os.path.join(work, "broken.apk")
        open(bpath, "wb").write(bytes(broken))
        r = reason(bpath)
        check(f"{tag}: a damaged file inside the zip is refused (testzip)", r != "" and plain(r), r)
        check(f"{tag}: wrong size is refused before install", "wrong size" in reason(good, len(GOOD) + 1))

        # install path off the phone: plain reason, button, one-line log
        said = []
        logf = os.path.join(os.getcwd(), m.LOG_FILE)
        before = open(logf).read().count("\n") if os.path.exists(logf) else 0
        m.install_online_update("9.9", base + "/app.apk", said.append)
        txt = said[-1] if said else ""
        shown = re.sub(r"\[[^\]]*\]", "", txt)
        check(f"{tag}: a failed update shows a plain reason", plain(shown.split("\n")[0]), txt[:120])
        check(f"{tag}: a failed update offers the browser button", "[ref=updatelink]" in txt)
        lines = open(logf).read().splitlines() if os.path.exists(logf) else []
        new = lines[before:]
        check(f"{tag}: the full error goes on one line in ai_log.txt",
              len(new) == 1 and "UPDATE" in new[0] and "Traceback" in new[0], str(new)[:160])
        rt = m.update_reinstall_text("9.9")
        check(f"{tag}: reinstall message is plain", not BAD_WORDS.search(rt) and len(rt) < 420 and "backup" in rt, rt)
        check(f"{tag}: fixed link points at this app",
              m.update_fixed_link().endswith(f"/releases/download/{m.UPDATE_TAG}/{m.UPDATE_APK}"))
        if os.path.exists(m.UPDATE_NAG_FILE):
            os.remove(m.UPDATE_NAG_FILE)
        check(f"{tag}: reinstall nag at most once a day", m.update_nag_due() is True and m.update_nag_due() is False)

        if LIVE:
            url = m.update_fixed_link()
            dest = os.path.join(work, "live.apk")
            try:
                m.update_download(url, dest, 0, waits=(2, 5, 10))
                why = ""
            except m.UpdateError as e:
                why = str(e)
            check(f"{tag}: real GET download of the published app", why == "" and os.path.getsize(dest) > 1_000_000, why)
            if not why:
                try:
                    m.validate_update_apk(dest, os.path.getsize(dest))
                    r = ""
                except m.UpdateError as e:
                    r = str(e)
                check(f"{tag}: the published app passes the checks with the permanent key", r == "", r)
    finally:
        srv.shutdown()
        shutil.rmtree(work, ignore_errors=True)


def gate_catches():
    src = open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
    import ast
    bad = src.replace('method="GET")', 'method="HEAD")', 1) + "\nx = 'android.app.DownloadManager'\n"
    probs = release_gate.check_updater(os.path.join(ROOT, "main.py"), bad, ast.parse(bad))
    check("gate: catches a HEAD request", any("HEAD" in p for p in probs))
    check("gate: catches DownloadManager", any("DownloadManager" in p for p in probs))
    bad2 = src.replace(CERT, "0" * 64)
    probs = release_gate.check_updater(os.path.join(ROOT, "main.py"), bad2, ast.parse(bad2))
    check("gate: catches a different signing key", any("permanent" in p for p in probs))


if __name__ == "__main__":
    run_app("main.py", "genius")
    run_app(os.path.join("ssalimuto", "main.py"), "ssalimuto")
    gate_catches()
    print(f"\n{'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)
