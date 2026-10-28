"""Honest result model for anything that "runs a check": a functional test case, a probe, an audit step.

Rules enforced at construction time (a result that breaks them cannot exist):
  * PASSED / FAILED need evidence: something a person can open and verify (a screenshot path, an HTTP status, a response excerpt).
  * BLOCKED / NOT_EXECUTED need a reason: why the check could not run or could not reach a verdict.
  * A substitution (e.g. the case asks for persona "SP-01" and it ran with an existing equivalent profile) must be declared, not hidden.

`summarize()` reports the executed share and the pass rate ONLY over what actually ran: a case that did not run never counts
as passed, and a suite where nothing ran reports a pass rate of None, not 0 % and not 100 %.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional


class Status(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"            # started, but something outside the check stopped it (login failed, element missing, data absent)
    NOT_EXECUTED = "NOT_EXECUTED"  # never started (no handler, out of scope, decided not to run)

    @property
    def executed(self) -> bool:
        return self in (Status.PASSED, Status.FAILED)


class ResultError(ValueError):
    pass


@dataclass
class Evidence:
    kind: str                      # "screenshot" | "http" | "text"
    value: str                     # path, "POST /api/x -> 400", or a short excerpt
    note: str = ""


@dataclass
class CaseResult:
    case_id: str
    status: Status
    criterion: str = ""
    detail: str = ""
    reason: str = ""                               # mandatory for BLOCKED / NOT_EXECUTED
    evidence: List[Evidence] = field(default_factory=list)
    substitution: str = ""                         # what ran differently from the written case, if anything
    security_relevant: bool = False                # the failure says something about access control / data exposure
    meta: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.status, Status):
            try:
                self.status = Status(self.status)
            except ValueError as e:
                raise ResultError(f"{self.case_id}: estado desconocido {self.status!r}") from e
        if not (self.case_id or "").strip():
            raise ResultError("case_id vacío")
        if self.status.executed and not self.evidence:
            raise ResultError(f"{self.case_id}: un resultado {self.status.value} necesita evidencia")
        if not self.status.executed and not (self.reason or "").strip():
            raise ResultError(f"{self.case_id}: un resultado {self.status.value} necesita el motivo")
        if self.security_relevant and self.status is not Status.FAILED:
            raise ResultError(f"{self.case_id}: solo un caso FAILED puede marcarse como relevante para seguridad")

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CaseResult":
        d = dict(d)
        d["evidence"] = [e if isinstance(e, Evidence) else Evidence(**e) for e in d.get("evidence") or []]
        return cls(**d)


def summarize(results: Iterable[CaseResult], total_planned: Optional[int] = None) -> Dict[str, Any]:
    """Counts plus two ratios that cannot be inflated: executed share over the plan, pass rate over what executed."""
    rs = list(results)
    counts = {s.value: 0 for s in Status}
    for r in rs:
        counts[r.status.value] += 1
    executed = counts[Status.PASSED.value] + counts[Status.FAILED.value]
    planned = total_planned if total_planned is not None else len(rs)
    if planned < len(rs):
        raise ResultError(f"total_planned ({planned}) menor que los resultados registrados ({len(rs)})")
    not_reported = planned - len(rs)
    return {
        "planned": planned,
        "reported": len(rs),
        "not_reported": not_reported,                # planned cases with no result at all count as not executed
        "counts": counts,
        "executed": executed,
        "executed_pct": round(100.0 * executed / planned, 1) if planned else None,
        "pass_rate_over_executed_pct": round(100.0 * counts[Status.PASSED.value] / executed, 1) if executed else None,
        "substitutions": sum(1 for r in rs if r.substitution),
        "security_failures": sum(1 for r in rs if r.security_relevant),
    }
