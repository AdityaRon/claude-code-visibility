import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import streamlit as st

from claude_dashboard.config import DANGEROUS_BASH_RE, BASH_INEFFICIENCY_RE


@st.cache_data(ttl=300)
def load_transcript_security(claude_dir: str) -> pd.DataFrame:
    """Scan transcript JSONL files for security and efficiency data.

    Extracts per-session:
    - Permission modes used
    - Dangerous Bash commands (rm -rf, force push, etc.)
    - Inefficient Bash commands (ls, find, grep that should use tools)
    - File read frequency (to detect repeated reads)
    """
    projects_dir = Path(claude_dir) / "projects"
    if not projects_dir.exists():
        return _empty_df()

    records = {}

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            sid = jsonl_file.stem
            try:
                record = _scan_transcript(jsonl_file, sid)
                if record:
                    records[sid] = record
            except Exception:
                continue

    if not records:
        return _empty_df()

    return pd.DataFrame(list(records.values()))


def _scan_transcript(jsonl_path: Path, session_id: str) -> dict | None:
    permission_modes = set()
    bash_commands = []
    dangerous_commands = []
    inefficient_bash = []
    file_read_counts: dict[str, int] = defaultdict(int)
    first_timestamp = None

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Track permission mode
            perm = entry.get("permissionMode")
            if perm:
                permission_modes.add(perm)

            if not first_timestamp and entry.get("timestamp"):
                first_timestamp = entry["timestamp"]

            entry_type = entry.get("type", "")
            if entry_type != "assistant":
                continue

            msg = entry.get("message", {})
            for block in msg.get("content", []):
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue

                name = block.get("name", "")
                inp = block.get("input", {})

                if name == "Bash":
                    cmd = inp.get("command", "")
                    if not cmd:
                        continue
                    bash_commands.append(cmd)

                    # Check dangerous patterns
                    for pat in DANGEROUS_BASH_RE:
                        if pat["compiled"].search(cmd):
                            dangerous_commands.append({
                                "command": cmd[:200],
                                "label": pat["label"],
                                "risk": pat["risk"],
                            })
                            break

                    # Check inefficiency patterns
                    for pat in BASH_INEFFICIENCY_RE:
                        if pat["compiled"].search(cmd):
                            inefficient_bash.append({
                                "command": cmd[:200],
                                "label": pat["label"],
                                "tool": pat["tool"],
                            })
                            break

                elif name == "Read":
                    fp = inp.get("file_path", "")
                    if fp:
                        file_read_counts[fp] += 1

    if not first_timestamp and not bash_commands and not permission_modes:
        return None

    repeated_reads = {fp: count for fp, count in file_read_counts.items() if count >= 3}

    return {
        "session_id": session_id,
        "permission_modes": list(permission_modes) if permission_modes else ["unknown"],
        "bash_command_count": len(bash_commands),
        "dangerous_command_count": len(dangerous_commands),
        "dangerous_commands": dangerous_commands,
        "inefficient_bash_count": len(inefficient_bash),
        "inefficient_bash_commands": inefficient_bash,
        "file_read_counts": dict(file_read_counts),
        "repeated_reads": repeated_reads,
        "repeated_read_count": len(repeated_reads),
    }


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "session_id", "permission_modes", "bash_command_count",
        "dangerous_command_count", "dangerous_commands",
        "inefficient_bash_count", "inefficient_bash_commands",
        "file_read_counts", "repeated_reads", "repeated_read_count",
    ])
