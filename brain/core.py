from pathlib import Path


def build_system(persona, mems):
    # Always include the section, even when empty, so the model knows it has no memory to draw on
    body = "\n".join(f"- {m}" for m in mems) if mems else "(trống)"
    return f"{persona}\n\nKÝ ỨC:\n{body}"


class Brain:
    def __init__(self, cfg, db, llm, memory):
        self.cfg, self.db, self.llm, self.mem = cfg, db, llm, memory
        self.persona = Path(cfg["persona_file"]).read_text(encoding="utf-8")
        self.turns = 0

    def _build(self, user_text):
        mems = self.mem.search(user_text, self.cfg["memory_top_k"])
        system = build_system(self.persona, mems)
        history = self.db.recent_messages(self.cfg["history_turns"] * 2)
        return [{"role": "system", "content": system}, *history,
                {"role": "user", "content": user_text}]

    # Generator on purpose: a TTS layer can later split the stream by sentence
    def reply_stream(self, user_text):
        messages = self._build(user_text)
        self.db.add_message("user", user_text)
        full = []
        for piece in self.llm.stream(messages):
            full.append(piece)
            yield piece
        self.db.add_message("assistant", "".join(full))
        self.turns += 1
        n = self.cfg.get("auto_extract_every", 0)
        if n and self.turns % n == 0:
            self.mem.extract(self.llm, self.db.recent_messages(n * 2))