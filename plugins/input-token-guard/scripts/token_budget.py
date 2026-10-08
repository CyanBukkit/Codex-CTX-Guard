#!/usr/bin/env python3
"""Estimate text input size and split large text files into bounded chunks."""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_LIMIT = 922_000
DEFAULT_HEADROOM = 0.18
DEFAULT_MAX_CHUNK = 80_000
DEFAULT_EXCLUDES = (".git", "node_modules", "dist", "build", ".venv", "__pycache__")


def estimate_tokens(text: str) -> int:
    """Return a conservative planning estimate for mixed-language text.

    ASCII prose averages roughly four characters per token. CJK and other
    non-ASCII text commonly tokenizes closer to one character per token, so
    charge it at that rate. This intentionally overestimates many inputs.
    """
    if not text:
        return 0
    ascii_chars = sum(1 for char in text if ord(char) < 128)
    non_ascii_chars = len(text) - ascii_chars
    return max(1, math.ceil(ascii_chars / 4 + non_ascii_chars))


def should_exclude(path: Path, patterns: list[str]) -> bool:
    parts = path.parts
    return any(
        any(fnmatch.fnmatch(part, pattern) or fnmatch.fnmatch(str(path), pattern) for part in parts)
        for pattern in patterns
    )


def iter_files(inputs: list[str], excludes: list[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for raw in inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(raw)
        candidates = [path] if path.is_file() else sorted(p for p in path.rglob("*") if p.is_file())
        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved in seen or should_exclude(candidate, excludes):
                continue
            seen.add(resolved)
            yield resolved


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def payload_limit(limit: int, headroom: float) -> int:
    if not 0 <= headroom < 1:
        raise ValueError("headroom must be between 0 and 1")
    return max(1, math.floor(limit * (1 - headroom)))


def estimate_command(args: argparse.Namespace) -> int:
    excludes = args.exclude or list(DEFAULT_EXCLUDES)
    rows = []
    total_tokens = 0
    total_bytes = 0
    total_chars = 0
    files = list(iter_files(args.inputs, excludes)) if args.inputs else []
    if not files:
        text = sys.stdin.read()
        total_tokens = estimate_tokens(text)
        total_bytes = len(text.encode("utf-8"))
        total_chars = len(text)
        rows.append({"path": "<stdin>", "bytes": total_bytes, "characters": total_chars, "estimated_tokens": total_tokens})
    else:
        for path in files:
            text = read_text(path)
            tokens = estimate_tokens(text)
            size = path.stat().st_size
            rows.append({"path": str(path), "bytes": size, "characters": len(text), "estimated_tokens": tokens})
            total_tokens += tokens
            total_bytes += size
            total_chars += len(text)

    recommended = payload_limit(args.limit, args.headroom)
    status = "OK"
    if total_tokens > args.limit:
        status = "OVER_LIMIT"
    elif total_tokens > recommended:
        status = "OVER_RECOMMENDED"
    result = {
        "estimated_tokens": total_tokens,
        "configured_limit": args.limit,
        "recommended_payload_tokens": recommended,
        "remaining_to_configured_limit": args.limit - total_tokens,
        "status": status,
        "bytes": total_bytes,
        "characters": total_chars,
        "files": rows,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Estimated tokens: {total_tokens:,}")
        print(f"Configured limit: {args.limit:,}")
        print(f"Recommended payload: {recommended:,} (headroom {args.headroom:.0%})")
        print(f"Status: {result['status']}")
        print(f"Files: {len(rows)} | Bytes: {total_bytes:,} | Characters: {total_chars:,}")
        for row in rows:
            print(f"{row['estimated_tokens']:>10,} tokens  {row['path']}")
    return 2 if result["status"] == "OVER_LIMIT" else 0


def take_token_budget(text: str, max_tokens: int) -> tuple[str, str]:
    """Split text at the largest prefix within the estimated token budget."""
    if estimate_tokens(text) <= max_tokens:
        return text, ""
    low = 0
    high = len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(text[:middle]) <= max_tokens:
            low = middle
        else:
            high = middle - 1
    return text[:low], text[low:]


def split_oversized_line(line: str, max_tokens: int) -> list[str]:
    pieces = []
    remaining = line
    while remaining:
        piece, remaining = take_token_budget(remaining, max_tokens)
        if not piece:
            # Defensive fallback for pathological input where even one character
            # exceeds the requested budget.
            piece, remaining = remaining[:1], remaining[1:]
        pieces.append(piece)
    return pieces


def split_command(args: argparse.Namespace) -> int:
    if len(args.inputs) != 1:
        raise ValueError("split accepts exactly one input file")
    source = Path(args.inputs[0]).expanduser().resolve()
    if not source.is_file():
        raise ValueError("split input must be a file")
    text = read_text(source)
    lines = text.splitlines(keepends=True)
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in lines:
        line_tokens = estimate_tokens(line)
        if current and current_tokens + line_tokens > args.max_tokens:
            chunks.append("".join(current))
            overlap = current[-args.overlap_lines:] if args.overlap_lines else []
            current = list(overlap)
            current_tokens = estimate_tokens("".join(current))
        if not current and line_tokens > args.max_tokens:
            # A single giant line cannot be bounded by line boundaries.
            chunks.extend(split_oversized_line(line, args.max_tokens))
            current = []
            current_tokens = 0
        else:
            current.append(line)
            current_tokens += line_tokens
    if current:
        chunks.append("".join(current))

    manifest = []
    width = max(3, len(str(max(1, len(chunks)))))
    for index, chunk in enumerate(chunks, start=1):
        target = output_dir / f"{source.stem}.part-{index:0{width}d}{source.suffix or '.txt'}"
        target.write_text(chunk, encoding="utf-8")
        manifest.append({"path": str(target), "estimated_tokens": estimate_tokens(chunk), "characters": len(chunk)})
    (output_dir / "manifest.json").write_text(json.dumps({"source": str(source), "max_tokens": args.max_tokens, "chunks": manifest}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Created {len(manifest)} chunks in {output_dir}")
    for row in manifest:
        print(f"{row['estimated_tokens']:>10,} tokens  {row['path']}")
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Estimate and split text inputs for safe context sizing.")
    sub = root.add_subparsers(dest="command", required=True)
    estimate = sub.add_parser("estimate", help="estimate files or stdin")
    estimate.add_argument("inputs", nargs="*", help="files or directories; omit to read stdin")
    estimate.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    estimate.add_argument("--headroom", type=float, default=DEFAULT_HEADROOM)
    estimate.add_argument("--exclude", action="append", help="glob to exclude; repeatable")
    estimate.add_argument("--json", action="store_true")
    estimate.set_defaults(func=estimate_command)
    split = sub.add_parser("split", help="split one text file by estimated token budget")
    split.add_argument("input")
    split.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_CHUNK)
    split.add_argument("--overlap-lines", type=int, default=0)
    split.add_argument("--output-dir", default="work/token-chunks")
    split.set_defaults(func=split_command, inputs=[None])
    return root


def main() -> int:
    args = parser().parse_args()
    if args.command == "split":
        args.inputs = [args.input]
    try:
        return args.func(args)
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
