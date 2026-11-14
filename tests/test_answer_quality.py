"""Quick offline tests for both apps (no phone, no internet needed).

    python tests/test_answer_quality.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kivy_stub  # noqa: E402

ROOT = os.path.dirname(HERE)
FAILS = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)


class FakeInput:
    """Enough of a TextInput to test the repeated-letter guard."""

    def __init__(self):
        self.text = ""
        self._kb_last = ("", 0.0, -1)
        self._sel = None

    def cursor_index(self):
        return len(self.text)

    def select_text(self, a, b):
        self._sel = (a, b)

    def delete_selection(self):
        a, b = self._sel
        self.text = self.text[:a] + self.text[b:]


def keyboard_tests(m, tag):
    m._ti_orig_insert = lambda self, s, from_undo=False: setattr(self, "text", self.text + s)
    ti = FakeInput()
    for ch in "hello":
        m._ti_guard_insert(ti, ch)
        time.sleep(0.05)
    check(f"{tag}: normal typing keeps double letters (hello)", ti.text == "hello")
    ti = FakeInput()
    m._ti_guard_insert(ti, "a")
    m._ti_guard_insert(ti, "a")              # same key sent twice at once by the keyboard
    check(f"{tag}: a letter sent twice in a blink is typed once", ti.text == "a")
    ti = FakeInput()
    for ch in "hel":
        m._ti_guard_insert(ti, ch)
        time.sleep(0.05)
    m._ti_guard_insert(ti, "hello")          # keyboard commits the whole word after the letters
    check(f"{tag}: a committed word replaces its letters (no 'helhello')", ti.text == "hello")
    check(f"{tag}: suggestions are switched off for every box", m._KB_SAFE & 524288 and m._KB_SAFE & 144)
    check(f"{tag}: streamed answer typed twice is shown once",
          m.qa_dedupe_text("The answer is 42 and that is final." * 2) == "The answer is 42 and that is final.")
    check(f"{tag}: repeated line removed", m.qa_dedupe_text("Line one here\nLine one here\nTwo") == "Line one here\nTwo")
    check(f"{tag}: different lines kept", m.qa_dedupe_text("a b c\nd e f") == "a b c\nd e f")


def quality_tests(m, tag):
    if not hasattr(m, "qa_route"):
        return
    r = m.qa_route
    check(f"{tag}: news goes to the web", r("What's the latest news in Uganda today?") == "fresh")
    check(f"{tag}: office holder goes to the web", r("Who is the president of the United States?") == "fresh")
    check(f"{tag}: exchange rate goes to the web", r("How much is 100 dollars in UGX today?") == "fresh")
    check(f"{tag}: boda sum is maths, not web",
          r("A boda boda charges 3,000 UGX for the first 2 km and 800 UGX for every extra km. How much is a 9.5 km trip?") == "math")
    check(f"{tag}: code question", r("Write a Python function that checks a phone number") == "code")
    check(f"{tag}: Luganda detected", r("Oli otya! Nnyinza ntya okwekuuma omusujja gw'ensiri?") == "luganda")
    check(f"{tag}: homework", r("Explain photosynthesis for an S2 biology student") == "homework")
    check(f"{tag}: electric current is not news", r("What is electric current?") != "fresh")
    check(f"{tag}: exact percent fact", "15% of 250,000 = 37,500" in m.qa_calc_facts("What is 15% of 250,000 UGX?"))
    check(f"{tag}: wrong sum caught", m.qa_check_math("So 7.5 x 800 = 6,500 UGX") == [("7.5 x 800 = 6,500", "7.5 x 800 = 6,000")])
    check(f"{tag}: right sum passes", m.qa_check_math("7.5 × 800 = 6,000 and 3,000 + 6,000 = 9,000") == [])
    check(f"{tag}: broken code caught", bool(m.qa_check_code("```python\ndef f(:\n  pass\n```")))
    check(f"{tag}: good code passes", not m.qa_check_code("```python\ndef f(x):\n    return x * 2\n```"))
    check(f"{tag}: follow-up query gets the subject",
          "Uganda" in m.qa_rewrite_query("How old was he?", [{"role": "user", "parts": [{"text": "Who was the first president of Uganda?"}]}]))
    check(f"{tag}: hidden rules kept out of memory",
          m.qa_clean_user("[Data saver: answer in under 120 words.] What is rain?") == "What is rain?")
    check(f"{tag}: leaked thinking removed", m.qa_clean_output("<think>hmm</think>Answer") == "Answer")
    md = m.md_to_markup("Use this:\n```python\nprint(a[0])\n```\nDone")
    check(f"{tag}: code block shown in monospace with exact brackets", "RobotoMono" in md and "a&bl;0&br;" in md)
    pdf = os.path.join(HERE, "sample.pdf")
    if os.path.exists(pdf):
        check(f"{tag}: text read from a PDF on the phone", "photosynthesis" in m.qa_pdf_text(pdf).lower())
    brain = m.brain_prompt("core")
    check(f"{tag}: built-in brain works offline", "Answer first" in brain)
    check(f"{tag}: app keeps its own name", m.APP_NAME_FREE in m.qa_persona("chat"))
    check(f"{tag}: no outside brand in the prompt", "hark" not in m.qa_persona("chat").lower())
    if hasattr(m, "cloud_encrypt"):
        key = m.cloud_key("correct horse battery", b"0123456789abcdef")
        blob = m.cloud_encrypt(b"private chat " * 1000, key)
        check(f"{tag}: backup is encrypted", b"private chat" not in blob)
        check(f"{tag}: backup decrypts with the passphrase", m.cloud_decrypt(blob, key) == b"private chat " * 1000)
        bad = m.cloud_key("wrong", b"0123456789abcdef")
        check(f"{tag}: wrong passphrase refused", m.cloud_decrypt(blob, bad) is None)


def main():
    for rel, tag in (("main.py", "Genius"), ("ssalimuto/main.py", "Ssalimuto AI")):
        os.environ["QA_TEST"] = "1"
        m = kivy_stub.load_app(os.path.join(ROOT, rel), "/tmp/qa_test_" + tag.split()[0].lower())
        m.net_online = lambda *a, **k: False
        keyboard_tests(m, tag)
        quality_tests(m, tag)
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
