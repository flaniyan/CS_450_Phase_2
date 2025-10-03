import sys
import subprocess

if __name__ == "__main__":
    # Delegate to run.py score <urls_file>
    # usage: python3 rating.py <urls_file>
    urls = sys.argv[1:] or []
    cmd = [sys.executable, "run.py", "score"] + urls
    raise SystemExit(subprocess.call(cmd))
