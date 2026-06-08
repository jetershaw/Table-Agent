"""Command-line interface for Table Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from table_agent.config import load_config


DEFAULT_CONFIG = Path("configs/default.yaml")


def main() -> int:
    parser = argparse.ArgumentParser(prog="table-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser(
        "config", help="Load, validate, and print the normalized config."
    )
    config_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )

    args = parser.parse_args()
    if args.command == "config":
        config = load_config(args.config)
        print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

