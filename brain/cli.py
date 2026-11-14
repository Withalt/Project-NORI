import statistics

from .config import load_config
from .core import Brain
from .db import DB
from .llm import AllBackendsFailed, LLMRouter
from .memory import Memory

REMEMBER_CMD = "/remember "


def print_stats(db):
    stats = db.llm_stats()
    if not stats:
        print("(no LLM calls logged yet)")
        return
    print(f"{'backend':<12} {'requests':>8} {'fail%':>6} {'empty%':>7} {'p50_first_s':>12}")
    for name, s in stats.items():
        med = f"{statistics.median(s['first']):.2f}" if s["first"] else "-"
        print(f"{name:<12} {s['n']:>8} {100 * s['fail'] / s['n']:>5.0f}% "
              f"{100 * s['empty'] / s['n']:>6.0f}% {med:>12}")


def main():
    cfg = load_config()
    db = DB(cfg["db_path"])
    llm = LLMRouter(cfg["backends"], db)
    brain = Brain(cfg, db, llm, Memory(db))
    print("Type /remember <text> to save a memory, /stats for backend stats, /q to quit.")
    while True:
        text = input("\nBạn: ").strip()
        if text == "/q":
            break
        if text == "/stats":
            print_stats(db)
            continue
        if text.startswith(REMEMBER_CMD):
            brain.mem.add(text[len(REMEMBER_CMD):], kind="manual", importance=2)
            print("(saved)")
            continue
        print("AI: ", end="", flush=True)
        n = 0
        try:
            for piece in brain.reply_stream(text):
                n += 1
                print(piece, end="", flush=True)
        except AllBackendsFailed as e:
            print(f"\n[error] {e}")
            continue
        print(f"   [{llm.last_backend}, {n} chunks]")


if __name__ == "__main__":
    main()