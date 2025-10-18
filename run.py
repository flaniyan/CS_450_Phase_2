from __future__ import annotations

import logging
import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from acmecli.cli import setup_logging  # noqa: E402


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Utility entrypoint for installing dependencies, "
            "running tests, and scoring URL files."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "install", help="Install the project in editable mode using pip."
    )
    subparsers.add_parser(
        "test", help="Run the pytest suite with coverage enabled."
    )

    score_parser = subparsers.add_parser(
        "score",
        help=(
            "Score repositories listed in the provided URL file "
            "and emit NDJSON to stdout."
        ),
    )
    score_parser.add_argument(
        "url_file",
        nargs="?",
        default="urls.txt",
        help="Path to a file containing one URL per line (defaults to urls.txt).",
    )

    return parser.parse_args(argv)


def do_install() -> int:
    base_cmd = [sys.executable, "-m", "pip", "install"]
    in_virtualenv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    user_flags: list[str] = [] if in_virtualenv else ["--user"]

    requirements = ROOT / "requirements.txt"
    if requirements.exists():
        try:
            command = base_cmd + user_flags + ["-r", str(requirements)]
            logging.debug("Installing requirements via: %s", " ".join(command))
            subprocess.check_call(command)
        except subprocess.CalledProcessError as exc:
            return exc.returncode

    try:
        command = base_cmd + user_flags + ["-e", str(ROOT)]
        logging.debug("Installing project via: %s", " ".join(command))
        subprocess.check_call(command)
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
    logging.debug("Running pytest command: %s", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    output = (proc.stdout or "") + (proc.stderr or "")

    # Parse test results with error handling
    collected = re.search(r"collected\s+(\d+)", output)
    passed = re.search(r"(\d+)\s+passed", output)
    coverage = re.search(r"TOTAL\s+.*?(\d+)%", output)

    try:
        total = int(collected.group(1)) if collected else 0
        success = int(passed.group(1)) if passed else 0
        cov_percent = int(coverage.group(1)) if coverage else 0
    except (ValueError, AttributeError):
        # Fallback if regex parsing fails
        total = 0
        success = 0
        cov_percent = 0

    print(
        f"{success}/{total} test cases passed. "
        f"{cov_percent}% line coverage achieved."
    )
    if proc.returncode != 0 and output:
        print(output)
    return proc.returncode


def do_score(url_file: str) -> int:
    """Score repositories from the provided URL file."""
    url_path = Path(url_file)
    if not url_path.exists():
        logging.error("URL file not found: %s", url_file)
        print(f"URL file not found: {url_file}", file=sys.stderr)
        return 1

    try:
        from acmecli.cli import main as cli_main
        return cli_main(["run", str(url_path)])
    except ImportError as e:
        logging.error("Failed to import acmecli.cli: %s", e)
        print(f"Error importing required modules: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logging.error("Unexpected error in scoring: %s", e)
        print(f"Error during scoring: {e}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    if not raw_args:
        return do_score("urls.txt")

    cmd = raw_args[0]
    if cmd in {"install", "test", "score"}:
        args = parse_args(raw_args)
        if args.command == "install":
            setup_logging()
            logging.info("Starting install command")
            code = do_install()
            if code == 0:
                logging.info("Install command completed successfully")
            else:
                logging.error("Install command failed with exit code %s", code)
            return code
        if args.command == "test":
            setup_logging()
            logging.info("Starting test command")
            code = do_test()
            if code == 0:
                logging.info("Test command completed successfully")
            else:
                logging.error("Test command failed with exit code %s", code)
            return code
        if args.command == "score":
            setup_logging()
            logging.info("Starting score command")
            return do_score(args.url_file)
    else:
        if len(raw_args) != 1:
            print(
                "Usage: run.py [install|test|score <URL_FILE>] or run.py <URL_FILE>",
                file=sys.stderr,
            )
            return 1
        return do_score(cmd)

    raise RuntimeError("Unhandled command")


if __name__ == "__main__":
    sys.exit(main())
