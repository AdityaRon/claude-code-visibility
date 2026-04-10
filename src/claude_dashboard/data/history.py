import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


def load_history(claude_dir: Path) -> pd.DataFrame:
    """Load history.jsonl into a DataFrame."""
    path = claude_dir / "history.jsonl"
    if not path.exists():
        return pd.DataFrame(columns=["display", "timestamp", "project", "session_id"])

    records = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    records.append({
                        "display": entry.get("display", ""),
                        "timestamp": datetime.fromtimestamp(
                            entry.get("timestamp", 0) / 1000, tz=timezone.utc
                        ),
                        "project": entry.get("project", ""),
                        "session_id": entry.get("sessionId", ""),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass

    if not records:
        return pd.DataFrame(columns=["display", "timestamp", "project", "session_id"])

    return pd.DataFrame(records).sort_values("timestamp", ascending=False).reset_index(drop=True)
