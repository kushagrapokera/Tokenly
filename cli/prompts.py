"""Numbered, cross-platform terminal prompts.

Deliberately uses only `input()` — no curses or arrow-key UI, which would need
`windows-curses` on Windows. `EOFError`/`KeyboardInterrupt` are caught so the
command exits cleanly on Ctrl-D (Unix) and Ctrl-Z+Enter (Windows).
"""


def choose(title: str, options: list[tuple[str, str]]) -> str | None:
    """Print a numbered menu and return the chosen value.

    `options` is a list of (value, label). Returns the selected value, or None when
    the user chooses back/exit, enters nothing, gives invalid input, or the stream
    ends — so callers treat every "no choice" the same way.
    """
    if not options:
        print(f"(nothing to choose for {title})")
        return None

    print(title)
    for index, (_value, label) in enumerate(options, start=1):
        print(f"  {index}) {label}")
    print("  0) Back / Exit")

    while True:
        try:
            raw = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if raw in ("", "0", "q", "quit", "exit"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print(f"Please enter 1-{len(options)}, or 0 to go back.")
