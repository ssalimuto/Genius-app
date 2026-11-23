"""Release gate: the build stops here if a promised feature is missing or the app would show
something it must never show (a banned name, a raw traceback). Run in CI before any release is published.

    python tests/release_gate.py            # checks Genius (main.py) and Ssalimuto AI (ssalimuto/main.py)
    python tests/release_gate.py <file>...  # checks only the given app files

Add a line to FEATURES whenever a feature is announced, so it can never silently go missing.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# feature name -> (functions/classes that must exist, words or commands that must appear in the code)
FEATURES = {
    "Typing fix (no repeated letters)": (["_ti_guard_insert"], []),
    "Word suggestion bar (keeps the keyboard open)": (["sb_suggest", "sb_apply", "sb_learn", "sb_clear", "sb_pick_into",
                                                       "sb_hold_focus", "SuggestChip", "SuggestScroll", "sb_add_bar",
                                                       "_sb_chat_typing"],
                                                      ['"suggest on"', '"suggest off"', "SuggestScroll(", "sb_add_bar(root, ti)"]),
    "Chat bubbles": (["ChatBubbles"], []),
    "App Builder": (["hk_build", "hk_builder_panel", "hk_edit"], []),
    "App Maker (installable apps)": (["ho_make_apk"], ["apk_template.bin"]),
    "Creations (CVs, letters, posters)": (["hk_make_doc", "hk_doc_handle", "creations"], []),
    "Answers with numbered sources": (["qa_reply", "qa_render_sources", "qa_gather"], []),
    "Checked maths": (["qa_check_math", "qa_calc_facts"], []),
    "Deep research": (["hk_research", "hk_research_handle", "qa_research"], ['"research']),
    "Read a web page": (["hk_read_link", "hk_link_handle"], []),
    "Find links": (["hk_find_links", "hk_links_handle"], []),
    "Opportunities": (["hk_opportunities"], ['"opportunities"']),
    "Projects": (["hk_proj_handle", "hk_projects"], []),
    "Automatic memory": (["hk_auto_memory"], []),
    "Storage screen": (["storage_box", "storage_dir", "storage_put"], ['"storage"']),
    "Voice input": (["native_listen", "speak_input"], []),
    "Read aloud": (["tts"], []),
    "Live progress card": (["_live_begin", "_live_end"], []),
    "Pictures (setpolli)": ([], ["setpolli"]),
    "What's new with installed version": (["whats_new_text", "version_line"], ["BUILD_NUMBER", "BUILD_COMMIT"]),
    "App updater reads the fixed download": (["online_update", "fetch_live_update"], ["UPDATE_TAG"]),
    "Safe updater (GET download, resume, checks, provider)": (
        ["install_online_update", "update_download", "validate_update_apk", "apk_signer_sha256",
         "installed_cert_sha256", "update_nag_due", "update_say_link", "update_open_link", "UpdateError"],
        ['"updatelink"', "update_open_link()", ".apkprovider", "FLAG_GRANT_READ_URI_PERMISSION",
         "canRequestPackageInstalls", "testzip()", "getPackageArchiveInfo", '"Range"', "UPDATE_STALL_SECONDS = 60"]),
}

UPDATE_CERT = "320faeaf8da56b8a0b98148d680af3fb2443499a00f9be853cdad18bf8b019c4"


def check_updater(path, src, tree):
    """The in-app updater: no DownloadManager, never HEAD, the permanent key, the read-only provider."""
    problems = []
    if "DownloadManager" in re.sub(r"(?m)#.*$", "", src):
        problems.append("updater: DownloadManager is back (it failed on many phones); use update_download")
    if re.search(r"""method\s*=\s*["']HEAD["']""", src):
        problems.append("updater: a HEAD request is used (download servers refuse HEAD); use GET only")
    m = re.search(r'^UPDATE_CERT_SHA256 = "([0-9a-f]+)"', src, re.M)
    if not m or m.group(1) != UPDATE_CERT:
        problems.append("updater: UPDATE_CERT_SHA256 is not the permanent signing key")
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "update_download"), None)
    if fn is not None:
        body = ast.get_source_segment(src, fn) or ""
        if 'method="GET"' not in body:
            problems.append("updater: update_download must ask with GET")
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "install_online_update"), None)
    if fn is not None:
        body = ast.get_source_segment(src, fn) or ""
        for need in ("installed_cert_sha256", "update_download", "validate_update_apk", "update_log_error"):
            if need not in body:
                problems.append(f"updater: install_online_update no longer calls {need}")
        if "getExternalStoragePublicDirectory" in body or "file://" in body:
            problems.append("updater: the download must stay in the app's cache, shared through the provider")
    # The provider and its manifest entry live next to the app file
    here = os.path.dirname(os.path.abspath(path))
    sx = os.path.join(here, "android_extra", "services.xml")
    if os.path.exists(sx):
        x = open(sx, encoding="utf-8").read()
        pm = re.search(r'<provider\s[^>]*android:name="([\w.]+)\.GeniusApkProvider"[^>]*/>', x, re.S)
        if not pm:
            problems.append("updater: GeniusApkProvider is not registered in services.xml")
        else:
            tag = pm.group(0)
            for need in ('android:authorities="{{ args.package }}.apkprovider"', 'android:exported="false"',
                         'android:grantUriPermissions="true"'):
                if need not in tag:
                    problems.append(f"updater: the provider entry needs {need}")
            jp = os.path.join(here, "android_extra", "java", *pm.group(1).split("."), "GeniusApkProvider.java")
            if not os.path.exists(jp):
                problems.append("updater: GeniusApkProvider.java is missing")
            else:
                j = open(jp, encoding="utf-8").read()
                if '"updates"' not in j or ".apk" not in j or "MODE_READ_ONLY" not in j:
                    problems.append("updater: GeniusApkProvider must serve only cache/updates/*.apk, read-only")
    return problems

TRACE_CALLS = {"format_exc", "format_exception", "print_exc", "format_tb"}
SHOW_CALLS = {"show", "say", "tell", "set_text", "toast", "notify", "speak", "tts"}
BANNED = "".join(["H", "a", "r", "k"])   # a name that must never appear in the app
BANNED_RE = re.compile(r"\b" + BANNED + r"\b")
TRACE_TEXT = "Traceback (most recent call last)"


def _names(tree):
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
                elif isinstance(t, ast.Attribute):
                    out.add(t.attr)
    return out


def _call_name(call):
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def check_file(path):
    problems = []
    src = open(path, encoding="utf-8").read()
    try:
        tree = ast.parse(src, path)
    except SyntaxError as e:
        return [f"does not compile: {e}"]
    names = _names(tree)
    for feat, (funcs, words) in FEATURES.items():
        missing = [f for f in funcs if f not in names] + [w for w in words if w not in src]
        if missing:
            problems.append(f"feature missing: {feat} (needs {', '.join(missing)})")
    # Text the person sees: string literals (docstrings and comments are not shown, so they are skipped)
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(node, "body", [])
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant):
                doc_ids.add(id(b[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
            if BANNED_RE.search(node.value):
                problems.append(f"line {node.lineno}: a banned name in app text: {node.value.strip()[:60]!r}")
            if TRACE_TEXT in node.value:
                problems.append(f"line {node.lineno}: raw traceback text in app text")
        if isinstance(node, ast.Call) and _call_name(node) in SHOW_CALLS:
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and _call_name(sub) in TRACE_CALLS:
                    problems.append(f"line {node.lineno}: a raw traceback is shown to the person ({_call_name(node)})")
                    break
    # The phone keyboard's own suggestions stay off (they made letters repeat); the app's bar is used instead
    if 'kw["keyboard_suggestions"] = False' not in src:
        problems.append("keyboard suggestions were turned back on (they make letters repeat): keep keyboard_suggestions=False")
    m_sb = re.search(r"(?s)# =+ 115\.6 Word suggestions.*?# =+ end word suggestions", src)
    if m_sb and re.search(r"hide_keyboard|\.focus = False|focus\", False", m_sb.group(0)):
        problems.append("the word suggestion bar must never close the keyboard")
    problems += check_updater(path, src, tree)
    # What's new must describe the version being shipped
    m = re.search(r'^VERSION = "([^"]+)"', src, re.M)
    c = re.search(r'^CHANGELOG = """([^\n]*)', src, re.M)
    if not m or not c:
        problems.append("VERSION or CHANGELOG missing")
    else:
        base = ".".join(m.group(1).split(".")[:2])
        if base not in c.group(1):
            problems.append(f"What's new is out of date: it starts with {c.group(1)!r} but the app is {m.group(1)}")
    return problems


def main(paths):
    bad = 0
    for p in paths:
        probs = check_file(p)
        label = os.path.relpath(p, ROOT)
        if probs:
            bad += 1
            print(f"GATE FAIL {label}")
            for x in probs:
                print("  - " + x)
        else:
            print(f"GATE PASS {label}: {len(FEATURES)} features present, no banned names, no raw tracebacks")
    return 1 if bad else 0


if __name__ == "__main__":
    files = sys.argv[1:] or [os.path.join(ROOT, "main.py"), os.path.join(ROOT, "ssalimuto", "main.py")]
    sys.exit(main(files))
