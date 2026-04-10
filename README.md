# Claude Code Dashboard

A local-first analytics dashboard for Claude Code users. Understand your usage patterns, token spend, tool efficiency, and productivity — all without sending data anywhere.

The dashboard reads directly from your local `~/.claude/` directory (the same data Claude Code already stores) and surfaces insights through an interactive Streamlit UI.

## What You Get

| Page | What it shows |
|------|--------------|
| **Overview** | KPIs (sessions, tokens, cost, duration), daily usage trends, activity heatmap (hour x day of week), recent sessions table |
| **Tokens & Cost** | Token type breakdown (input/output/cache read/cache create), cache hit rate gauge, daily token trends, cost by model, cost per session distribution |
| **Tool Usage** | Tool call distribution, usage over time, error rates, error categories, feature adoption (Agent/MCP/Web), Read vs Write+Edit scatter, **Bash efficiency analysis** |
| **Security** | **Permission mode tracking**, dangerous command audit (rm -rf, force push, sudo), tool error audit, auto-approval candidates, settings audit |
| **Sessions** | Duration distribution, outcome analysis (achieved/partial/not), helpfulness trend, session type breakdown, friction analysis, full drill-down table |
| **Projects** | Cross-project comparison table, metric comparison charts, activity by project over time, language distribution sunburst |
| **Productivity** | Best coding hours, code output efficiency, goal achievement trend, friction trends, git activity, **18 smart recommendations** including CLAUDE.md optimization tips |

## Quick Start

```bash
pip install claude-code-visibility
claude-dashboard
```

That's it. Opens at `http://localhost:8501`.

### Install from source

```bash
git clone https://github.com/AdityaRon/claude-code-visibility
cd claude-code-visibility
pip install .

# Or editable for development
pip install -e .
```

### Run options

```bash
# Default
claude-dashboard

# Or via Python module
python -m claude_dashboard

# Custom port
claude-dashboard --server.port 8502

# Custom Claude data directory
claude-dashboard --claude-dir /path/to/.claude

# Or via environment variable
CLAUDE_DASHBOARD_DIR=/path/to/.claude claude-dashboard
```

## Requirements

- Python 3.10+
- Claude Code installed and used (data lives in `~/.claude/`)

## When to Use This

- **After your first week of Claude Code** — you'll have enough data for the dashboard to show meaningful patterns.
- **Weekly check-ins** — see how your usage evolves, where tokens are going, which projects consume the most.
- **Cost awareness** — the dashboard estimates API-equivalent costs per model. If you're on a metered plan, this helps you understand spend. If you're on Pro/Max, it shows the value you're getting.
- **Debugging productivity** — high tool error rates? Low cache hit rates? Too many interruptions? The recommendations engine flags these automatically.
- **Team discussions** — share screenshots of your dashboards to compare patterns, identify best practices, and align on workflow improvements.

## How It Helps

1. **Token spend visibility** — see exactly where your tokens go (input vs output vs cache) and which models cost most.
2. **Cache optimization** — cache hit rate directly affects how much context Claude retains between turns. The dashboard tracks this and suggests improvements when it's low.
3. **Tool efficiency** — understand which tools Claude uses most, whether error rates are acceptable, and whether the Read-before-Write ratio is healthy.
4. **Session quality** — if you have session facets enabled, track goal achievement, helpfulness, and friction over time. See if you're getting better at prompting.
5. **Project comparison** — compare token usage, tool patterns, and code output across different repos.
6. **Actionable recommendations** — the Productivity page runs **18 smart checks** including:
   - CLAUDE.md optimization tips (e.g., "Claude re-reads these files often — document them in CLAUDE.md")
   - Bash efficiency (e.g., "329 Bash commands could use Glob/Grep/Read instead")
   - Model selection (e.g., "Sonnet achieves similar outcomes to Opus at lower cost")
   - Plan mode and Agent adoption suggestions
   - Security warnings (dangerous commands, permission mode)
7. **Security audit** — the Security page tracks permission modes, flags dangerous commands (rm -rf, force push, sudo), identifies tools safe for auto-approval, and audits your settings.json.

## Data Privacy & Security

**All data stays on your machine.** The dashboard:
- Reads from `~/.claude/` (read-only — never modifies your data)
- Runs on `localhost` only
- Makes zero network requests (no telemetry, no external APIs)
- Disables Streamlit's usage analytics (`--browser.gatherUsageStats=false`)
- Runs in headless mode (`--server.headless=true`)

### What data does it access?

| Source | Location | Contents |
|--------|----------|----------|
| Session metadata | `~/.claude/usage-data/session-meta/*.json` | Token counts, tool usage, duration, git activity per session |
| Transcripts | `~/.claude/projects/<encoded-path>/*.jsonl` | Per-message token usage, tool calls, timestamps |
| Session facets | `~/.claude/usage-data/facets/*.json` | Goal, outcome, helpfulness, friction (if enabled) |
| Stats cache | `~/.claude/stats-cache.json` | Aggregate daily stats, model usage totals |
| History | `~/.claude/history.jsonl` | Session display names and timestamps |

The dashboard **does not** access your conversation content, API keys, or any credentials. Transcript parsing only extracts metadata (token counts, tool names, timestamps) — not the text of your prompts or Claude's responses.

### Claude Code Permissions Context

Claude Code operates with a configurable permission system. For reference, the tools it can use include:

| Tool | What it does | Permission level |
|------|-------------|-----------------|
| **Read** | Read files | Generally auto-allowed |
| **Write** | Create new files | Requires approval |
| **Edit** | Modify existing files | Requires approval |
| **Bash** | Execute shell commands | Requires approval |
| **Glob** | Find files by pattern | Generally auto-allowed |
| **Grep** | Search file contents | Generally auto-allowed |
| **Agent** | Spawn sub-agents for parallel work | Requires approval |
| **WebSearch** | Search the web | Requires approval |
| **WebFetch** | Fetch web pages | Requires approval |
| **NotebookEdit** | Edit Jupyter notebooks | Requires approval |
| **LSP** | Language server operations | Generally auto-allowed |

You can configure allowed/denied tools in your Claude Code settings (`~/.claude/settings.json`). The dashboard's Tool Usage page shows which tools are being used and at what frequency, helping you audit whether your permission configuration matches your actual usage.

## Local Model / Self-Hosted Support

If you use Claude Code routed through a local model (e.g., via `apiBaseUrl` in your settings), the dashboard works the same way. Claude Code stores session data in `~/.claude/` regardless of which API endpoint is used.

**How local routing works in Claude Code:**

In your `~/.claude/settings.json` or via environment variables:
```json
{
  "apiBaseUrl": "http://localhost:8080"
}
```

Or with the `ANTHROPIC_BASE_URL` environment variable:
```bash
export ANTHROPIC_BASE_URL=http://localhost:8080
```

**Dashboard compatibility:**
- Session metadata, transcripts, and facets are generated by the Claude Code client — they exist regardless of the backend.
- If your local model reports a non-standard model name, the dashboard falls back to Sonnet-equivalent pricing for cost estimates. If the model name contains "opus" or "haiku", it maps to those pricing tiers instead.
- All charts, tool analytics, and session tracking work identically.
- If your local data is stored in a non-standard directory, use `--claude-dir` or `CLAUDE_DASHBOARD_DIR` to point to it.

## Cost Estimates

The dashboard shows **API-equivalent costs** — what you would pay if using the Claude API directly. This is useful for understanding the value you're getting from your subscription.

| Model | Input | Output | Cache Read | Cache Create |
|-------|-------|--------|------------|-------------|
| Claude Opus 4.6 | $15/M | $75/M | $1.50/M | $18.75/M |
| Claude Sonnet 4.6 | $3/M | $15/M | $0.30/M | $3.75/M |
| Claude Haiku 4.5 | $0.80/M | $4/M | $0.08/M | $1/M |

*These are API list prices per million tokens. Actual billing depends on your plan (Pro $20/mo, Max $100-200/mo, or API pay-per-use).*

## Publishing to PyPI

For maintainers — how to publish a new release:

```bash
# 1. Install build tools
pip install build twine

# 2. Build the package
python -m build

# 3. Upload to TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# 4. Test the install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ claude-code-visibility

# 5. Upload to real PyPI
twine upload dist/*
```

Before publishing, bump the version in both `pyproject.toml` and `src/claude_dashboard/__init__.py`.

## License

MIT
