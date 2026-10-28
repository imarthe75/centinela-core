import pytest

from centinela_core.results import CaseResult, Evidence, ResultError, Status, summarize

EV = [Evidence("http", "POST /api/x -> 400")]


def test_passed_without_evidence_is_rejected():
    with pytest.raises(ResultError):
        CaseResult("CI-1", Status.PASSED)


def test_failed_without_evidence_is_rejected():
    with pytest.raises(ResultError):
        CaseResult("CI-1", "FAILED")


def test_blocked_and_not_executed_need_a_reason():
    with pytest.raises(ResultError):
        CaseResult("CI-1", Status.BLOCKED)
    with pytest.raises(ResultError):
        CaseResult("CI-1", Status.NOT_EXECUTED, reason="   ")
    assert CaseResult("CI-1", Status.NOT_EXECUTED, reason="sin handler").reason


def test_unknown_status_and_empty_id_are_rejected():
    with pytest.raises(ResultError):
        CaseResult("CI-1", "OK", evidence=EV)
    with pytest.raises(ResultError):
        CaseResult(" ", Status.PASSED, evidence=EV)


def test_only_failed_can_be_security_relevant():
    with pytest.raises(ResultError):
        CaseResult("CI-1", Status.PASSED, evidence=EV, security_relevant=True)
    assert CaseResult("CI-1", Status.FAILED, evidence=EV, security_relevant=True).security_relevant


def test_round_trip_dict():
    r = CaseResult("CI-2", Status.FAILED, criterion="RQ-1·CA1", evidence=EV, substitution="perfil equivalente")
    again = CaseResult.from_dict(r.to_dict())
    assert again == r and again.to_dict()["status"] == "FAILED"


def test_summary_counts_only_what_ran():
    rs = [CaseResult("a", Status.PASSED, evidence=EV), CaseResult("b", Status.FAILED, evidence=EV),
          CaseResult("c", Status.BLOCKED, reason="login"), CaseResult("d", Status.NOT_EXECUTED, reason="sin handler")]
    s = summarize(rs, total_planned=10)
    assert s["executed"] == 2 and s["executed_pct"] == 20.0
    assert s["pass_rate_over_executed_pct"] == 50.0
    assert s["not_reported"] == 6


def test_summary_with_nothing_executed_has_no_pass_rate():
    s = summarize([CaseResult("a", Status.NOT_EXECUTED, reason="x")])
    assert s["executed"] == 0 and s["pass_rate_over_executed_pct"] is None and s["executed_pct"] == 0.0


def test_summary_rejects_plan_smaller_than_results():
    with pytest.raises(ResultError):
        summarize([CaseResult("a", Status.NOT_EXECUTED, reason="x")] * 2, total_planned=1)
