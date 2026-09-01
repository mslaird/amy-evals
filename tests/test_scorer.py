"""Tests for the scorer. Pure functions only -- no network, no API key, no calls."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from amy_evals.scorer import score_call, aggregate

FIX = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
load = lambda cid: json.loads((FIX / f"{cid}.json").read_text())


def test_known_good_call_passes():
    r = score_call(load("fx-002"))
    assert r.passed, [c.detail for c in r.failures]


def test_forbidden_calendar_language_is_caught():
    """fx-007 says 'let me check the calendar' -- forbidden by the agent prompt."""
    r = score_call(load("fx-007"))
    assert not r.passed
    assert any("let me check the calendar" in c.detail for c in r.failures)


def test_solicitor_must_not_produce_a_crm_record():
    """fx-008 wrote a CRM record for a solicitor. The verification doc forbids it."""
    r = score_call(load("fx-008"))
    assert not r.passed
    assert any(c.name == "crm_record" and not c.passed for c in r.checks)


def test_texting_offer_is_caught():
    """Amy has no SMS capability; offering to text is a hard failure."""
    r = score_call(load("fx-009"))
    assert not r.passed
    assert any("text" in c.detail.lower() for c in r.failures)


def test_solicitors_excluded_from_containment_denominator():
    """A declined solicitor is neither contained nor escalated; counting it as
    containment would inflate the metric."""
    ts = [load("fx-004"), load("fx-005")]     # one escalation, one solicitor
    m = aggregate([score_call(t) for t in ts], ts)
    assert m["containment_pct"] == 0.0        # 1 non-solicitor call, and it escalated
    assert m["escalation_pct"] == 50.0        # 1 of 2 total calls


def test_misbehaving_solicitor_still_excluded_from_containment():
    """The regression the outcome-based filter missed.

    fx-008 is a solicitor whose planted failure ends the call as "Message taken".
    Excluding by outcome string let it into the containment denominator and
    scored it as a win -- inflating exactly the metric the exclusion exists to
    protect. Exclusion is keyed on scenario_id, so a solicitor stays out no
    matter how the call ends.
    """
    ts = [load("fx-004"), load("fx-008")]     # one escalation, one misbehaving solicitor
    m = aggregate([score_call(t) for t in ts], ts)
    assert m["containment_pct"] == 0.0        # fx-008 must not count as contained


def test_ai_disclosure_requires_the_word_not_a_substring():
    """"ai" is a substring of "email", "details" and "again".

    A bare containment check passed the disclosure requirement for an agent that
    never disclosed. Matching is word-boundary.
    """
    from amy_evals.scorer import _says_word
    assert not _says_word("i will email you the details", "ai")
    assert not _says_word("let me say that again", "ai")
    assert _says_word("i am an ai assistant", "ai")
    assert _says_word("i will email you", "email")


def test_latency_percentiles_come_from_transcripts():
    ts = [load(c) for c in ("fx-001", "fx-002", "fx-003")]
    m = aggregate([score_call(t) for t in ts], ts)
    assert m["agent_turn_latency_p50_ms"] is not None
    assert m["agent_turn_latency_p95_ms"] >= m["agent_turn_latency_p50_ms"]
