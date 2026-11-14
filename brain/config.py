import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_config(path="config.yaml"):
    p = Path(path)
    if not p.exists():
        sys.exit(f"{path} not found. Copy config.example.yaml to config.yaml first.")
    load_dotenv()
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    cfg["backends"] = _usable_backends(cfg.get("backends", []))
    if not cfg["backends"]:
        sys.exit("No usable backend. Check your keys in .env and enabled flags in config.yaml.")
    return cfg


def _usable_backends(items):
    usable = []
    for b in items:
        if b.get("enabled", True) is False:
            continue
        missing = [k for k in ("name", "base_url", "model") if not b.get(k)]
        if missing:
            print(f"[config] skipping backend {b.get('name', '?')}: missing {missing}")
            continue
        env = b.get("api_key_env")
        key = os.environ.get(env) if env else b.get("api_key")
        if not key:
            print(f"[config] skipping '{b['name']}': {env or 'api_key'} is not set")
            continue
        usable.append({**b, "api_key": key})
    return usable