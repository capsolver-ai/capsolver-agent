"""CLI entry point for ``python -m capsolver_agent`` and the ``capsolver-agent`` console script.

Usage:
    capsolver-agent list                         # list all available tools
    capsolver-agent schema solve_captcha          # show JSON Schema for a tool
    capsolver-agent schema --format openai        # export all tools in OpenAI format
    capsolver-agent schema --format openai solve_captcha  # export one tool in OpenAI format
"""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_list(_args: argparse.Namespace) -> None:
    """List all tools with name and description."""
    from capsolver_agent.schema import get_all_tools

    tools = get_all_tools()
    for i, t in enumerate(tools, 1):
        print(f"{i}. {t.name}")
        # Wrap description at 72 chars
        desc_lines = _wrap(t.description, width=72)
        for line in desc_lines:
            print(f"   {line}")
        if i < len(tools):
            print()


def _cmd_schema(args: argparse.Namespace) -> None:
    """Show JSON Schema for one or all tools."""
    from capsolver_agent.schema import get_all_tools

    tools = get_all_tools()
    fmt = args.format

    if args.tool:
        # Single tool
        found = next((t for t in tools if t.name == args.tool), None)
        if found is None:
            names = ", ".join(t.name for t in tools)
            print(f"Error: unknown tool '{args.tool}'. Available: {names}", file=sys.stderr)
            sys.exit(1)
        if fmt == "openai":
            print(json.dumps(found.to_openai_function(), indent=2, ensure_ascii=False))
        else:
            print(json.dumps(found.to_json_schema(), indent=2, ensure_ascii=False))
    else:
        # All tools
        if fmt == "openai":
            data = [t.to_openai_function() for t in tools]
        else:
            data = [t.to_json_schema() for t in tools]
        print(json.dumps(data, indent=2, ensure_ascii=False))


def _wrap(text: str, width: int = 72) -> list[str]:
    """Simple word-wrap helper."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    length = 0
    for w in words:
        if length + len(w) + 1 > width and current:
            lines.append(" ".join(current))
            current = [w]
            length = len(w)
        else:
            current.append(w)
            length += len(w) + 1
    if current:
        lines.append(" ".join(current))
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="capsolver-agent",
        description="CapSolver Agent — inspect available tools and their schemas.",
    )
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List all available tools.")

    # schema
    schema_p = sub.add_parser("schema", help="Show JSON Schema for tools.")
    schema_p.add_argument("tool", nargs="?", default=None, help="Tool name (omit for all).")
    schema_p.add_argument(
        "--format",
        choices=["json", "openai"],
        default="json",
        help="Output format: json (default) or openai (OpenAI function-calling).",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "list": _cmd_list,
        "schema": _cmd_schema,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
