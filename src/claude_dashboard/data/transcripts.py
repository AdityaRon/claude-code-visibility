import json
from pathlib import Path

import pandas as pd
import streamlit as st


@st.cache_data(ttl=600)
def load_transcript_tokens(claude_dir: str, project_path: str, session_id: str) -> pd.DataFrame:
    """Load per-message token usage from a session transcript (lazy)."""
    claude_path = Path(claude_dir)
    encoded = project_path.replace("/", "-")
    transcript_path = claude_path / "projects" / encoded / f"{session_id}.jsonl"

    if not transcript_path.exists():
        return pd.DataFrame(columns=[
            "timestamp", "model", "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens",
        ])

    records = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") != "assistant":
                        continue
                    msg = entry.get("message", {})
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    records.append({
                        "timestamp": entry.get("timestamp", ""),
                        "model": msg.get("model") or entry.get("model") or "unknown",
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        pass

    if not records:
        return pd.DataFrame(columns=[
            "timestamp", "model", "input_tokens", "output_tokens",
            "cache_creation_input_tokens", "cache_read_input_tokens",
        ])

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_all_transcript_tokens(claude_dir: str) -> pd.DataFrame:
    """Load token usage from ALL session transcripts for aggregate cache analysis."""
    claude_path = Path(claude_dir)
    projects_dir = claude_path / "projects"
    if not projects_dir.exists():
        return pd.DataFrame()

    all_records = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            try:
                with open(jsonl_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("type") != "assistant":
                                continue
                            msg = entry.get("message", {})
                            usage = msg.get("usage")
                            if not usage:
                                continue
                            all_records.append({
                                "session_id": session_id,
                                "timestamp": entry.get("timestamp", ""),
                                "model": msg.get("model") or entry.get("model") or "unknown",
                                "input_tokens": usage.get("input_tokens", 0),
                                "output_tokens": usage.get("output_tokens", 0),
                                "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
                                "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
                            })
                        except (json.JSONDecodeError, KeyError):
                            continue
            except OSError:
                continue

    if not all_records:
        return pd.DataFrame()

    df = pd.DataFrame(all_records)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["date"] = df["timestamp"].dt.date
    return df
