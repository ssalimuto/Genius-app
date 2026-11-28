"""Unit tests for Orax core logic. Run: python tests/test_core.py [--live]
--live also checks the real network calls (jobs, rates, web search, free AI, download)."""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import core  # noqa: E402

TMP = tempfile.mkdtemp(prefix="orax_test_")
core.LOG_FILE = os.path.join(TMP, "log.txt")
FAILS = []
COUNT = [0]


def check(cond, name):
    COUNT[0] += 1
    if not cond:
        FAILS.append(name)
        print("FAIL:", name)


def p(name):
    return os.path.join(TMP, name)


# ---------------------------------------------------------------- scam rules
def test_scam():
    r = core.scam_check("Congratulations! You are hired. Pay a registration fee of 50,000 UGX to our mobile money "
                        "number 0772123456 to start. Guaranteed income. Contact us on WhatsApp only.")
    keys = {k for k, _ in r["flags"]}
    check(r["level"] == "high", "scam: fee offer is high")
    check({"fee", "guarantee", "personal_pay", "chat_only"} <= keys, "scam: flags fee/guarantee/momo/chat %s" % keys)
    check(core.scam_check("Send me the OTP code you just received")["level"] == "high", "scam: OTP is high")
    check(core.scam_check("Double your money in 7 days with bitcoin")["level"] == "high", "scam: doubling")
    check(core.scam_check("Earn 300,000 UGX per day, easy money, act now")["level"] in ("medium", "high"), "scam: too good")
    r = core.scam_check("We are hiring a junior Python developer. Apply on our careers page; interviews by video call.")
    check(r["level"] == "low" and not r["flags"], "scam: normal job is low (%s)" % r["flags"])
    check("does not prove" in r["summary"], "scam: low still warns")
    check(core.scam_check("")["level"] == "low", "scam: empty text")
    check(core.scam_check("Recruit 5 friends and earn referral bonus")["level"] in ("medium", "high"), "scam: pyramid")
    check("Verdict" in core.scam_prompt("x", r), "scam: prompt")


# ---------------------------------------------------------------- matching
def test_matching():
    r = core.match_opportunities("I can build android apps with kivy and python")
    check(r[0]["id"] in ("shop_apps", "fiverr", "upwork", "dev_programs"), "match: dev first (%s)" % r[0]["id"])
    r = core.match_opportunities("writing articles, I am a writer")
    top3 = [o["id"] for o in r[:4]]
    check("writing" in top3 or "upwork" in top3, "match: writing near top %s" % top3)
    check(len(core.match_opportunities("")) == len(core.OPPORTUNITIES), "match: all kept")
    inst = [("WhatsApp", "com.whatsapp"), ("MoMo App", "mtnft.momo.consumer"), ("Calculator", "com.android.calc"),
            ("Chrome", "com.android.chrome"), ("Fiverr", "com.fiverr.fiverr")]
    check(core.match_app("whatsapp", inst) == ("WhatsApp", "com.whatsapp"), "app: whatsapp")
    check(core.match_app("the momo app", inst) == ("MoMo App", "mtnft.momo.consumer"), "app: momo")
    check(core.match_app("calculator", inst)[1] == "com.android.calc", "app: calculator")
    check(core.match_app("calc", inst) is not None, "app: calc prefix")
    check(core.match_app("tiktok", inst) is None, "app: missing app -> None")
    check(core.match_app("", inst) is None, "app: empty")
    check(core.known_package("tiktok") == "com.zhiliaoapp.musically", "app: known tiktok")
    check(core.known_package("zzqqx") is None, "app: unknown")
    links = core.store_links("com.whatsapp")
    check(links[0] == "market://details?id=com.whatsapp" and "play.google.com" in links[1], "app: store links")
    check("market://search" in core.store_links(query="my game")[0], "app: store search")
    jobs = [{"title": "Senior Python Engineer"}, {"title": "Junior Android Developer", "where": "Worldwide"},
            {"title": "Content Writer", "where": "USA only"}, {"title": "Sales Manager"}, {"title": "Python intern"}]
    kept = core.filter_jobs(jobs)
    titles = [j["title"] for j in kept]
    check("Senior Python Engineer" not in titles and "Sales Manager" not in titles, "jobs: senior/sales dropped")
    check(titles[0] in ("Junior Android Developer", "Python intern"), "jobs: open-to-you first")
    check([j for j in kept if j["title"] == "Content Writer"][0]["kind"] == "Writing", "jobs: writing kind")
    check(not [j for j in kept if j["title"] == "Content Writer"][0]["open_to_you"], "jobs: USA only not open")


# ---------------------------------------------------------------- memory + corrections
def test_memory():
    m = core.Memory(p("mem.json"))
    check(m.add("I like Python", "skill") is not None, "mem: add")
    check(m.add("i like python!", "skill") is None, "mem: no duplicate")
    check(m.add("x") is None, "mem: too short")
    m.add("Kampala is the capital", "correction")
    ctx = m.context()
    check(ctx.startswith("Corrections"), "mem: corrections first")
    m2 = core.Memory(p("mem.json"))
    check(len(m2.facts) == 2, "mem: saved and reloaded")
    fid = m2.facts[0]["id"]
    check(m2.delete(fid) and len(m2.facts) == 1, "mem: delete")
    m2.clear()
    check(core.Memory(p("mem.json")).facts == [], "mem: clear")
    for i in range(210):
        m2.add("fact number %d" % i)
    check(len(m2.facts) == 200, "mem: capped at 200")
    f = core.extract_facts("I can build Android apps. I live in Mityana, Uganda. My goal is to earn 100k a month")
    kinds = {k for k, _ in f}
    check({"skill", "location", "goal"} <= kinds, "facts: skill/location/goal %s" % f)
    check(core.extract_facts("remember that my exam is on Friday") == [("fact", "my exam is on Friday")], "facts: remember")
    check(core.extract_facts("hello there") == [], "facts: nothing")
    check(core.detect_correction("That's wrong, it's 42") == "42", "corr: value")
    check(core.detect_correction("No, that is incorrect. The answer is Entebbe") == "Entebbe", "corr: answer is")
    check(core.detect_correction("you're wrong") == "", "corr: only wrong")
    check(core.detect_correction("correction: my name is Ssali") == "my name is Ssali", "corr: prefix")
    check(core.detect_correction("what is wrong with my phone") is None, "corr: normal question")
    s = core.system_prompt(m, "lg")
    check("Luganda" in s and "Ssali Muto" in s, "prompt: luganda + credit")


# ---------------------------------------------------------------- earnings
def test_earnings():
    e = core.Earnings(p("earn.json"))
    now = time.time()
    check(e.add("50,000", "earn", "Fiverr") is not None, "earn: add with comma")
    e.add(20000, "spend", "Data bundles")
    e.add(10000, "earn", "Fiverr")
    e.add(99999, "earn", "Old", ts=now - 30 * 86400)
    check(e.add("abc") is None and e.add(-5) is None and e.add(0) is None, "earn: bad amounts refused")
    wk = core.week_totals(e.items, now)
    check(wk == {"earned": 60000, "spent": 20000, "net": 40000}, "earn: week totals %s" % wk)
    bo = core.by_opportunity(e.items)
    check(bo["Fiverr"]["earned"] == 60000 and bo["Old"]["earned"] == 99999, "earn: by opportunity")
    check(core.ugx(1234567.6) == "UGX 1,234,568" and core.ugx(-500) == "-UGX 500", "earn: ugx format")
    e.delete(e.items[0]["id"])
    check(len(core.Earnings(p("earn.json")).items) == 3, "earn: delete persisted")
    ws = core.week_start(now)
    check(time.localtime(ws).tm_wday == 0 and ws <= now < ws + 7 * 86400, "earn: week starts Monday")


# ---------------------------------------------------------------- tasks + reminders
def test_tasks():
    t = core.Tasks(p("tasks.json"))
    pl = t.add_plan("Fiverr gig", ["Write gig", "Add screenshots", ""])
    check(len(pl["steps"]) == 2, "tasks: empty step dropped")
    check(t.toggle(pl["id"], 0) is True and t.toggle(pl["id"], 0) is False, "tasks: toggle")
    check(t.toggle(pl["id"], 9) is None, "tasks: bad index")
    now = 1_800_000_000
    r = core.parse_reminder("remind me to call Sam in 20 minutes", now)
    check(r == ("call Sam", now + 1200), "remind: in 20 minutes %s" % (r,))
    r = core.parse_reminder("remind me to study at 5pm", now)
    check(r and time.localtime(r[1]).tm_hour == 17 and r[1] > now, "remind: at 5pm")
    r = core.parse_reminder("remind me tomorrow at 8 to pray", now)
    check(r and r[1] - now > 3600 and time.localtime(r[1]).tm_hour == 8, "remind: tomorrow at 8")
    check(core.parse_reminder("remind me at 25:00 x", now) is None, "remind: bad time")
    check(core.parse_reminder("hello", now) is None, "remind: not a reminder")
    t.add_reminder("x", now - 5, pl["id"])
    t.add_reminder("y", now + 500)
    due = t.due(now)
    check(len(due) == 1 and due[0]["text"] == "x" and t.due(now) == [], "remind: due once")
    t.delete_plan(pl["id"])
    check(len(t.reminders) == 1 and not t.plans, "tasks: delete plan + its reminders")
    check(core.parse_steps("1. Do this\n2) Do that\n- bullet item\nnoise") == ["Do this", "Do that", "bullet item"],
          "plan: parse steps")
    check(len(core.offline_plan(core.OPPORTUNITIES[0])) >= 3 and len(core.offline_plan(None)) >= 3, "plan: offline")
    b = core.morning_brief([{"id": "a"}, {"id": "b"}], ["a"], t, core.Earnings(p("earn.json")))
    check(b["new_ids"] == ["b"] and any("This week" in x for x in b["lines"]), "brief: lines")


# ---------------------------------------------------------------- Teach Orax
def test_teach():
    good = {"name": "Morning jobs", "about": "jobs each morning", "triggers": ["morning jobs", "jobs today"],
            "time": "07:30", "steps": [{"tool": "jobs", "arg": "python"}, {"tool": "ask_ai", "arg": "Summarise {last}"}]}
    sk, why = core.validate_skill(good)
    check(sk and not why and sk["time"] == "07:30", "teach: good skill")
    bad_cases = [
        ({"name": "x", "triggers": ["abc"], "steps": [{"tool": "shell", "arg": "rm -rf /"}]}, "tool"),
        ({"name": "x", "triggers": ["abc"], "steps": [{"tool": "jobs", "arg": "", "code": "import os"}]}, "step keys"),
        ({"name": "x", "triggers": ["abc"], "steps": []}, "no steps"),
        ({"name": "x", "triggers": ["abc"], "steps": [{"tool": "jobs"}] * 7}, "too many"),
        ({"name": "x", "triggers": ["abc"], "time": "25:00", "steps": [{"tool": "jobs"}]}, "bad time"),
        ({"name": "", "triggers": ["abc"], "steps": [{"tool": "jobs"}]}, "no name"),
        ({"name": "x", "steps": [{"tool": "jobs"}]}, "no trigger/time"),
        ({"name": "x", "triggers": ["abc"], "steps": [{"tool": "jobs"}], "exec": "1"}, "extra key"),
        ({"name": "x", "triggers": ["abc"], "steps": [{"tool": "summarize_url", "arg": "file:///etc/passwd"}]}, "bad url"),
        ("not a dict", "type"),
    ]
    for d, n in bad_cases:
        s2, why2 = core.validate_skill(d)
        check(s2 is None and why2, "teach: rejects %s" % n)
    check(core.parse_skill_json('Here:\n```json\n{"name": "a", "steps": []}\n```') == {"name": "a", "steps": []},
          "teach: parse fenced json")
    check(core.parse_skill_json("no json") is None, "teach: no json")
    st = core.Skills(p("skills.json"))
    st.put(sk)
    check(st.match("show me Jobs Today please")["id"] == sk["id"], "teach: trigger match")
    check(st.match("nothing here") is None, "teach: no match")
    lt = time.localtime()
    noon = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 12, 0, 0, 0, 0, -1))
    check(len(st.due_now(noon)) == 1, "teach: due after 07:30")
    st.mark_ran(sk["id"], noon)
    check(st.due_now(noon) == [], "teach: not twice a day")
    st.delete(sk["id"])
    check(core.Skills(p("skills.json")).items == [], "teach: delete")
    check("ask_ai" in core.skill_prompt("x"), "teach: prompt lists tools")


# ---------------------------------------------------------------- maths + currency
def test_maths():
    c = core.calculate
    check(c("2+3*4") == "14", "calc: precedence")
    check(c("what is 15% of 200000") == "30,000", "calc: percent of")
    check(c("10 / 4") == "2.5", "calc: division")
    check(c("2^10") == "1,024", "calc: power")
    check(c("sqrt(16)") == "4", "calc: sqrt")
    check(c("1/0") is None, "calc: divide by zero safe")
    check(c("__import__('os')") is None, "calc: no code")
    check(c("9**9**9") is None, "calc: huge power refused")
    check(c("hello") is None, "calc: words")
    check(core.convert("5 km to miles") == "5 km = 3.1069 miles", "conv: km->miles %s" % core.convert("5 km to miles"))
    check(core.convert("100 c to f").endswith("212 f"), "conv: temp")
    check(core.convert("5 kg to km") is None, "conv: wrong dimension")
    r = core.Rates(p("rates.json"))
    r.data = {"ts": int(time.time()), "rates": {"USD": 1.0, "UGX": 3700.0, "KES": 130.0}}
    out = core.convert("$10 to ugx", r)
    check(out.startswith("10 USD = 37,000 UGX"), "cur: usd->ugx %s" % out)
    check(core.convert("1000 ugx to kenyan shillings", r).startswith("1,000 UGX = 35.14 KES"), "cur: kenyan shillings")
    check("don't have a rate" in core.convert("10 usd to xyz", r), "cur: unknown code")
    old = core.OFFLINE["force"]
    core.OFFLINE["force"] = True
    empty = core.Rates(p("rates_empty.json"))
    check("can't get exchange rates" in core.convert("10 usd to ugx", empty), "cur: offline no rates")
    core.OFFLINE["force"] = old
    check(core.parse_conversion("hello") is None, "conv: not conversion")


# ---------------------------------------------------------------- intents + text helpers
def test_intents():
    di = core.detect_intent
    cases = [("open whatsapp", "open_app"), ("open google.com", "open_url"), ("download https://x.org/a.pdf", "download"),
             ("install tiktok", "store"), ("remind me to read in 5 min", "remind"), ("remember I like tea", "remember"),
             ("that's wrong, it's Gulu", "correction"), ("teach orax: every morning show jobs", "teach"),
             ("draft an email to my teacher", "draft"), ("is this a scam: pay fee", "scam"), ("find jobs python", "jobs"),
             ("plan selling phones", "plan"), ("100 usd to ugx", "convert"), ("2+2", "calc"), ("call 0772 123456", "dial"),
             ("search best laptops", "search"), ("hello there", "chat"), ("help", "help"), ("", "chat"),
             ("summarize https://example.com/x", "summarize_url"), ("read a file", "read_file")]
    for text, want in cases:
        got = di(text)[0]
        check(got == want, "intent: %r -> %s (got %s)" % (text, want, got))
    check(di("call 0772 123456")[1] == "0772123456", "intent: dial digits")
    t = core.clean_reply("<think>x</think>Hello!\nI am Chat" "GPT, made by Open" "AI.\n---")
    check("GPT" not in t and "Orax" in t and "think" not in t, "clean: vendor removed: %r" % t)
    check(core.clean_reply("Ask me about Open" "AI's history") == "Ask me about Open" "AI's history", "clean: topic kept")
    check(core.split_subject("Subject: Hi\n\nBody here") == ("Hi", "Body here"), "draft: subject split")
    check(core.split_subject("Just text") == ("", "Just text"), "draft: no subject")
    check(core.check_verdict("MATCHES yes", [])[0] == "unsure", "check: no sources never matches")
    check(core.check_verdict("MATCHES. fine", [{"title": "a"}])[0] == "matches", "check: matches")
    check(core.check_verdict("CONFLICTS no", [{"title": "a"}])[0] == "conflicts", "check: conflicts")
    check(core.check_verdict("", [{"title": "a"}])[0] == "unsure", "check: empty")
    check(core.safe_filename("https://x.org/a%20b.pdf") == "a b.pdf", "file: name")
    check(core.safe_filename("https://x.org/", "application/pdf") == "download.pdf", "file: ext from type")
    f = p("t.txt")
    open(f, "w").write("hello file")
    check(core.read_text_file(f) == ("hello file", ""), "file: read text")
    open(p("bin.dat"), "wb").write(b"\x00" * 100)
    check(core.read_text_file(p("bin.dat"))[1], "file: binary refused")
    check(core.read_text_file(p("missing.txt"))[1], "file: missing plain reason")
    c = core.AnswerCache(p("cache.json"))
    c.put("What is the capital of Uganda?", "Kampala")
    check(c.find("what is the capital of uganda") and c.find("how do I cook") is None, "cache: find")
    c.put("x", core.NO_ANSWER)
    check(c.find("x") is None, "cache: no-answer not stored")
    st = core.Settings(p("settings.json"))
    st.set("lang", "lg")
    check(core.Settings(p("settings.json")).get("lang") == "lg", "settings: persist")
    open(p("broken.json"), "w").write("{not json")
    check(core.Settings(p("broken.json")).get("lang") == "en", "settings: broken file -> defaults")


# ---------------------------------------------------------------- network OFF
def test_offline():
    core.OFFLINE["force"] = True
    try:
        t0 = time.time()
        check(core.http_get("https://example.com") is None, "off: http_get None")
        check(core.online() is False, "off: online False")
        check(core.ask_ai("hi", deadline=5) == "", "off: ask_ai empty")
        check(core.web_search("uganda") == [], "off: web_search empty")
        check(core.fetch_remoteok() == [] and core.fetch_remotive() == [], "off: jobs empty")
        jc = core.JobCache(p("jobs.json"))
        jc.data = {"ts": 0, "jobs": [{"id": "1", "title": "Old job"}]}
        jobs, cached = core.get_jobs(jc, force=True)
        check(cached and jobs[0]["title"] == "Old job", "off: jobs from cache")
        check(core.download_file("https://x.org/a.pdf", p("dl"))[0] is None, "off: download plain reason")
        check(core.fetch_page_text("https://example.com") == "", "off: page text empty")
        check(time.time() - t0 < 15, "off: fast failure")
    finally:
        core.OFFLINE["force"] = False


# ---------------------------------------------------------------- network ON (--live)
def test_live():
    if not core.online():
        print("live: no network here, skipped")
        return
    jobs, cached = core.get_jobs(core.JobCache(p("jobs_live.json")), force=True)
    check(len(jobs) > 0, "live: jobs %d" % len(jobs))
    check(any(j["source"] == "Remote OK" for j in core.fetch_remoteok()), "live: remoteok source label")
    r = core.Rates(p("rates_live.json"))
    out = core.convert("100 usd to ugx", r)
    check(out and "UGX" in out and "rate from" in out, "live: currency %s" % out)
    res = core.web_search("Kampala Uganda")
    check(len(res) > 0, "live: web search %d" % len(res))
    a = core.ask_ai("Reply with the word OK only.", deadline=45)
    check(bool(a), "live: free AI answered")
    path, why = core.download_file("https://open.er-api.com/v6/latest/USD", p("dl"))
    check(path and os.path.getsize(path) > 500, "live: download (%s)" % why)
    check(core.download_file("https://example.com/", p("dl"))[0] is None, "live: html page refused")
    check(len(core.fetch_page_text("https://example.com/")) > 20, "live: page text")


if __name__ == "__main__":
    for fn in (test_scam, test_matching, test_memory, test_earnings, test_tasks, test_teach, test_maths,
               test_intents, test_offline):
        fn()
    if "--live" in sys.argv:
        test_live()
    print("%d checks, %d failed" % (COUNT[0], len(FAILS)))
    sys.exit(1 if FAILS else 0)
