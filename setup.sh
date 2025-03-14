#!/usr/bin/env bash
# Create the virtualenv, install dependencies, and optionally put imgkit and
# vidkit on your PATH. Safe to re-run.
set -euo pipefail

# Follow the symlink chain: the project lives next to the real file, not next
# to whatever link was used to reach it.
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  LINK_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$LINK_DIR/$SOURCE"
done
HERE="$(cd -P "$(dirname "$SOURCE")" && pwd)"
cd "$HERE"

COMMANDS=(imgkit vidkit)
PYTHON="${PYTHON:-python3}"

LINK_CHOICE=""     # "yes" | "no" | "" (ask, if anyone is there to ask)
BIN_DIR=""
SKIP_VENV="no"

usage() {
  cat <<USAGE
Usage: ./setup.sh [options]

  --link              put imgkit and vidkit on your PATH without asking
  --no-link           skip that step without asking
  --bin-dir DIR       link into DIR (default: ~/.local/bin)
  --link-only         skip the virtualenv; only do the linking
  -h, --help          show this
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --link)      LINK_CHOICE="yes"; shift ;;
    --no-link)   LINK_CHOICE="no"; shift ;;
    --link-only) SKIP_VENV="yes"; shift ;;
    --bin-dir)   BIN_DIR="${2:-}"; shift 2 ;;
    --bin-dir=*) BIN_DIR="${1#*=}"; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# ---------------------------------------------------------------- virtualenv

if [ "$SKIP_VENV" = "no" ]; then
  if [ ! -d .venv ]; then
    echo "Creating virtualenv..."
    "$PYTHON" -m venv .venv
  fi

  echo "Installing dependencies..."
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
  echo
fi

# ------------------------------------------------------------------- linking

if [ -z "$BIN_DIR" ]; then
  BIN_DIR="$HOME/.local/bin"
fi

if [ -z "$LINK_CHOICE" ]; then
  if [ -t 0 ]; then
    printf "Put imgkit and vidkit on your PATH, in %s? [Y/n] " "$BIN_DIR"
    read -r reply
    case "$reply" in
      [Nn]*) LINK_CHOICE="no" ;;
      *)     LINK_CHOICE="yes" ;;
    esac
  else
    # Piped, or running unattended. Do not guess, and do not hang.
    LINK_CHOICE="no"
    echo "Not linking: no terminal to ask. Re-run with --link to do it anyway."
  fi
fi

if [ "$LINK_CHOICE" = "no" ]; then
  echo
  echo "Ready. Run them with:"
  for cmd in "${COMMANDS[@]}"; do echo "  $HERE/$cmd"; done
  exit 0
fi

mkdir -p "$BIN_DIR" 2>/dev/null || true
if [ ! -d "$BIN_DIR" ] || [ ! -w "$BIN_DIR" ]; then
  echo "Cannot write to $BIN_DIR." >&2
  echo "Choose somewhere else with --bin-dir DIR, or create it yourself first." >&2
  exit 1
fi

linked=0
for cmd in "${COMMANDS[@]}"; do
  target="$BIN_DIR/$cmd"

  if [ -L "$target" ] && [ "$(readlink "$target")" = "$HERE/$cmd" ]; then
    echo "  $cmd already linked"
    linked=$((linked + 1))
    continue
  fi

  if [ -e "$target" ] || [ -L "$target" ]; then
    # Something else owns that name. It is not ours to delete.
    echo "  $cmd NOT linked: $target already exists and is not ours"
    continue
  fi

  ln -s "$HERE/$cmd" "$target"
  echo "  $cmd -> $target"
  linked=$((linked + 1))
done

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *)
    echo
    echo "$BIN_DIR is not on your PATH. Add this to your shell profile:"
    echo "  export PATH=\"$BIN_DIR:\$PATH\""
    ;;
esac

echo
if [ "$linked" -gt 0 ]; then
  echo "Ready. Run them with:  ${COMMANDS[*]}"
else
  echo "Ready. Run them with:"
  for cmd in "${COMMANDS[@]}"; do echo "  $HERE/$cmd"; done
fi
