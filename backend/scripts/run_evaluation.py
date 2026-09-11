"""Run a deterministic RevenueRescue AI evaluation batch.

Author: Karthikeya
"""

from __future__ import annotations

import argparse

from app.evaluation.report import write_json_report


def main() -> None:
    """Parse evaluation arguments and write the report."""

    parser = argparse.ArgumentParser(description="Run a deterministic RevenueRescue AI evaluation")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--output", default="artifacts/evaluation_report.json")
    args = parser.parse_args()
    output = write_json_report(args.output, seed=args.seed, count=args.count)
    print(f"Evaluation report written to {output}")


if __name__ == "__main__":
    main()
