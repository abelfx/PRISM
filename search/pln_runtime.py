"""
Live PeTTa session that evaluates `PLN.Apply` from `lib_pln.metta`.

Python search owns the agenda. MeTTa PLN owns one-step deduction.
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from prism.search.rules import ParsedSentence

ConceptSTV = Dict[str, Tuple[float, float]]

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
_DEFAULT_PETTA = os.path.join(_REPO_ROOT, "PeTTa")
_SERVER_PL = os.path.join(_REPO_ROOT, "prism", "ffi", "pln_apply_server.pl")

_SENTENCE_RE = re.compile(
    r"\(Sentence\s+\(\(([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\s+([A-Za-z0-9_\-]+)\)"
    r"\s+\(stv\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
    r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\)\)\s+\((.*?)\)\)"
)

_lock = threading.Lock()
_session: Optional["PeTTaPLNSession"] = None
_STV_DECL_RE = re.compile(
    r"STV\s+([A-Za-z0-9_\-]+)\s*\)\s*\(stv\s+([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
    r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
)


def stamp_disjoint(ev1: Sequence[str], ev2: Sequence[str]) -> bool:
    """Cheap client-side `StampDisjoint` skip before calling MeTTa."""
    if not ev1 or not ev2:
        return True
    return set(ev1).isdisjoint(set(ev2))


def parse_stv_declarations(decls: Sequence[str]) -> ConceptSTV:
    """Parse `(= (STV A) (stv 0.1667 0.9))` strings from domain generators."""
    table: ConceptSTV = {}
    for decl in decls:
        match = _STV_DECL_RE.search(decl)
        if match:
            table[match.group(1)] = (float(match.group(2)), float(match.group(3)))
    return table


def infer_concept_stvs(sentences: Sequence[Any]) -> ConceptSTV:
    """Default concept priors: strength `1/n`, confidence `0.9` (chain generator)."""
    from prism.search.rules import parse_sentence

    names: set[str] = set()
    for sentence in sentences:
        parsed = parse_sentence(sentence)
        if parsed:
            names.add(parsed.subject)
            names.add(parsed.object_node)
    n = max(len(names), 1)
    prior = round(1.0 / n, 4)
    return {name: (prior, 0.9) for name in names}


def _format_sentence(parsed: "ParsedSentence") -> str:
    stamp = " ".join(str(x) for x in parsed.evidence_stamp)
    return (
        f"(Sentence (({parsed.relation} {parsed.subject} {parsed.object_node}) "
        f"(stv {parsed.strength} {parsed.confidence})) ({stamp}))"
    )


def _format_stv_decls(stvs: ConceptSTV) -> str:
    lines = []
    for name in sorted(stvs):
        strength, confidence = stvs[name]
        lines.append(f"(= (STV {name}) (stv {strength} {confidence}))")
    return "\n".join(lines)


def _parse_apply_results(lines: Sequence[str]) -> Optional[Any]:
    from prism.search.rules import parse_sentence

    for line in lines:
        # An undefined PLN.Apply is returned unevaluated and contains its input
        # Sentences.  Never mistake one of those premises for a conclusion.
        if "PLN.Apply" in line:
            continue
        for match in _SENTENCE_RE.finditer(line):
            rel, sub, obj = match.group(1), match.group(2), match.group(3)
            strength = float(match.group(4))
            confidence = float(match.group(5))
            if confidence <= 0.0:
                continue
            stamp = [tok for tok in match.group(6).split() if tok]
            sentence = ["Sentence", [[rel, sub, obj], ["stv", strength, confidence]], stamp]
            if parse_sentence(sentence) is not None:
                return sentence
    return None


class PeTTaPLNSession:
    """Long-lived `swipl` process with `lib_pln.metta` loaded."""

    def __init__(self, petta_home: Optional[str] = None) -> None:
        self.petta_home = os.path.abspath(petta_home or os.environ.get("PETTA_HOME", _DEFAULT_PETTA))
        self._proc: Optional[subprocess.Popen[str]] = None
        self._installed_stvs: Optional[ConceptSTV] = None
        self._stderr_lines: List[str] = []
        self._stderr_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        env = os.environ.copy()
        env["PETTA_HOME"] = self.petta_home
        pythonpath = [
            self.petta_home,
            os.path.join(self.petta_home, ".."),
            os.path.join(self.petta_home, "prism"),
            os.path.join(self.petta_home, "repos", "PLN"),
            env.get("PYTHONPATH", ""),
        ]
        env["PYTHONPATH"] = os.pathsep.join(p for p in pythonpath if p)
        self._proc = subprocess.Popen(
            [
                "swipl",
                "--stack_limit=8g",
                "-q",
                "-s",
                _SERVER_PL,
                "--",
                "--silent",
            ],
            cwd=self.petta_home,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._stderr_lines = []
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()
        self._installed_stvs = None
        self._command(">BOOT", timeout=120.0)

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.poll() is None and self._proc.stdin:
                self._proc.stdin.write(">QUIT\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None
        self._installed_stvs = None

    def _drain_stderr(self) -> None:
        if self._proc is None or self._proc.stderr is None:
            return
        for line in self._proc.stderr:
            self._stderr_lines.append(line.rstrip("\n"))

    def _stderr_text(self) -> str:
        return "\n".join(self._stderr_lines[-40:])

    def ensure_stvs(self, stvs: ConceptSTV) -> None:
        if self._installed_stvs == stvs:
            return
        self._command(">RESET_STVS")
        decls = _format_stv_decls(stvs)
        if decls:
            self.eval(decls)
        self._installed_stvs = dict(stvs)

    def eval(self, code: str, timeout: float = 30.0) -> List[str]:
        payload = ">EVAL\n" + code.rstrip() + "\n>END\n"
        return self._command(payload, timeout=timeout)

    def apply(self, s1: str, s2: str) -> List[str]:
        code = f"!(collapse (PLN.Apply {s1} {s2}))"
        return self.eval(code)

    def _command(self, payload: str, timeout: float = 30.0) -> List[str]:
        if self._proc is None or self._proc.poll() is not None or self._proc.stdin is None:
            raise RuntimeError("PeTTa PLN session is not running")
        self._proc.stdin.write(payload if payload.endswith("\n") else payload + "\n")
        self._proc.stdin.flush()
        return self._read_reply(timeout=timeout)

    def _read_reply(self, timeout: float) -> List[str]:
        if self._proc is None or self._proc.stdout is None:
            raise RuntimeError("PeTTa PLN session has no stdout")
        # subprocess timeout is per wait(); line reads can block. Use a crude
        # poll via communicating only if the process dies.
        lines: List[str] = []
        status: Optional[str] = None
        while True:
            if self._proc.poll() is not None:
                raise RuntimeError(f"PeTTa PLN process exited: {self._stderr_text()}")
            raw = self._proc.stdout.readline()
            if raw == "":
                raise RuntimeError(f"PeTTa PLN session closed: {self._stderr_text()}")
            text = raw.rstrip("\n")
            if text == "<OK":
                status = "ok"
                continue
            if text == "<ERR":
                status = "err"
                continue
            if text == "<END":
                break
            if text.startswith("<"):
                lines.append(text[1:])
        if status == "err":
            raise RuntimeError("PeTTa PLN error: " + " ".join(lines))
        if status != "ok":
            raise RuntimeError("PeTTa PLN protocol error")
        return lines


def get_session() -> PeTTaPLNSession:
    global _session
    with _lock:
        if _session is None:
            _session = PeTTaPLNSession()
            _session.start()
        return _session


def apply_pln_pair(
    p1: "ParsedSentence",
    p2: "ParsedSentence",
    concept_stvs: Optional[ConceptSTV] = None,
) -> Optional[Any]:
    """One `PLN.Apply` step executed by `lib_pln.metta`."""
    if p1.subject == p2.object_node:
        return None
    if not stamp_disjoint(p1.evidence_stamp, p2.evidence_stamp):
        return None

    stvs = dict(concept_stvs or {})
    if not stvs:
        stvs = infer_concept_stvs(
            [
                p1.raw,
                p2.raw,
                ["Sentence", [[p1.relation, p1.subject, p2.object_node], ["stv", 0.9, 0.9]], []],
            ]
        )
    else:
        inferred = infer_concept_stvs([p1.raw, p2.raw])
        for name, tv in inferred.items():
            stvs.setdefault(name, tv)

    session = get_session()
    session.ensure_stvs(stvs)
    lines = session.apply(_format_sentence(p1), _format_sentence(p2))
    return _parse_apply_results(lines)


def apply_pln_sentences(
    s1: Any,
    s2: Any,
    concept_stvs: Optional[ConceptSTV] = None,
) -> Optional[Any]:
    """Apply live PLN to two raw Sentence S-expressions."""
    from prism.search.rules import parse_sentence

    p1 = parse_sentence(s1)
    p2 = parse_sentence(s2)
    if p1 is None or p2 is None:
        return None
    return apply_pln_pair(p1, p2, concept_stvs)
