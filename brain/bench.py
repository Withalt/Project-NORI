import json
import random
import re
import statistics
import sys
import time
from pathlib import Path

from .config import load_config
from .core import build_system
from .db import DB
from .llm import AllBackendsFailed, LLMRouter

# Free tiers rate-limit hard; local backends skip this pause
DELAY = 4
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

TESTS = [
    # ... (giữ nguyên toàn bộ TESTS như cũ) ...
]


def build_messages(system, t):
    return [{"role": "system", "content": build_system(system, t.get("mem", []))},
            *t.get("history", []),
            {"role": "user", "content": t["user"]}]


def run_one(router, messages):
    t0, first, out = time.time(), None, []
    try:
        for piece in router.stream(messages):
            if first is None:
                first = time.time() - t0
            out.append(piece)
    except AllBackendsFailed:
        return "", None, None
    return "".join(out), first, time.time() - t0


def run():
    cfg = load_config()
    system = Path(cfg["persona_file"]).read_text(encoding="utf-8")
    db = DB(":memory:")
    # One router per backend so nothing falls over to another model
    routers = {b["name"]: (b, LLMRouter([b], db)) for b in cfg["backends"]}
    raw = {t["id"]: {} for t in TESTS}
    stats = {n: {"first": [], "total": [], "cjk": 0, "empty": 0, "words": []} for n in routers}

    for t in TESTS:
        msgs = build_messages(system, t)
        for name, (b, router) in routers.items():
            text, first, total = run_one(router, msgs)
            raw[t["id"]][name] = text
            s = stats[name]
            if not text.strip():
                s["empty"] += 1
            else:
                s["words"].append(len(text.split()))
                s["cjk"] += bool(CJK.search(text))
                s["first"].append(first)
                s["total"].append(total)
            print(f"[{t['id']:>2}/{len(TESTS)}] {name}", flush=True)
            if "localhost" not in b["base_url"]:
                time.sleep(DELAY)

    rng = random.Random(42)
    key, lines = {}, ["# Score each answer 0-3, fill in the numbers after the colon\n"]
    for t in TESTS:
        names = list(routers)
        rng.shuffle(names)
        labels = {chr(65 + i): n for i, n in enumerate(names)}
        key[t["id"]] = labels
        lines.append(f"\n## P{t['id']}\n**Prompt:** {t['user']}\n**Look for:** {t['check']}\n")
        for lab, n in labels.items():
            lines.append(f"\n### {lab}\n{raw[t['id']][n] or '(EMPTY / FAILED)'}\n\nscore {lab}: \n")
    Path("bench_out.md").write_text("\n".join(lines), encoding="utf-8")
    Path("bench_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")

    print("\nBackend      p50_first  p50_total  avg_words  cjk_leaks  empty")
    for n, s in stats.items():
        med = lambda v: f"{statistics.median(v):.2f}" if v else "  -  "
        avg = f"{statistics.mean(s['words']):.0f}" if s["words"] else "-"
        print(f"{n:<12} {med(s['first']):>9} {med(s['total']):>10} {avg:>10} "
              f"{s['cjk']:>10} {s['empty']:>6}")
    print("\nNow open bench_out.md, fill the scores, then run: python -m brain.bench score")


def score():
    key = json.loads(Path("bench_key.json").read_text(encoding="utf-8"))
    text = Path("bench_out.md").read_text(encoding="utf-8")
    totals, counts, zeros = {}, {}, {}
    for pid, labels in key.items():
        sec = re.search(rf"## P{pid}\n(.*?)(?=\n## P|\Z)", text, re.S).group(1)
        for lab, name in labels.items():
            m = re.search(rf"score {lab}:\s*([0-3])", sec)
            if not m:
                continue
            v = int(m.group(1))
            totals[name] = totals.get(name, 0) + v
            counts[name] = counts.get(name, 0) + 1
            if v == 0:
                zeros.setdefault(name, []).append(pid)
    print("Backend      score   max   pct   zeros(prompt ids)")
    for n in sorted(totals, key=totals.get, reverse=True):
        mx = counts[n] * 3
        print(f"{n:<12} {totals[n]:>5} {mx:>5} {100*totals[n]/mx:>4.0f}%   {zeros.get(n, [])}")


if __name__ == "__main__":
    score() if len(sys.argv) > 1 and sys.argv[1] == "score" else run()