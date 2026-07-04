from __future__ import annotations

import json
from pathlib import Path

from mmir.schema import Sample


def load_samples(path: str | Path) -> list[Sample]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Sample file not found: {input_path}")
    if input_path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in input_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else list(payload.values())
    return [sample for row in rows if (sample := Sample.from_row(row)).instance_id]
