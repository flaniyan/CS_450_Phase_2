from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Utility entrypoint for installing dependencies, running tests, and scoring URL files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help="Install the project in editable mode using pip.")
    subparsers.add_parser("test", help="Run the pytest suite with coverage enabled.")

    score_parser = subparsers.add_parser(
        "score",
        help="Score repositories listed in the provided URL file and emit NDJSON to stdout.",
    )
    score_parser.add_argument(
        "url_file",
        nargs="?",
        default="urls.txt",
        help="Path to a file containing one URL per line (defaults to urls.txt).",
    )

    return parser.parse_args(argv)


def do_install() -> int:
    cmd = [sys.executable, "-m", "pip", "install", "-e", str(ROOT)]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        return exc.returncode
    return 0


def do_test() -> int:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "--maxfail=1",
        "--disable-warnings",
        "--cov=acmecli",
        "--cov-report=term-missing",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    collected = re.search(r"collected\s+(\d+)", output)
    passed = re.search(r"(\d+)\s+passed", output)
    coverage = re.search(r"TOTAL\s+.*?(\d+)%", output)

    total = int(collected.group(1)) if collected else 0
    success = int(passed.group(1)) if passed else 0
    cov_percent = int(coverage.group(1)) if coverage else 0

    print(f"{success}/{total} test cases passed. {cov_percent}% line coverage achieved.")
    if proc.returncode != 0 and output:
        print(output)
    return proc.returncode


def do_score(url_file: str) -> int:
    url_path = Path(url_file)
    if not url_path.exists():
        print(f"URL file not found: {url_file}", file=sys.stderr)
        return 1

    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    from acmecli.cli import main as cli_main  # imported lazily to ensure src is on sys.path

    return cli_main(["run", str(url_path)])


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    if not raw_args:
        return do_score("urls.txt")

    cmd = raw_args[0]
    if cmd in {"install", "test", "score"}:
        args = parse_args(raw_args)
        if args.command == "install":
            return do_install()
        if args.command == "test":
            return do_test()
        if args.command == "score":
            return do_score(args.url_file)
    else:
        if len(raw_args) != 1:
            print("Usage: run.py [install|test|score <URL_FILE>] or run.py <URL_FILE>", file=sys.stderr)
            return 1
        return do_score(cmd)

    raise RuntimeError("Unhandled command")


if __name__ == "__main__":
    sys.exit(main())
