from .config import load_config
from .core import Brain
from .db import DB
from .llm import LLMRouter
from .memory import Memory

REMEMBER_CMD = "/remember "


def main():
    cfg = load_config()
    db = DB(cfg["db_path"])
    llm = LLMRouter(cfg["backends"], db)
    brain = Brain(cfg, db, llm, Memory(db))
    print("Type /remember <text> to save a memory, /q to quit.")
    while True:
        text = input("\nBạn: ").strip()
        if text == "/q":
            break
        if text.startswith(REMEMBER_CMD):
            brain.mem.add(text[len(REMEMBER_CMD):], kind="manual", importance=2)
            print("(saved)")
            continue
        print("AI: ", end="", flush=True)
        for piece in brain.reply_stream(text):
            print(piece, end="", flush=True)
        print(f"   [{llm.last_backend}]")


if __name__ == "__main__":
    main()