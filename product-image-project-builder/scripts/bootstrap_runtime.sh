#!/usr/bin/env sh
set -eu

usage() { echo "Usage: $0 <package-root> [--install-python]" >&2; exit 4; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
root=$1
install=${2:-}
[ -z "$install" ] || [ "$install" = "--install-python" ] || usage
find_python() {
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}
python_bin=$(find_python || true)
if [ -z "$python_bin" ]; then
  [ "$install" = "--install-python" ] || { echo "Python 3.10+ is missing. Re-run with --install-python after authorizing system installation." >&2; exit 4; }
  case "$(uname -s)" in
    Darwin) if command -v brew >/dev/null 2>&1; then brew install python; else echo "Homebrew is unavailable. Install Python from https://www.python.org/downloads/macos/, then rerun." >&2; exit 4; fi ;;
    Linux) if command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip; elif command -v dnf >/dev/null 2>&1; then sudo dnf install -y python3 python3-pip; elif command -v yum >/dev/null 2>&1; then sudo yum install -y python3 python3-pip; elif command -v pacman >/dev/null 2>&1; then sudo pacman -Sy --noconfirm python python-pip; else echo "No supported Linux package manager was found." >&2; exit 4; fi ;;
    *) echo "Unsupported platform. Install Python 3.10+, then rerun." >&2; exit 4 ;;
  esac
  python_bin=$(find_python || true)
  [ -n "$python_bin" ] || { echo "Python 3.10+ is not yet available on PATH. Open a new terminal and rerun." >&2; exit 4; }
fi
runtime="$root/.runtime"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
"$python_bin" -m venv "$runtime"
"$runtime/bin/python" -m pip install --upgrade pip
"$runtime/bin/python" -m pip install -r "$script_dir/../requirements.txt"
printf '%s\n' "$runtime/bin/python"
