import re
import time

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError, RateLimitError

CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


class AllBackendsFailed(Exception):
    pass


class LLMRouter:
    def __init__(self, backends, db, cooldown=300):
        self.backends, self.db, self.cooldown = backends, db, cooldown
        self.clients, self.dead_until = {}, {}
        self.last_backend = None

    def _client(self, b):
        if b["name"] not in self.clients:
            self.clients[b["name"]] = OpenAI(
                base_url=b["base_url"], api_key=b["api_key"], timeout=b.get("timeout", 30))
        return self.clients[b["name"]]

    def stream(self, messages):
        for b in self.backends:
            if self.dead_until.get(b["name"], 0) > time.time():
                continue
            t0, first, got = time.time(), None, False
            # Model name reported by the server; differs from config for routers like openrouter/free
            used = None
            try:
                s = self._client(b).chat.completions.create(
                    model=b["model"], messages=messages, stream=True,
                    max_tokens=b.get("max_tokens", 500),
                    **({"temperature": b["temperature"]} if "temperature" in b else {}))
                for chunk in s:
                    used = used or getattr(chunk, "model", None)
                    if not chunk.choices:
                        continue
                    d = chunk.choices[0].delta.content
                    if d:
                        cut = False
                        # Cut the stream at the first CJK character instead of showing it
                        if b.get("strip_cjk"):
                            m = CJK.search(d)
                            if m:
                                d, cut = d[:m.start()], True
                        if d:
                            if first is None:
                                first = time.time() - t0
                            got = True
                            yield d
                        if cut:
                            break
                if not got:
                    # An empty reply is a failure: log it and fall through to the next backend
                    self.db.log_llm(b["name"], False, error="empty reply",
                                    model=used or b["model"])
                    continue
                self.last_backend = b["name"]
                self.db.log_llm(b["name"], True, first, time.time() - t0,
                                model=used or b["model"])
                return
            except (RateLimitError, APIConnectionError, APITimeoutError, APIError) as e:
                self.db.log_llm(b["name"], False, error=f"{type(e).__name__}: {e}"[:300],
                                model=b["model"])
                if isinstance(e, RateLimitError):
                    # Skip this backend for a while instead of retrying a spent quota
                    self.dead_until[b["name"]] = time.time() + self.cooldown
                # Failing over mid-stream would duplicate text, so stop instead
                if got:
                    return
                continue
        raise AllBackendsFailed("All backends failed, check the llm_log table.")

    def complete(self, messages):
        return "".join(self.stream(messages))