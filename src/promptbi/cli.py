from __future__ import annotations

import argparse
from pathlib import Path

from .data import load_data
from .pipeline import run_analysis
from .tableau import create_hyper, create_tableau_public_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="PromptBI Studio command line")
    parser.add_argument("data", type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, default=Path("outputs") / "latest")
    parser.add_argument("--hyper", action="store_true", help="Create a Tableau Hyper extract")
    parser.add_argument("--public-bundle", action="store_true", help="Create a reviewed Tableau Public package")
    args = parser.parse_args()
    frame = load_data(args.data)
    result = run_analysis(frame, args.prompt)
    output = result.write(args.output)
    hyper = create_hyper(frame, output / "data.hyper") if args.hyper else None
    if args.public_bundle:
        create_tableau_public_bundle(frame, result.plan.to_dict(), output / "tableau_public_package.zip", hyper)
    print(output.resolve())


if __name__ == "__main__":
    main()

