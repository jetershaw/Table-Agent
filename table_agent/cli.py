"""Command-line interface for Table Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from table_agent.baseline import run_baseline_collection
from table_agent.config import load_config
from table_agent.merge import merge_crop_recognition_output
from table_agent.recognition import run_crop_recognition
from table_agent.runner import run_end_to_end
from table_agent.smoke import run_vision_smoke
from table_agent.splitter import run_split_generation
from table_agent.split_review import run_split_review


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

    smoke_parser = subparsers.add_parser(
        "smoke", help="Call MinerU and Qwen with a base64 image message."
    )
    smoke_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    smoke_parser.add_argument(
        "--image",
        default=None,
        help="Optional image path. Defaults to the first benchmark image.",
    )
    smoke_parser.add_argument(
        "--service",
        choices=["both", "mineru", "qwen"],
        default="both",
        help="Service to call. Defaults to both.",
    )

    baseline_parser = subparsers.add_parser(
        "baseline", help="Collect full-image MinerU baseline results."
    )
    baseline_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    baseline_parser.add_argument("--start", type=int, default=0)
    baseline_parser.add_argument("--end", type=int, default=None)
    baseline_parser.add_argument("--limit", type=int, default=None)
    baseline_parser.add_argument("--output-jsonl", default=None)

    split_parser = subparsers.add_parser(
        "split", help="Generate vertical split candidates and crops."
    )
    split_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    split_parser.add_argument("--start", type=int, default=0)
    split_parser.add_argument("--end", type=int, default=None)
    split_parser.add_argument("--limit", type=int, default=None)
    split_parser.add_argument("--output-json", default=None)

    review_parser = subparsers.add_parser(
        "split-review", help="Ask Qwen to review and revise vertical split cuts."
    )
    review_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    review_parser.add_argument("--start", type=int, default=0)
    review_parser.add_argument("--end", type=int, default=None)
    review_parser.add_argument("--limit", type=int, default=None)
    review_parser.add_argument("--output-json", default=None)

    crop_parser = subparsers.add_parser(
        "crop-recognize", help="Run MinerU recognition on reviewed crops."
    )
    crop_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    crop_parser.add_argument("--start", type=int, default=0)
    crop_parser.add_argument("--end", type=int, default=None)
    crop_parser.add_argument("--limit", type=int, default=None)
    crop_parser.add_argument("--output-json", default=None)

    merge_parser = subparsers.add_parser(
        "merge", help="Merge crop-level OTSL outputs and convert to HTML."
    )
    merge_parser.add_argument("--input-json", required=True)
    merge_parser.add_argument("--output-json", required=True)

    run_parser = subparsers.add_parser(
        "run", help="Run end-to-end baseline and Table Agent smoke."
    )
    run_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help=f"Path to config YAML. Defaults to {DEFAULT_CONFIG}.",
    )
    run_parser.add_argument("--start", type=int, default=0)
    run_parser.add_argument("--end", type=int, default=None)
    run_parser.add_argument("--limit", type=int, default=None)
    run_parser.add_argument("--output-jsonl", default=None)
    run_parser.add_argument("--sample-timeout", type=int, default=120)

    args = parser.parse_args()
    if args.command == "config":
        config = load_config(args.config)
        print(json.dumps(config.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "smoke":
        config = load_config(args.config)
        result = run_vision_smoke(config, args.image, args.service)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "baseline":
        config = load_config(args.config)
        result = run_baseline_collection(
            config,
            start=args.start,
            end=args.end,
            limit=args.limit,
            output_jsonl=args.output_jsonl,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "split":
        config = load_config(args.config)
        result = run_split_generation(
            config,
            start=args.start,
            end=args.end,
            limit=args.limit,
            output_json=args.output_json,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "split-review":
        config = load_config(args.config)
        result = run_split_review(
            config,
            start=args.start,
            end=args.end,
            limit=args.limit,
            output_json=args.output_json,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "crop-recognize":
        config = load_config(args.config)
        result = run_crop_recognition(
            config,
            start=args.start,
            end=args.end,
            limit=args.limit,
            output_json=args.output_json,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "merge":
        result = merge_crop_recognition_output(args.input_json, args.output_json)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "run":
        config = load_config(args.config)
        result = run_end_to_end(
            config,
            start=args.start,
            end=args.end,
            limit=args.limit,
            output_jsonl=args.output_jsonl,
            sample_timeout=args.sample_timeout,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

