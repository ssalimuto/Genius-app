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
}

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
