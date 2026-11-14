import json
import re
import time


def _fts_query(text):
    words = re.findall(r"\w+", text.lower())
    words = [w for w in words if len(w) > 1][:12]
    return " OR ".join(f'"{w}"' for w in words)


class Memory:
    def __init__(self, db):
        self.db = db

    def add(self, content, kind="fact", importance=1):
        self.db.c.execute(
            "INSERT INTO memories(ts,kind,content,importance) VALUES(?,?,?,?)",
            (time.time(), kind, content, importance))
        self.db.c.commit()

    def search(self, text, k=5):
        q = _fts_query(text)
        if not q:
            return []
        rows = self.db.c.execute(
            """SELECT m.content FROM memories_fts f
               JOIN memories m ON m.id = f.rowid
               WHERE memories_fts MATCH ?
               ORDER BY bm25(memories_fts) LIMIT ?""", (q, k)).fetchall()
        return [r[0] for r in rows]

    def extract(self, llm, recent):
        dialog = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        prompt = ("Từ đoạn hội thoại, rút tối đa 3 sự thật BỀN VỮNG về người dùng "
                  "(sở thích, mục tiêu, thói quen, sự kiện quan trọng). "
                  'Chỉ trả JSON dạng ["...", "..."]. Không có gì đáng nhớ thì trả [].\n\n' + dialog)
        try:
            out = llm.complete([{"role": "user", "content": prompt}])
            items = json.loads(out[out.index("["): out.rindex("]") + 1])
            for it in items:
                if isinstance(it, str) and it.strip():
                    self.add(it.strip(), kind="auto")
        except Exception:
            # Extraction is best-effort and must never break the conversation
            pass