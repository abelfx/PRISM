"""Real-KG pilot: unguided PLN versus PRISM over a normalized similarity graph."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Sequence

from benchmarks.domains.kg_similarity import (
    concept_stvs,
    held_out_queries,
    load_similarity_kg,
    select_bipartite_slice,
    to_pln_sentences,
)
from prism.core.config import SearchConfig
from prism.search.engine import AStarSearchEngine


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KG = ROOT / "kgadexp.metta"
DEFAULT_PETTA = ROOT / "PeTTa"
DEFAULT_PLN = DEFAULT_PETTA / "repos" / "PLN"


def _git_revision(path: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metta_sentence(sentence: Any) -> str:
    relation, left, right = sentence[1][0]
    _, strength, confidence = sentence[1][1]
    stamp = " ".join(sentence[2])
    return f"(Sentence (({relation} {left} {right}) (stv {strength} {confidence})) ({stamp}))"


def _write_baseline_program(
    path: Path,
    facts: Sequence[Any],
    stvs: Dict[str, tuple[float, float]],
    goal: Sequence[str],
    max_steps: int,
    queue_size: int,
) -> None:
    declarations = "\n".join(
        f"(= (STV {node}) (stv {tv[0]} {tv[1]}))" for node, tv in sorted(stvs.items())
    )
    kb = "\n    ".join(_metta_sentence(fact) for fact in facts)
    goal_expr = "(" + " ".join(goal) + ")"
    # Import the exact local PLN checkout used by PRISM.  A network git-import
    # can silently select a different branch/revision and invalidate comparison.
    pln_library = (DEFAULT_PLN / "lib_pln.metta").resolve()
    program = f'''!(import! &self "{pln_library}")

{declarations}

(= (kb) ({kb}))

(= (UnguidedQuery $kb $term)
   (BestConfidenceCandidate
    (collapse
     (let ($TasksRet $BeliefsRet)
          (PLN.Derive $kb $kb 1 {max_steps} {queue_size} {queue_size} ())
          (case (superpose $BeliefsRet)
                (((Sentence ($Term $TV) $Ev)
                  (case (== $Term $term) ((True ($TV $Ev)))))))))))

!(println! (KG_BASELINE_RESULT (UnguidedQuery (kb) {goal_expr})))
'''
    path.write_text(program, encoding="utf-8")


def run_unguided_baseline(
    facts: Sequence[Any],
    stvs: Dict[str, tuple[float, float]],
    goal: Sequence[str],
    max_steps: int,
    queue_size: int,
    timeout_seconds: float,
) -> Dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", suffix=".metta", delete=False) as handle:
        temp_path = Path(handle.name)
    try:
        _write_baseline_program(temp_path, facts, stvs, goal, max_steps, queue_size)
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                ["sh", "run.sh", str(temp_path)],
                cwd=DEFAULT_PETTA,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed = time.perf_counter() - started
            output = proc.stdout + "\n" + proc.stderr
            ansi = re.compile(r"\x1b\[[0-9;]*m")
            result_text = ""
            for raw_line in output.splitlines():
                line = ansi.sub("", raw_line).strip()
                if line.startswith("(KG_BASELINE_RESULT ") and line.endswith(")"):
                    result_text = line[len("(KG_BASELINE_RESULT ") : -1]
            tv_match = re.search(
                r"\(stv\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\)\s+\(([^)]*)\)",
                result_text,
            )
            parsed = None
            if tv_match:
                parsed = {
                    "strength": float(tv_match.group(1)),
                    "confidence": float(tv_match.group(2)),
                    "evidence": tv_match.group(3).split(),
                }
            return {
                "success": parsed is not None,
                "seconds": elapsed,
                "exit_code": proc.returncode,
                "result": result_text,
                "parsed": parsed,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "seconds": timeout_seconds,
                "exit_code": None,
                "result": "",
                "parsed": None,
                "timed_out": True,
            }
    finally:
        temp_path.unlink(missing_ok=True)


def run_pilot(args: argparse.Namespace) -> Dict[str, Any]:
    kg = load_similarity_kg(args.kg)
    sources, targets, edges = select_bipartite_slice(
        kg, source_limit=args.sources, target_limit=args.targets
    )
    facts = to_pln_sentences(edges, strength=args.strength, confidence=args.confidence)
    stvs = concept_stvs((*sources, *targets))
    queries = held_out_queries(sources, limit=args.queries)
    runs: List[Dict[str, Any]] = []

    for goal in queries:
        baseline = run_unguided_baseline(
            facts, stvs, goal, args.max_steps, args.queue_size, args.timeout
        )
        engine = AStarSearchEngine(
            SearchConfig(
                max_steps=args.max_steps,
                beam_width=args.beam_width,
                guided=True,
                use_stage0_filter=True,
            )
        )
        started = time.perf_counter()
        result = engine.search(facts, facts, goal, concept_stvs=stvs)
        prism_parsed = None
        if result.goal_sentence is not None:
            prism_parsed = {
                "strength": result.goal_sentence[1][1][1],
                "confidence": result.goal_sentence[1][1][2],
                "evidence": result.goal_sentence[2],
            }
        baseline_parsed = baseline.get("parsed")
        stv_agreement = bool(
            baseline_parsed
            and prism_parsed
            and abs(baseline_parsed["strength"] - prism_parsed["strength"]) < 1e-12
            and abs(baseline_parsed["confidence"] - prism_parsed["confidence"]) < 1e-12
        )
        same_evidence_path = bool(
            stv_agreement
            and baseline_parsed["evidence"] == prism_parsed["evidence"]
        )
        runs.append(
            {
                "goal": goal,
                "baseline": baseline,
                "exact_stv_agreement": stv_agreement,
                "same_evidence_path": same_evidence_path,
                "prism": {
                    "success": result.goal_found,
                    "seconds": time.perf_counter() - started,
                    "steps": result.steps_expanded,
                    "nodes": result.nodes_generated,
                    "proof_length": len(result.proof_path),
                    "goal_sentence": result.goal_sentence,
                    "parsed": prism_parsed,
                },
            }
        )

    return {
        "schema_version": 1,
        "reproducibility": {
            "python": platform.python_version(),
            "prism_revision": _git_revision(Path(__file__).resolve().parents[1]),
            "petta_revision": _git_revision(DEFAULT_PETTA),
            "pln_revision": _git_revision(DEFAULT_PLN),
            "source_sha256": _sha256(Path(args.kg)),
            "parameters": {
                "sources": args.sources,
                "targets": args.targets,
                "queries": args.queries,
                "strength": args.strength,
                "confidence": args.confidence,
                "max_steps": args.max_steps,
                "queue_size": args.queue_size,
                "beam_width": args.beam_width,
                "timeout": args.timeout,
            },
        },
        "source": str(Path(args.kg).resolve()),
        "source_balanced": kg.is_source_syntax_balanced,
        "raw_edges": kg.raw_edge_count,
        "unique_edges": len(kg.unique_edges),
        "duplicates_removed": kg.duplicate_count,
        "slice": {
            "sources": len(sources),
            "targets": len(targets),
            "undirected_edges": len(edges),
            "pln_sentences": len(facts),
        },
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kg", default=str(DEFAULT_KG))
    parser.add_argument("--sources", type=int, default=3)
    parser.add_argument("--targets", type=int, default=6)
    parser.add_argument("--queries", type=int, default=2)
    parser.add_argument("--strength", type=float, default=0.9)
    parser.add_argument("--confidence", type=float, default=0.8)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--queue-size", type=int, default=100)
    parser.add_argument("--beam-width", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = run_pilot(args)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
