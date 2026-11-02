"""Generate docs/cli.md from the real argparse parser, so the docs cannot drift from the code.

    python scripts/gen_cli_docs.py
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from intellidoc.cli import EXIT_NEEDS_ATTENTION, EXIT_OK, build_parser  # noqa: E402


def subparsers(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def row(action) -> str:
    if action.option_strings:
        name = ", ".join(f"`{o}`" for o in action.option_strings)
        if not action.choices and not isinstance(action, argparse._StoreTrueAction):
            name += f" `{action.metavar or action.dest.upper()}`"
    else:
        name = f"`{action.metavar or action.dest}`"
    if action.choices:
        kind = " \\| ".join(map(str, action.choices))
    elif isinstance(action, argparse._StoreTrueAction):
        kind = "flag"
    else:
        kind = getattr(action.type, "__name__", "text")
    required = action.required if action.option_strings else True
    default = "" if action.default in (None, argparse.SUPPRESS, False) else f"`{action.default}`"
    return f"| {name} | {kind} | {'yes' if required else 'no'} | {default} | {action.help or ''} |"


def main() -> None:
    parser = build_parser()
    out = [
        "# CLI reference",
        "",
        "_Generated from the code by `scripts/gen_cli_docs.py`. Do not edit by hand._",
        "",
        "```",
        "python -m intellidoc COMMAND [options]",
        "```",
        "",
        f"Exit codes: `{EXIT_OK}` = every document was integrated, "
        f"`{EXIT_NEEDS_ATTENTION}` = at least one was sent to review, failed, or nothing was found.",
        "",
        "Global option: `--version` prints the version and exits.",
        "",
    ]
    for name, sub in subparsers(parser).items():
        out += [f"## `{name}`", "", sub.description or "", "", "```", sub.format_usage().strip(), "```", ""]
        actions = [a for a in sub._actions if not isinstance(a, argparse._HelpAction)]
        n = len(actions)
        out += [f"{n} argument{'s' if n != 1 else ''}:", "",
                "| Argument | Type | Required | Default | What it does |", "|---|---|---|---|---|"]
        out += [row(a) for a in actions]
        out.append("")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "cli.md").write_text("\n".join(out))
    print("wrote docs/cli.md")


if __name__ == "__main__":
    main()
