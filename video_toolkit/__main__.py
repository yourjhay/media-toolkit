import sys

# A command, or no terminal to show a menu in, means the command line. Only a
# person at a terminal with nothing to say gets the menu.
if __name__ == "__main__":
    if sys.argv[1:] or not sys.stdin.isatty():
        from .cli import main
    else:
        from .tui import main
    sys.exit(main())
