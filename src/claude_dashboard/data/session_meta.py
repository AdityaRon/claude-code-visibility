import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def load_session_meta(claude_dir: Path) -> pd.DataFrame:
    """Load all session metadata from session-meta files AND transcript JSONL files.

    Session-meta files only cover a subset of sessions. We supplement by
    scanning transcript JSONL files in projects/ to discover all sessions.
    """
    meta_dir = claude_dir / "usage-data" / "session-meta"
    projects_dir = claude_dir / "projects"

    # Step 1: Load session-meta JSON files (rich metadata)
    meta_records = {}
    if meta_dir.exists():
        for f in meta_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                sid = data.get("session_id", f.stem)
                meta_records[sid] = _parse_session_meta(data)
            except (json.JSONDecodeError, KeyError):
                continue

    # Step 2: Scan transcript JSONL files for sessions not in session-meta
    transcript_records = {}
    if projects_dir.exists():
        for project_dir in projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            # Decode project path: -Users-foo-bar -> /Users/foo/bar
            encoded_name = project_dir.name
            project_path = _decode_project_path(encoded_name)

            for jsonl_file in project_dir.glob("*.jsonl"):
                sid = jsonl_file.stem
                if sid in meta_records:
                    continue  # Already have rich metadata
                try:
                    record = _parse_transcript(jsonl_file, sid, project_path)
                    if record:
                        transcript_records[sid] = record
                except Exception:
                    continue

    # Merge both sources
    all_records = list(meta_records.values()) + list(transcript_records.values())

    if not all_records:
        return _empty_df()

    df = pd.DataFrame(all_records)
    df["start_time"] = pd.to_datetime(df["start_time"], utc=True, errors="coerce")
    df = df.dropna(subset=["start_time"])
    df["date"] = df["start_time"].dt.date
    df["project_name"] = df["project_path"].apply(_extract_project_name)
    df["total_tool_calls"] = df["tool_counts"].apply(
        lambda tc: sum(tc.values()) if tc else 0
    )
    df["total_messages"] = df["user_message_count"] + df["assistant_message_count"]
    return df.sort_values("start_time", ascending=False).reset_index(drop=True)


def _parse_session_meta(data: dict) -> dict:
    """Parse a session-meta JSON file."""
    return {
        "session_id": data.get("session_id", ""),
        "project_path": data.get("project_path", ""),
        "start_time": data.get("start_time", ""),
        "duration_minutes": data.get("duration_minutes", 0),
        "user_message_count": data.get("user_message_count", 0),
        "assistant_message_count": data.get("assistant_message_count", 0),
        "tool_counts": data.get("tool_counts", {}),
        "languages": data.get("languages", {}),
        "git_commits": data.get("git_commits", 0),
        "git_pushes": data.get("git_pushes", 0),
        "input_tokens": data.get("input_tokens", 0),
        "output_tokens": data.get("output_tokens", 0),
        "lines_added": data.get("lines_added", 0),
        "lines_removed": data.get("lines_removed", 0),
        "files_modified": data.get("files_modified", 0),
        "first_prompt": data.get("first_prompt", ""),
        "user_interruptions": data.get("user_interruptions", 0),
        "user_response_times": data.get("user_response_times", []),
        "tool_errors": data.get("tool_errors", 0),
        "tool_error_categories": data.get("tool_error_categories", {}),
        "uses_task_agent": data.get("uses_task_agent", False),
        "uses_mcp": data.get("uses_mcp", False),
        "uses_web_search": data.get("uses_web_search", False),
        "uses_web_fetch": data.get("uses_web_fetch", False),
        "message_hours": data.get("message_hours", []),
        "user_message_timestamps": data.get("user_message_timestamps", []),
    }


def _parse_transcript(jsonl_path: Path, session_id: str, project_path: str) -> dict | None:
    """Extract session metadata by scanning a transcript JSONL file."""
    tool_counts = {}
    user_msg_count = 0
    asst_msg_count = 0
    input_tokens = 0
    output_tokens = 0
    first_timestamp = None
    last_timestamp = None
    first_prompt = ""
    message_hours = []
    cwd = ""
    files_modified = set()
    lines_added = 0
    lines_removed = 0

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")
            timestamp = entry.get("timestamp")

            if entry_type == "user":
                msg = entry.get("message", {})
                content = msg.get("content", "")

                # Count actual user messages (not tool results)
                if isinstance(content, str) and content:
                    user_msg_count += 1
                    if not first_prompt:
                        first_prompt = content[:200]
                    if timestamp:
                        if not first_timestamp:
                            first_timestamp = timestamp
                        last_timestamp = timestamp
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            message_hours.append(dt.hour)
                        except (ValueError, AttributeError):
                            pass

                if not cwd and entry.get("cwd"):
                    cwd = entry["cwd"]

            elif entry_type == "assistant":
                asst_msg_count += 1
                msg = entry.get("message", {})

                # Token usage
                usage = msg.get("usage", {})
                if usage:
                    input_tokens += usage.get("input_tokens", 0)
                    output_tokens += usage.get("output_tokens", 0)

                # Tool counts + code change tracking
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        name = block.get("name", "unknown")
                        tool_counts[name] = tool_counts.get(name, 0) + 1
                        inp = block.get("input", {})

                        if name == "Write":
                            fp = inp.get("file_path", "")
                            if fp:
                                files_modified.add(fp)
                            content_str = inp.get("content", "")
                            if content_str:
                                lines_added += content_str.count("\n") + 1

                        elif name == "Edit":
                            fp = inp.get("file_path", "")
                            if fp:
                                files_modified.add(fp)
                            new = inp.get("new_string", "")
                            old = inp.get("old_string", "")
                            if new:
                                lines_added += new.count("\n") + 1
                            if old:
                                lines_removed += old.count("\n") + 1

                if timestamp:
                    if not first_timestamp:
                        first_timestamp = timestamp
                    last_timestamp = timestamp

    if not first_timestamp:
        return None

    # Calculate duration
    duration_minutes = 0
    try:
        t1 = datetime.fromisoformat(first_timestamp.replace("Z", "+00:00"))
        t2 = datetime.fromisoformat(last_timestamp.replace("Z", "+00:00"))
        duration_minutes = (t2 - t1).total_seconds() / 60
    except (ValueError, AttributeError):
        pass

    return {
        "session_id": session_id,
        "project_path": cwd or project_path,
        "start_time": first_timestamp,
        "duration_minutes": round(duration_minutes, 1),
        "user_message_count": user_msg_count,
        "assistant_message_count": asst_msg_count,
        "tool_counts": tool_counts,
        "languages": {},
        "git_commits": 0,
        "git_pushes": 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "files_modified": len(files_modified),
        "first_prompt": first_prompt,
        "user_interruptions": 0,
        "user_response_times": [],
        "tool_errors": 0,
        "tool_error_categories": {},
        "uses_task_agent": "Agent" in tool_counts,
        "uses_mcp": False,
        "uses_web_search": "WebSearch" in tool_counts,
        "uses_web_fetch": "WebFetch" in tool_counts,
        "message_hours": message_hours,
    }


def _extract_project_name(project_path: str) -> str:
    """Extract a meaningful project name from a project path.

    Handles worktree paths like:
      /Users/.../lacework-security-content/.claude/worktrees/foo -> lacework-security-content
    And regular paths like:
      /Users/.../incident-builder -> incident-builder
    """
    if not project_path:
        return "unknown"
    p = Path(project_path)

    # Worktree: .../<repo>/.claude/worktrees/<name>
    parts = p.parts
    for i, part in enumerate(parts):
        if part == ".claude" and i > 0:
            return parts[i - 1]

    return p.name


def _decode_project_path(encoded: str) -> str:
    """Decode project dir name back to a path.

    The encoding replaces / with -, but this is lossy (repo names also have hyphens).
    This is only used as a fallback when the transcript doesn't have a cwd field.
    """
    # Don't try to be clever - just return the encoded name as-is.
    # The actual project_path will come from the transcript's cwd field.
    return encoded


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "session_id", "project_path", "start_time", "duration_minutes",
            "user_message_count", "assistant_message_count", "tool_counts",
            "languages", "git_commits", "git_pushes", "input_tokens",
            "output_tokens", "lines_added", "lines_removed", "files_modified",
            "first_prompt", "user_interruptions", "user_response_times",
            "tool_errors", "tool_error_categories", "uses_task_agent",
            "uses_mcp", "uses_web_search", "uses_web_fetch", "message_hours",
            "date", "project_name", "total_tool_calls", "total_messages",
            "user_message_timestamps",
        ]
    )
