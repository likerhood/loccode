from __future__ import annotations

import argparse

from mmir.pipeline import run_location
from mmir.retrievers.dense import available_dense_methods


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MM-IR localization.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    locate = subparsers.add_parser("locate", help="Run localization.")
    locate.add_argument("--samples", required=True)
    locate.add_argument("--structure-dir", required=True)
    locate.add_argument("--output-dir", required=True)
    locate.add_argument("--method", default="bm25-mmir", choices=["bm25-mmir", *available_dense_methods()])
    locate.add_argument("--dense-model", default="")
    locate.add_argument("--dense-batch-size", type=int, default=16)
    locate.add_argument("--dense-device", default="")
    locate.add_argument("--ocr-cache", default="")
    locate.add_argument("--web-cache", default="")
    locate.add_argument("--limit", type=int, default=0)
    locate.add_argument("--top-files", type=int, default=15)
    locate.add_argument("--candidate-file-pool", type=int, default=40)
    locate.add_argument("--top-modules", type=int, default=15)
    locate.add_argument("--top-functions", type=int, default=15)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "locate":
        run_location(
            samples_path=args.samples,
            structure_dir=args.structure_dir,
            output_dir=args.output_dir,
            ocr_cache=args.ocr_cache or None,
            web_cache=args.web_cache or None,
            limit=args.limit or None,
            top_files=args.top_files,
            candidate_file_pool=args.candidate_file_pool,
            top_modules=args.top_modules,
            top_functions=args.top_functions,
            method=args.method,
            dense_model=args.dense_model or None,
            dense_batch_size=args.dense_batch_size,
            dense_device=args.dense_device or None,
        )


if __name__ == "__main__":
    main()
