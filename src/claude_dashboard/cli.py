import os
import subprocess
import sys
from pathlib import Path


def main():
    app_path = Path(__file__).parent / "app.py"

    # Extract --claude-dir before passing remaining args to Streamlit
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg.startswith("--claude-dir"):
            if "=" in arg:
                claude_dir = arg.split("=", 1)[1]
            elif i + 1 < len(args):
                claude_dir = args[i + 1]
                args.pop(i + 1)
            else:
                print("Error: --claude-dir requires a path argument", file=sys.stderr)
                sys.exit(1)
            args.pop(i)
            os.environ["CLAUDE_DASHBOARD_DIR"] = claude_dir
            break

    sys.exit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(app_path),
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
                *args,
            ]
        )
    )
