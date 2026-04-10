import os
import re
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_DASHBOARD_DIR", Path.home() / ".claude"))

# API-equivalent pricing per million tokens
MODEL_PRICING = {
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_creation": 18.75,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-haiku-4-5": {
        "input": 0.80,
        "output": 4.0,
        "cache_read": 0.08,
        "cache_creation": 1.0,
    },
    # Older model variants (still appear in transcripts)
    "claude-sonnet-4-5": {
        "input": 3.0,
        "output": 15.0,
        "cache_read": 0.30,
        "cache_creation": 3.75,
    },
    "claude-opus-4-5": {
        "input": 15.0,
        "output": 75.0,
        "cache_read": 1.5,
        "cache_creation": 18.75,
    },
}

# Fallback pricing for unknown models (use Sonnet rates)
DEFAULT_PRICING = MODEL_PRICING["claude-sonnet-4-6"]

# Color palette
COLORS = {
    "primary": "#6366f1",
    "secondary": "#8b5cf6",
    "success": "#22c55e",
    "warning": "#f59e0b",
    "danger": "#ef4444",
    "info": "#3b82f6",
    "muted": "#94a3b8",
}

TOOL_COLORS = {
    "Bash": "#ef4444",
    "Read": "#3b82f6",
    "Write": "#22c55e",
    "Edit": "#10b981",
    "Glob": "#f59e0b",
    "Grep": "#f97316",
    "Agent": "#8b5cf6",
    "LSP": "#ec4899",
    "WebSearch": "#06b6d4",
    "WebFetch": "#14b8a6",
    "NotebookEdit": "#a855f7",
    "TodoWrite": "#6366f1",
    "TaskCreate": "#6366f1",
    "TaskUpdate": "#818cf8",
}


# --- Security & Efficiency Patterns ---

DANGEROUS_BASH_PATTERNS = [
    {"pattern": r"\brm\s+-r", "label": "Recursive delete", "risk": "high"},
    {"pattern": r"\bgit\s+reset\s+--hard\b", "label": "Git hard reset", "risk": "high"},
    {"pattern": r"\bgit\s+push\s+(--force|-f)\b", "label": "Git force push", "risk": "high"},
    {"pattern": r"\bgit\s+checkout\s+\.\s*$", "label": "Discard all changes", "risk": "medium"},
    {"pattern": r"\bgit\s+clean\s+-f", "label": "Git clean force", "risk": "high"},
    {"pattern": r"\bgit\s+branch\s+-D\b", "label": "Force delete branch", "risk": "medium"},
    {"pattern": r"\bsudo\b", "label": "Sudo usage", "risk": "medium"},
    {"pattern": r"\bchmod\s+777\b", "label": "World-writable permissions", "risk": "high"},
    {"pattern": r"\bcurl\b.*\|\s*(ba)?sh", "label": "Pipe to shell", "risk": "high"},
    {"pattern": r"--no-verify\b", "label": "Skip git hooks", "risk": "medium"},
    {"pattern": r"--break-system-packages\b", "label": "Break system packages", "risk": "medium"},
    {"pattern": r"\bkill\s+-9\b", "label": "Force kill process", "risk": "low"},
]

# Pre-compiled for performance
DANGEROUS_BASH_RE = [
    {**p, "compiled": re.compile(p["pattern"])} for p in DANGEROUS_BASH_PATTERNS
]

BASH_INEFFICIENCY_PATTERNS = [
    {"pattern": r"^\s*ls\s", "label": "ls (use Glob)", "tool": "Glob"},
    {"pattern": r"\bfind\s.*-name\b", "label": "find -name (use Glob)", "tool": "Glob"},
    {"pattern": r"^\s*grep\s", "label": "grep (use Grep)", "tool": "Grep"},
    {"pattern": r"^\s*rg\s", "label": "rg (use Grep)", "tool": "Grep"},
    {"pattern": r"^\s*cat\s", "label": "cat (use Read)", "tool": "Read"},
    {"pattern": r"^\s*head\s", "label": "head (use Read)", "tool": "Read"},
    {"pattern": r"^\s*tail\s", "label": "tail (use Read)", "tool": "Read"},
    {"pattern": r"^\s*sed\s", "label": "sed (use Edit)", "tool": "Edit"},
    {"pattern": r"^\s*awk\s", "label": "awk (use Edit)", "tool": "Edit"},
]

BASH_INEFFICIENCY_RE = [
    {**p, "compiled": re.compile(p["pattern"])} for p in BASH_INEFFICIENCY_PATTERNS
]

PERMISSION_MODE_LABELS = {
    "default": "Default (ask permission)",
    "plan": "Plan mode (read-only)",
    "acceptEdits": "Accept Edits (auto-approve)",
}

PERMISSION_MODE_COLORS = {
    "default": "#3b82f6",
    "plan": "#22c55e",
    "acceptEdits": "#f59e0b",
}


def get_model_pricing(model: str) -> dict:
    """Get pricing for a model, matching by prefix.

    Handles standard Claude model names, versioned variants (e.g.
    claude-sonnet-4-6-20250514), and unknown/local model names
    (falls back to Sonnet rates).
    """
    if not model or model == "unknown":
        return DEFAULT_PRICING
    for key, pricing in MODEL_PRICING.items():
        if key in model or model.startswith(key.rsplit("-", 1)[0]):
            return pricing
    # Local/custom models: check for family keywords
    model_lower = model.lower()
    if "opus" in model_lower:
        return MODEL_PRICING["claude-opus-4-6"]
    if "haiku" in model_lower:
        return MODEL_PRICING["claude-haiku-4-5"]
    return DEFAULT_PRICING


def estimate_cost(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    model: str = "claude-sonnet-4-6",
) -> float:
    """Estimate API-equivalent cost in USD."""
    pricing = get_model_pricing(model)
    return (
        input_tokens * pricing["input"] / 1_000_000
        + output_tokens * pricing["output"] / 1_000_000
        + cache_read_tokens * pricing["cache_read"] / 1_000_000
        + cache_creation_tokens * pricing["cache_creation"] / 1_000_000
    )
