#!/usr/bin/env python3
"""Behavioral Probe Harness v1 — read-only identity measurement instrument.

Standalone CLI (deliberately OUTSIDE the tir package — the placement signals
"not part of the entity"). It asks the entity a frozen set of identity questions
through the REAL context-assembly path, records the answers OUTSIDE any entity
store, and writes NOTHING to working.db / archive.db / Chroma / FTS / the
workspace.

Zero-write is structural, not a flag: this script only calls readers
(retrieve, build_system_prompt_with_debug, chat_completion_text WITHOUT tools) and
never imports or calls a writer, the agent loop, or the routes module. There is no
"no-persist mode" toggle to get wrong — persistence is impossible by construction.

FROZEN INSTRUMENT DECISION — a probe turn uses AUTONOMOUS-session framing (no human
speaker), with retrieval keyed on the question text. A probe is not a conversation
with a specific person; the human-speaker framing would inject a direct-address
directive toward a nonexistent speaker and contaminate the identity signal being
measured. This framing is part of the instrument and is recorded in every results
file as framing="autonomous". Changing it changes the instrument.

Run: python -m scripts.probe [--samples 3] [--questions probe/questions.md]
                            [--out-dir probe/results] [--out PATH] [--force]
(python scripts/probe.py ... also works.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from tir.config import CHAT_MODEL, OLLAMA_HOST, get_model_options
from tir.engine.context import build_system_prompt_with_debug
from tir.engine.context_budget import AUTO_RETRIEVAL_RESULTS, budget_retrieved_chunks
from tir.engine.ollama import chat_completion_text
from tir.memory.retrieval import retrieve

# Part of the frozen instrument (see module docstring).
PROBE_FRAMING = "autonomous"
DEFAULT_QUESTIONS = Path("probe/questions.md")
DEFAULT_OUT_DIR = Path("probe/results")


# ---------------------------------------------------------------------------
# Frozen question set
# ---------------------------------------------------------------------------

def parse_questions(text: str) -> list[dict]:
    """Parse the frozen question file.

    Format: one question per block. A block starts with an H2 header ('## <id>')
    whose text is the question's stable, immutable id; the lines until the next
    '## ' (or EOF) are the question text. Lines before the first '## ' (title,
    comments) are ignored.
    """
    questions: list[dict] = []
    current_id: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_id is not None:
            questions.append({"id": current_id, "text": "\n".join(current_lines).strip()})

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            current_id = line[3:].strip()
            current_lines = []
        elif current_id is not None:
            current_lines.append(line)
    flush()

    if not questions:
        raise ValueError("No questions found (expected '## <id>' blocks).")
    ids = [q["id"] for q in questions]
    if any(not qid for qid in ids):
        raise ValueError("A question has an empty id.")
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate question ids: {ids}")
    for q in questions:
        if not q["text"]:
            raise ValueError(f"Question '{q['id']}' has empty text.")
    return questions


def load_questions(path: Path) -> tuple[list[dict], str]:
    """Load and parse the question file, returning (questions, sha256-of-file)."""
    if not path.exists():
        raise FileNotFoundError(f"Questions file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return parse_questions(raw), sha


# ---------------------------------------------------------------------------
# Run metadata helpers
# ---------------------------------------------------------------------------

def _git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _effective_model_options() -> dict:
    """Resolved chat model options (records the instrument's own settings, so a
    temperature/num_ctx change can't masquerade as identity drift)."""
    try:
        return dict(get_model_options("chat"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# The read-only probe
# ---------------------------------------------------------------------------

def run_probe_sample(question_text: str) -> dict:
    """One read-only sample: retrieve -> build (autonomous) -> generate.

    Retrieval is done explicitly so the retrieved chunk IDs can be recorded; the
    chunks are then handed to the shared builder (which is NOT modified — it
    accepts retrieved_chunks and skips its own auto-retrieval). No tools, no agent
    loop, no writers. Nothing here persists.
    """
    started = time.monotonic()

    # Match the live chat path exactly: same retrieval breadth
    # (AUTO_RETRIEVAL_RESULTS) and the same character budgeting
    # (budget_retrieved_chunks). This measures the entity under its lived memory
    # conditions and prevents the retrieved context from growing unboundedly and
    # silently overflowing num_ctx as memory accumulates.
    raw_chunks = retrieve(query=question_text, max_results=AUTO_RETRIEVAL_RESULTS)
    chunks, budget = budget_retrieved_chunks(raw_chunks)
    chunk_ids = [c.get("chunk_id") for c in chunks]

    system_prompt, debug = build_system_prompt_with_debug(
        user_name="(probe)",        # inert under autonomous framing (never rendered)
        user_message=question_text,
        retrieved_chunks=chunks,    # explicit, budgeted -> no second retrieval
        tool_descriptions=None,     # no tools
        autonomous=True,            # frozen framing: no human speaker
    )

    answer = chat_completion_text(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question_text},
        ],
        role="chat",                # normal chat model + options
    )

    return {
        "answer": answer,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "retrieved_context_chars": debug.get("retrieved_context_chars", 0),
        "retrieved_chunk_ids": chunk_ids,
        "retrieved_budget": {
            "max_chars": budget.get("max_chars"),
            "used_chars": budget.get("used_chars"),
            "input_chunks": budget.get("input_chunks"),
            "included_chunks": budget.get("included_chunks"),
            "truncated_chunks": budget.get("truncated_chunks"),
        },
    }


def run_probe(questions: list[dict], samples: int) -> list[dict]:
    """Run every question `samples` times. A failed sample is recorded and the
    run continues (one bad sample must not lose the run)."""
    results: list[dict] = []
    for q in questions:
        for i in range(samples):
            record = {
                "question_id": q["id"],
                "question_text": q["text"],
                "sample_index": i,
                "answer": None,
                "latency_ms": None,
                "retrieved_context_chars": None,
                "retrieved_chunk_ids": None,
                "retrieved_budget": None,
                "error": None,
            }
            try:
                record.update(run_probe_sample(q["text"]))
            except Exception as e:  # noqa: BLE001 — capture, don't crash the run
                record["error"] = f"{type(e).__name__}: {e}"
            status = "ok" if record["error"] is None else f"ERROR ({record['error']})"
            print(f"  {q['id']} sample {i}: {status}", file=sys.stderr)
            results.append(record)
    return results


def build_document(
    questions_path: Path, questions_sha: str, samples: int, results: list[dict]
) -> dict:
    return {
        "run": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_head": _git_head(),
            "model": CHAT_MODEL,
            "ollama_host": OLLAMA_HOST,
            "model_options": _effective_model_options(),
            "framing": PROBE_FRAMING,
            "samples_per_question": samples,
            "questions_file": str(questions_path),
            "questions_file_sha256": questions_sha,
        },
        "results": results,
    }


def _forbidden_output_roots() -> list[Path]:
    """Entity-store roots the results file must never be written under."""
    try:
        from tir.config import DATA_DIR, WORKSPACE_DIR
        return [Path(DATA_DIR).resolve(), Path(WORKSPACE_DIR).resolve()]
    except Exception:
        return []


def _resolve_out_path(args) -> Path:
    if args.out is not None:
        return args.out
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return args.out_dir / f"{date_str}.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Behavioral probe harness v1 (read-only).")
    parser.add_argument("--samples", type=int, default=3, help="Samples per question (default 3).")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--out", type=Path, default=None, help="Explicit output path (overrides dated default).")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing dated results file.")
    args = parser.parse_args(argv)

    if args.samples < 1:
        parser.error("--samples must be >= 1")

    questions, questions_sha = load_questions(args.questions)
    out_path = _resolve_out_path(args)

    if out_path.exists() and not args.force:
        parser.error(f"Results file already exists: {out_path} (use --out or --force).")

    # Defense-in-depth on top of the structural store guarantee: never write the
    # results file under an entity store (DATA_DIR / workspace).
    resolved = out_path.resolve()
    for forbidden in _forbidden_output_roots():
        if forbidden == resolved or forbidden in resolved.parents:
            parser.error(f"Refusing to write probe results under an entity store path: {forbidden}")

    total = len(questions) * args.samples
    print(f"Probe: {len(questions)} questions x {args.samples} samples = {total} generations "
          f"(framing={PROBE_FRAMING})", file=sys.stderr)

    results = run_probe(questions, args.samples)
    document = build_document(args.questions, questions_sha, args.samples, results)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ok = sum(1 for r in results if r["error"] is None)
    print(f"Wrote {out_path} ({ok}/{len(results)} samples ok)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
