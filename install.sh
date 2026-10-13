#!/bin/sh
# Install imgkit and vidkit in one go: the system packages they need, the
# toolkit itself, and the two commands on your PATH.
#
#   curl -fsSL https://raw.githubusercontent.com/yourjhay/media-toolkit/main/install.sh | sh
#
# Running it again updates the toolkit, so it doubles as the update command.
#
# Plain POSIX sh, not bash: piped into `sh` this is dash on Debian and Ubuntu,
# and on a minimal Linux bash may not be installed yet. Everything runs from
# main() on the last line, so a download cut off part way runs nothing rather
# than half an install.
set -eu

REPO_URL="${MEDIA_TOOLKIT_REPO:-https://github.com/yourjhay/media-toolkit.git}"
INSTALL_DIR="${MEDIA_TOOLKIT_DIR:-$HOME/.local/share/media-toolkit}"
BIN_DIR="$HOME/.local/bin"
INSTALL_DEPS="yes"
MODIFY_PATH="yes"

usage() {
  cat <<USAGE
Usage: curl -fsSL .../install.sh | sh -s -- [options]

  --dir DIR           where the toolkit goes (default: ~/.local/share/media-toolkit)
  --bin-dir DIR       where imgkit and vidkit are linked (default: ~/.local/bin)
  --repo URL          clone from somewhere else, such as a fork
  --no-deps           install no system packages; use what is already there
  --no-modify-path    leave your shell profile alone
  -h, --help          show this
USAGE
}

say()  { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf '%s\n' "$*" >&2; }
die()  { printf '\n%s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------------- finding

works() {
  # On a Mac without the developer tools, /usr/bin/git and /usr/bin/python3
  # exist but only offer to install those tools. Being present is not enough.
  "$@" >/dev/null 2>&1
}

python_ok() {
  # New enough for yt-dlp, and able to build a virtualenv with pip in it.
  # Debian and Ubuntu ship python3 without ensurepip, which setup.sh needs.
  "$1" -c 'import sys, venv; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1 &&
    "$1" -m ensurepip --version >/dev/null 2>&1
}

find_python() {
  PYTHON_BIN=""
  for candidate in python3 python3.15 python3.14 python3.13 python3.12 python3.11 python3.10; do
    found=$(command -v "$candidate" 2>/dev/null) || continue
    if python_ok "$found"; then
      PYTHON_BIN="$found"
      return 0
    fi
  done
  return 1
}

has_cairo() {
  # cairosvg loads the cairo library at runtime, so pip cannot supply it and
  # nothing fails until an SVG is converted. Look for the library itself.
  for lib in \
    /opt/homebrew/lib/libcairo.2.dylib /usr/local/lib/libcairo.2.dylib \
    /opt/local/lib/libcairo.2.dylib \
    /usr/lib/libcairo.so.2 /usr/lib64/libcairo.so.2 /lib/libcairo.so.2 \
    /usr/lib/*/libcairo.so.2 /lib/*/libcairo.so.2
  do
    [ -e "$lib" ] && return 0
  done
  return 1
}

find_brew() {
  # Homebrew can be installed without being on PATH, especially in a plain sh.
  if ! command -v brew >/dev/null 2>&1; then
    for brew in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      [ -x "$brew" ] && eval "$("$brew" shellenv)" && break
    done
  fi
  command -v brew >/dev/null 2>&1
}

detect_package_manager() {
  PM=""
  if [ "$OS" = "Darwin" ]; then
    find_brew && PM="brew"
    return 0
  fi
  for candidate in apt-get dnf pacman zypper apk; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PM="$candidate"
      return 0
    fi
  done
}

# Package names differ from one manager to the next. Each "need" is one of
# git, python, bash, ffmpeg or cairo.
packages_for() {
  case "$PM:$1" in
    brew:python)    echo "python" ;;
    brew:*)         echo "$1" ;;
    apt-get:git)    echo "git ca-certificates" ;;
    apt-get:python) echo "python3 python3-venv" ;;
    apt-get:cairo)  echo "libcairo2" ;;
    dnf:python)     echo "python3" ;;
    dnf:ffmpeg)     echo "ffmpeg-free" ;;
    pacman:python)  echo "python" ;;
    zypper:python)  echo "python3 python3-pip" ;;
    zypper:cairo)   echo "libcairo2" ;;
    apk:git)        echo "git ca-certificates" ;;
    apk:python)     echo "python3 py3-pip" ;;
    *)              echo "$1" ;;
  esac
}

# ---------------------------------------------------------------- installing

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  else
    sudo "$@"
  fi
}

can_be_root() {
  [ "$(id -u)" -eq 0 ] || command -v sudo >/dev/null 2>&1
}

APT_UPDATED="no"

pkg_install() {
  case "$PM" in
    brew)
      brew install "$@" ;;
    apt-get)
      if [ "$APT_UPDATED" = "no" ]; then
        as_root apt-get update -qq
        APT_UPDATED="yes"
      fi
      # -qq does not reach dpkg, which prints hundreds of lines for ffmpeg.
      # Errors still arrive on stderr.
      as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" >/dev/null ;;
    dnf)
      as_root dnf install -y -q "$@" ;;
    pacman)
      as_root pacman -S --needed --noconfirm "$@" ;;
    zypper)
      as_root zypper --non-interactive --quiet install "$@" ;;
    apk)
      as_root apk add --no-cache --quiet "$@" ;;
  esac
}

install_homebrew() {
  # Homebrew's installer asks for a password and a keypress. Its stdin here is
  # this script arriving down the pipe, so hand it the terminal instead.
  if ! (exec </dev/tty) 2>/dev/null; then
    die "Homebrew is needed to install $1, and there is no terminal to install it from.
Install Homebrew from https://brew.sh, then run this again."
  fi
  step "Installing Homebrew, which provides $1"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty
  find_brew || die "Homebrew was installed but cannot be found. Open a new terminal and run this again."
  PM="brew"
}

install_dependencies() {
  REQUIRED=""
  EXTRAS=""
  works git --version || REQUIRED="$REQUIRED git"
  find_python         || REQUIRED="$REQUIRED python"
  works bash -c :     || REQUIRED="$REQUIRED bash"
  works ffmpeg -version || EXTRAS="$EXTRAS ffmpeg"
  has_cairo           || EXTRAS="$EXTRAS cairo"

  if [ -z "$REQUIRED$EXTRAS" ]; then
    say "Everything it needs is already installed."
    return 0
  fi

  if [ "$INSTALL_DEPS" = "no" ]; then
    [ -z "$REQUIRED" ] && return 0
    die "Missing:$REQUIRED
Install them yourself, or run this again without --no-deps."
  fi

  if [ -z "$PM" ] && [ "$OS" = "Darwin" ]; then
    install_homebrew "$(echo $REQUIRED $EXTRAS)"
  fi
  if [ -z "$PM" ]; then
    [ -z "$REQUIRED" ] && return 0
    die "Missing:$REQUIRED
This system's package manager is not one this installer knows. Install them
yourself, then run this again with --no-deps."
  fi

  # Everything outside Homebrew installs as root.
  if [ "$PM" != "brew" ] && ! can_be_root; then
    die "Installing$REQUIRED$EXTRAS needs root, and sudo is not available.
Install them yourself, then run this again with --no-deps."
  fi

  if [ -n "$REQUIRED" ]; then
    packages=""
    for need in $REQUIRED; do packages="$packages $(packages_for "$need")"; done
    step "Installing$packages"
    [ "$PM" != "brew" ] && [ "$(id -u)" -ne 0 ] && say "sudo may ask for your password."
    hint=""
    # pacman is not synced first: -Sy without -u is the partial upgrade Arch
    # warns against, and -Syu is a whole-system upgrade nobody asked for. A
    # stale or missing database then names packages the mirrors lack.
    [ "$PM" = "pacman" ] && hint="
If pacman could not find them, run sudo pacman -Syu first."
    # shellcheck disable=SC2086  # one word per package
    pkg_install $packages || die "Installing$packages failed. Install them yourself, then run this again.$hint"
  fi

  # ffmpeg and cairo each serve only part of the toolkit, and ffmpeg is not in
  # every distribution's default repositories. Failing on either should not
  # stop the rest from working.
  for need in $EXTRAS; do
    # ffmpeg usually brings cairo with it.
    [ "$need" = "cairo" ] && has_cairo && continue
    packages=$(packages_for "$need")
    step "Installing $packages"
    [ "$need" = "ffmpeg" ] && say "ffmpeg is large. This can take a few minutes."
    # shellcheck disable=SC2086
    pkg_install $packages || warn "Could not install $packages. Carrying on without it."
  done

  if [ -n "$REQUIRED" ] && ! find_python; then
    die "Python 3.10 or newer, with venv, is needed and could not be installed.
Install it yourself, then run this again."
  fi
}

# --------------------------------------------------------------- the toolkit

fetch_toolkit() {
  if [ -d "$INSTALL_DIR/.git" ] && [ -f "$INSTALL_DIR/setup.sh" ]; then
    step "Updating the toolkit in $INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only --quiet ||
      die "Could not update $INSTALL_DIR. If you have changed files in it, put them aside and run this again."
  elif [ -e "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
    # Something else lives there. It is not ours to clone over or delete.
    die "$INSTALL_DIR already exists and is not the toolkit, so it was left alone.
Choose somewhere else with --dir DIR."
  else
    step "Downloading the toolkit into $INSTALL_DIR"
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --quiet --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

run_setup() {
  step "Setting up"
  # setup.sh would warn that BIN_DIR is not on PATH; this script deals with
  # that itself just below, so let setup.sh see it as already there.
  PATH="$BIN_DIR:$PATH" PYTHON="$PYTHON_BIN" \
    bash "$INSTALL_DIR/setup.sh" --link --bin-dir "$BIN_DIR"
}

# ---------------------------------------------------------------------- PATH

profile_files() {
  case "$(basename "${SHELL:-sh}")" in
    zsh)  echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
    bash)
      # Terminal on a Mac opens login shells, which read .bash_profile.
      # Linux terminals open interactive ones, which read .bashrc.
      if [ "$OS" = "Darwin" ]; then echo "$HOME/.bash_profile"; else echo "$HOME/.bashrc"; fi ;;
    fish) echo "$HOME/.config/fish/conf.d/media-toolkit.fish" ;;
    *)    echo "$HOME/.profile" ;;
  esac
}

add_to_path() {
  PATH_ADDED=""
  case ":$ORIGINAL_PATH:" in
    *":$BIN_DIR:"*) return 0 ;;
  esac

  if [ "$MODIFY_PATH" = "no" ]; then
    say
    say "$BIN_DIR is not on your PATH. Add this to your shell profile:"
    say "  export PATH=\"$BIN_DIR:\$PATH\""
    return 0
  fi

  profile=$(profile_files)
  case "$profile" in
    *.fish) line="fish_add_path \"$BIN_DIR\"" ;;
    *)      line="export PATH=\"$BIN_DIR:\$PATH\"" ;;
  esac
  if ! grep -qsF "$line" "$profile"; then
    mkdir -p "$(dirname "$profile")"
    printf '\n# Added by the media-toolkit installer\n%s\n' "$line" >>"$profile"
  fi
  PATH_ADDED="$profile"
}

report_extras() {
  if ! works ffmpeg -version; then
    say
    say "ffmpeg is not installed. vidkit needs it for everything except downloading."
  fi
  if ! has_cairo; then
    say
    say "The cairo library is not installed. imgkit needs it for SVG -> PNG."
  fi
}

# ---------------------------------------------------------------------- main

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --dir)            [ $# -ge 2 ] || { usage >&2; exit 2; }; INSTALL_DIR="$2"; shift 2 ;;
      --dir=*)          INSTALL_DIR="${1#*=}"; shift ;;
      --bin-dir)        [ $# -ge 2 ] || { usage >&2; exit 2; }; BIN_DIR="$2"; shift 2 ;;
      --bin-dir=*)      BIN_DIR="${1#*=}"; shift ;;
      --repo)           [ $# -ge 2 ] || { usage >&2; exit 2; }; REPO_URL="$2"; shift 2 ;;
      --repo=*)         REPO_URL="${1#*=}"; shift ;;
      --no-deps)        INSTALL_DEPS="no"; shift ;;
      --no-modify-path) MODIFY_PATH="no"; shift ;;
      -h|--help)        usage; exit 0 ;;
      *)                warn "Unknown option: $1"; usage >&2; exit 2 ;;
    esac
  done

  OS=$(uname -s)
  case "$OS" in
    Darwin|Linux) ;;
    *) die "This installer handles macOS and Linux, not $OS." ;;
  esac
  ORIGINAL_PATH="$PATH"

  step "Checking what is already installed"
  detect_package_manager
  install_dependencies
  find_python || die "Python 3.10 or newer, with venv, is needed. Install it, then run this again."

  fetch_toolkit
  run_setup
  add_to_path
  report_extras

  step "Done"
  say "The toolkit is in $INSTALL_DIR. Run this installer again to update it."
  if [ -n "$PATH_ADDED" ]; then
    say "$PATH_ADDED puts $BIN_DIR on your PATH."
    say "Open a new terminal, then run imgkit or vidkit."
  fi
}

main "$@"
