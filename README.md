# Project NORI

A Vietnamese-speaking AI companion with long-term memory. Terminal chat for now; voice, Live2D and a 2D world are planned.

Language: English | [Tiếng Việt](README.vi.md)

**Status:** v0 done (brain core). v1 (daily use and memory tuning) in progress.
This is a personal project. Chat content is sent to whichever LLM backends you configure; only storage (history, memories, logs) is local.

## Quick start

```powershell
git clone https://github.com/[username]/nori_ai.git
cd nori_ai
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy config.example.yaml config.yaml
copy persona.example.md persona.md
copy .env.example .env
```

1. Put API keys in `.env`.
2. In `config.yaml`, fill in `model` for each backend you use. Free-tier model names change often, check the provider's current list.
3. Edit `persona.md` (companion name, user name, tone).
4. Run `python -m brain.cli`.

Python version used in development: [run `python --version` and fill in].

| Command | What it does |
|---|---|
| `/remember <text>` | Save a long-term memory |
| `/stats` | Requests, failure rate and median first-token latency per backend |
| `/q` | Quit |

## How it works

```
user text -> memory search (FTS5) + recent history + persona -> LLM router -> reply
                                                                   |
                                      backends tried in order: gemini -> openrouter -> local
```

- `brain/llm.py`: router. Tries backends in order; falls over on errors, rate limits (429) and empty replies. A backend that hit a rate limit is skipped for 5 minutes. It never fails over mid-stream, because that would duplicate text.
- `brain/memory.py`: memories in SQLite with FTS5 keyword search, accent-insensitive.
- `brain/core.py`: builds the prompt (persona + `KÝ ỨC` section + last `history_turns` turns). The memory section is always present, even when empty, so the model knows it has nothing to draw on.
- `brain/db.py`: schema, chat history, `llm_log` (backend, actual model, latency, error per call).
- `brain/bench.py`: benchmark harness (see below).

Data lives in `companion.db` (path set by `db_path`). Chat turns are saved only when a reply succeeded.

## Configuration

Everything is in `config.yaml` (git-ignored; `config.example.yaml` is the template). Keys go in `.env` and are referenced by name with `api_key_env`.

Add a backend by adding a block. Any OpenAI-compatible endpoint works. Order matters.

```yaml
- name: my_provider
  base_url: "https://api.example.com/v1"
  api_key_env: MY_PROVIDER_API_KEY
  model: "model-name"
  timeout: 30
  max_tokens: 300
```

Backends with a missing key are skipped with a warning; `enabled: false` switches one off. `temperature` and `strip_cjk` (cut the stream at the first Chinese/Japanese character) are optional per-backend settings.

## Decisions and known limits

Read this before changing the design.

- **Gemini is the main backend; local is emergency only.** In the benchmark the local 3B model was far behind the API models and failed on basics (using chat history, arithmetic, mixing in Chinese words). Its latency also rules out voice. Final scores: [fill in from your last `score` run, with the date].
- **`openrouter/free` is a router, not a model.** Each request may be served by a different free model, so quality and latency vary. The `model` column in `llm_log` shows which one answered. Do not benchmark it as if it were one model.
- **Free tiers change without notice.** Treat benchmark scores as a snapshot. The durable part is the harness: add a backend block and re-run.
- **Memory retrieval is keyword-based.** It can miss a relevant memory ("who am I") and can pull in an irrelevant one. Idea if it keeps failing: always load memories saved with `/remember`, use FTS only for the rest, or move to embeddings.
- **Facts only live in history for `history_turns` turns** (default 10). Anything that must last needs `/remember`.
- **Gemini streams in large chunks** (about 3 chunks for a short reply), not word by word. For voice, a sentence splitter must handle a chunk that holds several sentences.
- **Voice latency budget:** first token is about 1 to 2.5 s on Gemini. STT and TTS for Vietnamese still need to be measured on the target machine (8 GB RAM, MX330 2 GB) before committing to v2.

## Benchmark

`brain/bench.py` runs 20 Vietnamese prompts on every configured backend, hides and shuffles backend names, and writes `bench_out.md` for manual scoring (0 to 3). Run it again when the persona, prompt or model changes.

```powershell
python -m brain.bench          # writes bench_out.md and bench_key.json
# fill in "score A: 3" etc. in bench_out.md
python -m brain.bench score    # totals per backend
```

Pass rule I set before looking at results: a local model is accepted only if it reaches 70% of the best API backend's score and has no 0 on P5, P6, P12.

## Roadmap

Plans, not promises.

- [x] v0: brain core, swappable backends, memory, benchmark
- [ ] v1: use it daily for 2 to 3 weeks; note every annoyance; tune memory and persona
- [ ] v2: voice (STT, TTS) and Live2D, only if v1 is actually used daily and STT/TTS latency is acceptable
- [ ] v3: 2D world companion (utility-AI behavior, LLM called sparingly)

Emotion, curiosity and self-model modules from the original design are deferred until v1 proves useful.

## Notes

- Large parts of the code were written with AI assistance (Claude) and then tested and edited by the author.
- Only the code is MIT-licensed. Characters, art, persona and Live2D models are not part of this repo.

## License

MIT. See [LICENSE](LICENSE).
