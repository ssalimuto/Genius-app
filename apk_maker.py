# -*- coding: utf-8 -*-
"""apk_maker: turn an App-Builder HTML app into a real installable Android APK.

Works on the phone, offline, with the Python standard library only.

    import apk_maker
    apk_maker.make_apk(template_path, html_text, app_name, out_path, key_dir)

template_path  apk_template.bin, the unsigned WebView shell built in CI from shellapp/
html_text      the app (one HTML file, str or bytes); it becomes assets/app.html
app_name       the name under the icon (up to 30 characters)
out_path       where to write the .apk
key_dir        a private folder to keep the signing key in (made on first use, then reused,
               so a remade app with the same name installs as an update)

What it does: copies the template, swaps assets/app.html, patches the placeholder package
id (org.ssalimuto.mkapp.zzzzzzzzzzzz) and label (30 x '#') in the compiled manifest /
resources.arsc string pools, then signs with APK signature scheme v1 (JAR signing:
MANIFEST.MF, CERT.SF, CERT.RSA) using an RSA-2048 key made on the device. The template
targets SDK 29, so v1 alone installs on Android 5 to 14+.
"""
import base64
import hashlib
import json
import os
import secrets
import struct
import time
import zipfile

__all__ = ["make_apk", "package_for", "PKG_PLACEHOLDER", "LABEL_PLACEHOLDER"]

PKG_PREFIX = "org.ssalimuto.mkapp."
PKG_PLACEHOLDER = PKG_PREFIX + "z" * 12
LABEL_PLACEHOLDER = "#" * 30
KEY_FILE = "apk_maker_key.json"


# --------------------------------------------------------------------------- names

def package_for(app_name):
    """Same-length package id for an app name: org.ssalimuto.mkapp.<12 lowercase letters>.

    Up to 8 letters come from the name, the rest from a hash of the name, so the id is
    stable for the same name (updates work) and different names rarely clash."""
    name = (app_name or "").strip().lower()
    letters = "".join(c for c in name if "a" <= c <= "z")[:8]
    h = hashlib.sha256(name.encode("utf-8")).digest()
    fill = "".join(chr(97 + b % 26) for b in h)
    return PKG_PREFIX + (letters + fill)[:12]


def _clean_label(app_name):
    s = "".join(ch for ch in (app_name or "") if ch.isprintable()).strip()
    return s or "My App"


# ------------------------------------------------------------- binary XML / ARSC patch

def _fit_utf16(s, max_units):
    out = ""
    for ch in s:
        if len((out + ch).encode("utf-16-le")) // 2 > max_units:
            break
        out += ch
    return out


def _fit_utf8(s, max_bytes):
    out = ""
    for ch in s:
        if len((out + ch).encode("utf-8")) > max_bytes:
            break
        out += ch
    return out


def _patch_string_pool(buf, start, mapping):
    """Rewrite strings in one ResStringPool chunk in place. A new string may be shorter
    than the old one (lengths are rewritten, a terminator added; the spare bytes are
    left unused), never longer. Returns how many strings were changed."""
    _t, hsize, csize = struct.unpack_from("<HHI", buf, start)
    count, _styles, flags, s_start, _st = struct.unpack_from("<IIIII", buf, start + 8)
    utf8 = bool(flags & 0x100)
    changed = 0
    for i in range(count):
        (off,) = struct.unpack_from("<I", buf, start + hsize + 4 * i)
        p = start + s_start + off
        if utf8:
            # u16 length (1 or 2 bytes), u8 length (1 or 2 bytes), bytes, 0
            q = p
            n16 = buf[q]; l16 = 1
            if n16 & 0x80:
                n16 = ((n16 & 0x7F) << 8) | buf[q + 1]; l16 = 2
            q += l16
            n8 = buf[q]; l8 = 1
            if n8 & 0x80:
                n8 = ((n8 & 0x7F) << 8) | buf[q + 1]; l8 = 2
            q += l8
            old = bytes(buf[q:q + n8]).decode("utf-8", "replace")
            new = mapping(old)
            if new is None or new == old:
                continue
            new = _fit_utf8(new, n8)
            nb = new.encode("utf-8")
            nu = len(new.encode("utf-16-le")) // 2
            if l16 == 1:
                buf[p] = nu
            else:
                buf[p] = 0x80 | (nu >> 8); buf[p + 1] = nu & 0xFF
            r = p + l16
            if l8 == 1:
                buf[r] = len(nb)
            else:
                buf[r] = 0x80 | (len(nb) >> 8); buf[r + 1] = len(nb) & 0xFF
            buf[q:q + len(nb)] = nb
            buf[q + len(nb)] = 0
            for k in range(q + len(nb) + 1, q + n8 + 1):
                buf[k] = 0
        else:
            # u16 length (1 or 2 units), utf-16 chars, 0x0000
            (n,) = struct.unpack_from("<H", buf, p); lu = 1
            if n & 0x8000:
                (n2,) = struct.unpack_from("<H", buf, p + 2)
                n = ((n & 0x7FFF) << 16) | n2; lu = 2
            q = p + 2 * lu
            old = bytes(buf[q:q + 2 * n]).decode("utf-16-le", "replace")
            new = mapping(old)
            if new is None or new == old:
                continue
            new = _fit_utf16(new, n)
            nb = new.encode("utf-16-le")
            nu = len(nb) // 2
            if lu == 1:
                struct.pack_into("<H", buf, p, nu)
            else:
                struct.pack_into("<HH", buf, p, 0x8000 | (nu >> 16), nu & 0xFFFF)
            buf[q:q + len(nb)] = nb
            for k in range(q + len(nb), q + 2 * n + 2):
                buf[k] = 0
        changed += 1
    return changed


def _walk_chunks(buf, start, end, mapping):
    """Find every string pool in a chunk tree (XML, table, package) and patch it."""
    changed = 0
    pos = start
    while pos + 8 <= end:
        ctype, hsize, csize = struct.unpack_from("<HHI", buf, pos)
        if csize < 8 or pos + csize > end:
            break
        if ctype == 0x0001:  # RES_STRING_POOL_TYPE
            changed += _patch_string_pool(buf, pos, mapping)
        elif ctype in (0x0002, 0x0003, 0x0200):  # TABLE, XML, TABLE_PACKAGE: have children
            changed += _walk_chunks(buf, pos + hsize, pos + csize, mapping)
        pos += csize
    return changed


def _patch_binary(data, mapping, raw_pairs=()):
    buf = bytearray(data)
    _t, hsize, csize = struct.unpack_from("<HHI", buf, 0)
    changed = _walk_chunks(buf, hsize, min(csize, len(buf)), mapping)
    for old, new in raw_pairs:  # same-length UTF-16 swaps (resources.arsc package name)
        assert len(old) == len(new)
        o, n = old.encode("utf-16-le"), new.encode("utf-16-le")
        if o in buf:
            buf = bytearray(bytes(buf).replace(o, n))
            changed += 1
    return bytes(buf), changed


# -------------------------------------------------------------------------------- RSA

_SMALL_PRIMES = [p for p in range(3, 2000) if all(p % d for d in range(2, int(p ** 0.5) + 1))]


def _is_probable_prime(n, rounds=24):
    if n < 2:
        return False
    for p in _SMALL_PRIMES:
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2; s += 1
    for _ in range(rounds):
        a = secrets.randbelow(n - 3) + 2
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _random_prime(bits, e):
    while True:
        c = secrets.randbits(bits) | (3 << (bits - 2)) | 1  # top two bits set: n has 2*bits bits
        if (c - 1) % e == 0:
            continue
        if _is_probable_prime(c, rounds=1) and _is_probable_prime(c):
            return c


def _rsa_generate(bits=2048, e=65537):
    while True:
        p = _random_prime(bits // 2, e)
        q = _random_prime(bits // 2, e)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        phi = (p - 1) * (q - 1)
        d = pow(e, -1, phi)
        return {"n": n, "e": e, "d": d, "p": p, "q": q}


def _rsa_sign_sha256(key, message):
    """RSASSA-PKCS1-v1_5 with SHA-256."""
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420") + hashlib.sha256(message).digest()
    k = (key["n"].bit_length() + 7) // 8
    em = b"\x00\x01" + b"\xff" * (k - len(digest_info) - 3) + b"\x00" + digest_info
    m = int.from_bytes(em, "big")
    p, q, d = key["p"], key["q"], key["d"]
    # CRT for speed
    dp, dq, qinv = d % (p - 1), d % (q - 1), pow(q, -1, p)
    m1, m2 = pow(m, dp, p), pow(m, dq, q)
    h = (qinv * (m1 - m2)) % p
    s = m2 + h * q
    assert pow(s, key["e"], key["n"]) == m
    return s.to_bytes(k, "big")


# -------------------------------------------------------------------------------- DER

def _der_len(n):
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(b)]) + b


def _tlv(tag, content):
    return bytes([tag]) + _der_len(len(content)) + content


def _seq(*items):
    return _tlv(0x30, b"".join(items))


def _set(*items):
    return _tlv(0x31, b"".join(sorted(items)))


def _int(v):
    b = v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big")  # always room for a 0 sign bit
    return _tlv(0x02, b)


def _oid(dotted):
    parts = [int(x) for x in dotted.split(".")]
    out = bytes([40 * parts[0] + parts[1]])
    for v in parts[2:]:
        enc = [v & 0x7F]
        v >>= 7
        while v:
            enc.append(0x80 | (v & 0x7F)); v >>= 7
        out += bytes(reversed(enc))
    return _tlv(0x06, out)


_NULL = b"\x05\x00"
OID_RSA = "1.2.840.113549.1.1.1"
OID_SHA256_RSA = "1.2.840.113549.1.1.11"
OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_DATA = "1.2.840.113549.1.7.1"
OID_SIGNED_DATA = "1.2.840.113549.1.7.2"


def _alg(oid):
    return _seq(_oid(oid), _NULL)


def _name(cn):
    return _seq(
        _set(_seq(_oid("2.5.4.10"), _tlv(0x0C, b"Ssalimuto App Maker"))),
        _set(_seq(_oid("2.5.4.3"), _tlv(0x0C, cn.encode("utf-8")))),
    )


def _make_cert(key, cn="Made on my phone"):
    serial = secrets.randbits(63) | 1
    name = _name(cn)
    t0 = time.gmtime(time.time() - 86400)
    not_before = _tlv(0x17, time.strftime("%y%m%d%H%M%SZ", t0).encode())
    not_after = _tlv(0x18, b"20761231235959Z")
    spki = _seq(_alg(OID_RSA), _tlv(0x03, b"\x00" + _seq(_int(key["n"]), _int(key["e"]))))
    tbs = _seq(
        _tlv(0xA0, _int(2)),          # v3
        _int(serial),
        _alg(OID_SHA256_RSA),
        name,
        _seq(not_before, not_after),
        name,
        spki,
    )
    sig = _rsa_sign_sha256(key, tbs)
    cert = _seq(tbs, _alg(OID_SHA256_RSA), _tlv(0x03, b"\x00" + sig))
    return cert, name, serial


def _pkcs7_signed_data(key, cert, issuer, serial, sf_bytes):
    signature = _rsa_sign_sha256(key, sf_bytes)
    signer_info = _seq(
        _int(1),
        _seq(issuer, _int(serial)),
        _alg(OID_SHA256),
        _alg(OID_RSA),
        _tlv(0x04, signature),
    )
    signed_data = _seq(
        _int(1),
        _set(_alg(OID_SHA256)),
        _seq(_oid(OID_DATA)),        # detached content
        _tlv(0xA0, cert),            # certificates [0] IMPLICIT
        _set(signer_info),
    )
    return _seq(_oid(OID_SIGNED_DATA), _tlv(0xA0, signed_data))


# --------------------------------------------------------------------------- key cache

def _load_or_make_key(key_dir):
    path = os.path.join(key_dir, KEY_FILE) if key_dir else None
    if path and os.path.exists(path):
        try:
            with open(path) as f:
                j = json.load(f)
            key = {k: int(j[k], 16) for k in ("n", "e", "d", "p", "q")}
            cert = base64.b64decode(j["cert"])
            return key, cert, j["issuer"], int(j["serial"], 16)
        except Exception:
            pass  # damaged: make a new one
    key = _rsa_generate()
    cert, issuer, serial = _make_cert(key)
    issuer_b64 = base64.b64encode(issuer).decode()
    if path:
        os.makedirs(key_dir, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({**{k: format(key[k], "x") for k in ("n", "e", "d", "p", "q")},
                       "cert": base64.b64encode(cert).decode(),
                       "issuer": issuer_b64, "serial": format(serial, "x")}, f)
        try:
            os.chmod(tmp, 0o600)
        except Exception:
            pass
        os.replace(tmp, path)
    return key, cert, issuer_b64, serial


# --------------------------------------------------------------------------- v1 signing

def _mf_line(text):
    """Manifest lines are at most 72 bytes; longer ones continue on lines starting with a space."""
    b = text.encode("utf-8")
    out = [b[:72]]
    b = b[72:]
    while b:
        out.append(b" " + b[:71])
        b = b[71:]
    return b"\r\n".join(out) + b"\r\n"


def _b64(b):
    return base64.b64encode(b).decode()


def _build_signature_files(entries, key, cert, issuer, serial):
    main = _mf_line("Manifest-Version: 1.0") + _mf_line("Created-By: 1.0 (Ssalimuto App Maker)") + b"\r\n"
    sections = []
    for name, data in entries:
        sec = (_mf_line("Name: " + name)
               + _mf_line("SHA-256-Digest: " + _b64(hashlib.sha256(data).digest())) + b"\r\n")
        sections.append((name, sec))
    mf = main + b"".join(s for _, s in sections)
    sf = (_mf_line("Signature-Version: 1.0")
          + _mf_line("Created-By: 1.0 (Ssalimuto App Maker)")
          + _mf_line("SHA-256-Digest-Manifest: " + _b64(hashlib.sha256(mf).digest()))
          + _mf_line("SHA-256-Digest-Manifest-Main-Attributes: " + _b64(hashlib.sha256(main).digest()))
          + b"\r\n")
    for name, sec in sections:
        sf += (_mf_line("Name: " + name)
               + _mf_line("SHA-256-Digest: " + _b64(hashlib.sha256(sec).digest())) + b"\r\n")
    rsa = _pkcs7_signed_data(key, cert, base64.b64decode(issuer), serial, sf)
    return mf, sf, rsa


# ------------------------------------------------------------------------------- zip

def _write_aligned(zf, name, data, compress, date_time, align=4):
    zi = zipfile.ZipInfo(name, date_time=date_time)
    zi.compress_type = compress
    zi.external_attr = 0o644 << 16
    zi.create_system = 0
    if compress == zipfile.ZIP_STORED:
        offset = zf.fp.tell()
        base = offset + 30 + len(name.encode("utf-8")) + 6  # header + name + 0xD935 extra head
        pad = (-base) % align
        zi.extra = struct.pack("<HHH", 0xD935, 2 + pad, align) + b"\x00" * pad
    zf.writestr(zi, data)


def make_apk(template_path, html_text, app_name, out_path, key_dir=None, icon_png=None):
    """Build a signed APK from the shell template. Returns out_path.

    icon_png (optional): PNG bytes to use as the launcher icon (any square size)."""
    if isinstance(html_text, str):
        html = html_text.encode("utf-8")
    else:
        html = bytes(html_text)
    label = _clean_label(app_name)
    pkg = package_for(label)
    assert len(pkg) == len(PKG_PLACEHOLDER)

    def mapping(s):
        if PKG_PLACEHOLDER in s:
            return s.replace(PKG_PLACEHOLDER, pkg)
        if s == LABEL_PLACEHOLDER:
            return label
        return None

    with zipfile.ZipFile(template_path) as zin:
        infos = [i for i in zin.infolist()
                 if not i.filename.startswith("META-INF/") and not i.is_dir()]
        items = []
        icon_names = []
        found = {"manifest": 0, "html": False}
        for info in infos:
            data = zin.read(info.filename)
            n = info.filename
            if n == "AndroidManifest.xml":
                data, c = _patch_binary(data, mapping)
                found["manifest"] = c
            elif n == "resources.arsc":
                data, _c = _patch_binary(data, mapping, [(PKG_PLACEHOLDER, pkg)])
            elif n == "assets/app.html":
                data = html
                found["html"] = True
            elif n.startswith("res/mipmap") and n.endswith("/ic_launcher.png"):
                icon_names.append(n)
                if icon_png:
                    data = bytes(icon_png)
            items.append((info, data))
        if found["manifest"] < 2:
            raise ValueError("template manifest placeholders not found (got %d)" % found["manifest"])
        if not found["html"]:
            items.append((None, html))

    entries = []
    for info, data in items:
        name = info.filename if info else "assets/app.html"
        entries.append((name, data))

    key, cert, issuer, serial = _load_or_make_key(key_dir)
    mf, sf, rsa = _build_signature_files(entries, key, cert, issuer, serial)

    now = time.localtime()[:6]
    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w") as zout:
        _write_aligned(zout, "META-INF/MANIFEST.MF", mf, zipfile.ZIP_DEFLATED, now)
        _write_aligned(zout, "META-INF/CERT.SF", sf, zipfile.ZIP_DEFLATED, now)
        _write_aligned(zout, "META-INF/CERT.RSA", rsa, zipfile.ZIP_DEFLATED, now)
        for (info, data), (name, _d) in zip(items, entries):
            dt = info.date_time if info else now
            if name == "resources.arsc" or name.endswith(".png") or name.endswith(".so"):
                comp = zipfile.ZIP_STORED
            elif info is not None:
                comp = info.compress_type
            else:
                comp = zipfile.ZIP_DEFLATED
            _write_aligned(zout, name, data, comp, dt, 4096 if name.endswith(".so") else 4)
    os.replace(tmp, out_path)
    return out_path


if __name__ == "__main__":  # quick manual test: python apk_maker.py template.bin app.html "Name" out.apk keydir
    import sys
    t, h, nm, o = sys.argv[1:5]
    kd = sys.argv[5] if len(sys.argv) > 5 else None
    with open(h, encoding="utf-8") as f:
        src = f.read()
    t0 = time.time()
    print(make_apk(t, src, nm, o, kd), package_for(nm), "%.1fs" % (time.time() - t0))
