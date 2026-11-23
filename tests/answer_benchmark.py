"""Answer benchmark: 15 varied questions sent through the app's own free answer path (no keys).

    python tests/answer_benchmark.py before <app file> <out.json>   # the old path (web hand-off, else free backup AI)
    python tests/answer_benchmark.py after  <app file> <out.json>   # the new path (qa_reply)

Free services limit how often one address may ask, so the questions go one by one with a pause between them.
Answers are saved for a person to judge against what the big assistants give.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kivy_stub  # noqa: E402

PROMPTS = [
    {"id": "news", "kind": "current news", "q": "What's the latest news in Uganda today?"},
    {"id": "fx", "kind": "live number", "q": "What is the exchange rate of the US dollar to Uganda shillings now?"},
    {"id": "pop", "kind": "fact with sources", "q": "What is the population of Uganda? Give your sources."},
    {"id": "pct", "kind": "maths", "q": "What is 15% of 250,000 UGX, and then add 18% VAT to that amount?",
     "expect": ["37,500", "44,250"]},
    {"id": "boda", "kind": "step-by-step reasoning",
     "q": "A boda boda charges 3,000 UGX for the first 2 km and 800 UGX for every extra km. How much is a 9.5 km trip? Show the steps.",
     "expect": ["9,000"]},
    {"id": "time", "kind": "reasoning", "q": "A bus leaves Kampala at 2:40 pm and the trip takes 3 hours 55 minutes. What time does it arrive?",
     "expect": ["6:35"]},
    {"id": "code", "kind": "coding",
     "q": "Write a Python function that checks if a Ugandan phone number like 0772123456 or +256772123456 is a valid MTN or Airtel number, and says which network."},
    {"id": "debug", "kind": "coding (debug)", "q": "Why does this Python code crash? nums = [1, 2, 3]\nprint(nums[3])"},
    {"id": "lug", "kind": "Luganda", "q": "Oli otya! Nnyinza ntya okwekuuma omusujja gw'ensiri?"},
    {"id": "nid", "kind": "Ugandan local", "q": "What do I need to get a national ID (Ndaga Muntu) in Uganda?"},
    {"id": "hw", "kind": "homework", "q": "Explain photosynthesis for an S2 biology student, with the word equation."},
    {"id": "link", "kind": "summarise a link", "q": "Summarise https://en.wikipedia.org/wiki/Lake_Victoria"},
    {"id": "img", "kind": "image request", "q": "Draw a boda boda rider on a Kampala street at sunset."},
    {"id": "follow", "kind": "follow-up memory", "q": "Who was the first president of Uganda?",
     "then": "How old was he when he became president?"},
    {"id": "potus", "kind": "freshness trap", "q": "Who is the president of the United States?"},
]


def _plain(t):
    return re.sub(r"\[/?(b|i|u|size|color|ref|font)[^\]]*\]", "", t or "")


def old_reply(m, q, convo):
    """What the app did before 118 for a person with no AI key."""
    u = m._URL_RE.search(q)
    if u:
        rest = (q[:u.start()] + " " + q[u.end():]).strip(" :,-")
        rest = re.sub(r"^(please\s+)?(read|open|check|summari[sz]e|look at|visit|go to)\s*", "", rest, flags=re.I).strip(" :,-?")
        out, err = m.hk_read_link(u.group(0), rest if len(rest) > 6 else None)
        return err or out, "link"
    if m.PIC_ASK.search(q):
        return "(picture request: goes to the picture maker, not judged as text)", "picture"
    if m.HO_FRESH.search(q) and not m.HO_SKIP.search(q):
        ans, links = m.ho_crawl(q)
        if ans:
            if links:
                ans += "\n" + "  ".join(f"[ref=url:{u}]{t[:38]}[/ref]" for t, u in links[:3])
            return ans, "web"
    pre = m.v110_prompt_prefix(q)
    text = (pre + "\n" + q) if pre else q
    r = m.ga_free(text, convo=convo)
    return r or m.NET_AI_MSG, "free AI"


def new_reply(m, q, convo):
    if m.PIC_ASK.search(q) and not m._URL_RE.search(q):
        return "(picture request: goes to the picture maker, not judged as text)", "picture"
    return m.qa_reply(q, convo=convo)


def main():
    mode, path, out = sys.argv[1], sys.argv[2], sys.argv[3]
    only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    m = kivy_stub.load_app(path, "/tmp/qa_bench_" + mode)
    m.LIVE["fn"] = lambda s: print("   live:", s, flush=True)
    results = json.load(open(out)) if os.path.exists(out) else {}
    for p in PROMPTS:
        if only and p["id"] not in only:
            continue
        convo = []
        turns = [p["q"]] + ([p["then"]] if p.get("then") else [])
        rec = {"kind": p["kind"], "turns": []}
        for q in turns:
            t0 = time.time()
            try:
                r, way = (old_reply if mode == "before" else new_reply)(m, q, convo)
            except Exception as e:
                r, way = f"(crashed: {type(e).__name__}: {e})", "crash"
            secs = round(time.time() - t0, 1)
            convo.append({"role": "user", "parts": [{"text": q}]})
            convo.append({"role": "model", "parts": [{"text": r or ""}]})
            rec["turns"].append({"q": q, "a": _plain(r), "way": way, "secs": secs, "ai": m.LAST_AI.get("name")})
            print(f"== {p['id']} [{way}, {secs}s]\nQ: {q}\nA: {_plain(r)[:1500]}\n", flush=True)
            time.sleep(12)
        if p.get("expect"):
            a = " ".join(t["a"] for t in rec["turns"]).replace(" ", "")
            rec["expected_found"] = all(e.replace(" ", "") in a for e in p["expect"])
        results[p["id"]] = rec
        json.dump(results, open(out, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
