"""Prepare TaxPal chunks for GraphRAG and optionally build the graph index."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "graphrag"
DEFAULT_CHUNKS = PROJECT_ROOT / "data" / "chunks" / "all_chunks.json"


def prepare_input(chunks_path: Path, graph_root: Path, max_chunks: int = 0) -> int:
    with chunks_path.open(encoding="utf-8") as source:
        chunks = json.load(source)
    if max_chunks > 0:
        chunks = chunks[:max_chunks]

    input_dir = graph_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_path = input_dir / "tax_chunks.jsonl"
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for index, chunk in enumerate(chunks):
            record = {
                "id": str(chunk.get("chunk_id") or f"taxpal_{index:06d}"),
                "title": str(chunk.get("title") or "Uganda tax-law document"),
                "text": str(chunk.get("text") or ""),
                "source": str(chunk.get("source") or ""),
                "url": str(chunk.get("url") or ""),
                "section": str(chunk.get("section") or ""),
            }
            if record["text"].strip():
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(chunks)


def build_index(graph_root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "graphrag", "index", "--root", str(graph_root)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=0,
        help="Limit input for a lower-cost pilot; 0 uses the complete corpus.",
    )
    parser.add_argument("--index", action="store_true", help="Build the index after preparing input.")
    args = parser.parse_args()

    count = prepare_input(args.chunks.resolve(), args.root.resolve(), args.max_chunks)
    print(f"Prepared {count} TaxPal chunks under {args.root.resolve() / 'input'}.")
    if args.index:
        print("Starting GraphRAG indexing. This makes billable model requests.")
        build_index(args.root.resolve())


if __name__ == "__main__":
    main()
