from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.storage import save_app_state  # noqa: E402


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "usstock" / "local_state.json"
    if not source.exists():
        raise SystemExit(f"State file not found: {source}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    save_app_state(payload)
    print(f"Migrated {source} into SQLite app_state.")


if __name__ == "__main__":
    main()
