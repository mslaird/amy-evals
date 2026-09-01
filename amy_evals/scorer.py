"""Deterministic scorer for Amy call transcripts.

Design note, and the reason this is not an LLM-as-judge:

The published measurement on LLM judges for agent task completion is poor --
no configuration of 5 judges x 5 prompt strategies exceeded ~0.65 AUROC on
tau2-bench, and 0.54 on API-call traces (arXiv:2606.09863). Judges latch onto
confident closing language rather than verified state. Every check here is
instead a string or state assertion against a rule quoted from the agent's own
prompt, so a result is reproducible and arguable rather than a model's opinion.

Where a judgement genuinely needs semantics (was the caller actually
frustrated?), that lives in the transcript's labelled metadata, supplied by the
scenario definition, not inferred at scoring time.
"""
import re
from dataclasses import dataclass, field
from .scenarios import BY_ID


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CallResult:
    call_id: str
    scenario_id: str
    checks: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list:
        return [c for c in self.checks if not c.passed]


def _says_word(haystack: str, phrase: str) -> bool:
    """Word-boundary containment.

    `"ai" in "i will email you"` is True, which made the AI-disclosure check
    pass for an agent that never disclosed. Every must_say phrase is matched on
    word boundaries instead.
    """
    return re.search(rf"\b{re.escape(phrase.lower())}\b", haystack) is not None


def _agent_text(transcript: dict) -> str:
    """All agent speech in one lowercased blob."""
    return " ".join(
        t.get("content", "")
        for t in transcript.get("turns", [])
        if t.get("role") == "agent"
    ).lower()


def score_call(transcript: dict) -> CallResult:
    """Score one transcript against its declared scenario.

    `transcript` shape (see fixtures/):
        {
          "call_id": str,
          "scenario_id": str,
          "turns": [{"role": "agent"|"caller", "content": str, "ms": int?}, ...],
          "post_call": {"outcome": str, ...},
          "crm_record_written": bool,
          "cost_usd": float?,
        }
    """
    scenario = BY_ID[transcript["scenario_id"]]
    said = _agent_text(transcript)
    checks = []

    for phrase in scenario.must_say:
        checks.append(CheckResult(
            name=f"says:{phrase}",
            passed=_says_word(said, phrase),
            detail="" if _says_word(said, phrase) else f"agent never said {phrase!r}",
        ))

    for phrase in scenario.must_not_say:
        hit = phrase.lower() in said
        checks.append(CheckResult(
            name=f"avoids:{phrase}",
            passed=not hit,
            detail=f"agent said forbidden phrase {phrase!r}" if hit else "",
        ))

    outcome = (transcript.get("post_call") or {}).get("outcome")
    ok = outcome in scenario.allowed_outcomes
    checks.append(CheckResult(
        name="outcome",
        passed=ok,
        detail="" if ok else f"outcome {outcome!r} not in {scenario.allowed_outcomes}",
    ))

    wrote = bool(transcript.get("crm_record_written"))
    ok = wrote == scenario.expect_crm_record
    checks.append(CheckResult(
        name="crm_record",
        passed=ok,
        detail="" if ok else f"crm_record_written={wrote}, expected {scenario.expect_crm_record}",
    ))

    return CallResult(
        call_id=transcript.get("call_id", "?"),
        scenario_id=transcript["scenario_id"],
        checks=checks,
    )


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100)
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))


def aggregate(results, transcripts):
    """Roll per-call results into the metrics table.

    Every number here is computed from the transcripts. Nothing is asserted.
    """
    total = len(results)
    by_scenario = {}
    for r in results:
        b = by_scenario.setdefault(r.scenario_id, {"pass": 0, "total": 0})
        b["total"] += 1
        b["pass"] += 1 if r.passed else 0

    outcomes = [(t.get("post_call") or {}).get("outcome") for t in transcripts]
    escalated = sum(1 for o in outcomes if o == "Escalated to Mark")
    # Containment = resolved without handing off to a human. Solicitors are
    # excluded from the denominator: declining spam is neither containment nor
    # escalation, and counting it as a "win" would inflate the number.
    # Both conditions are load-bearing, and they catch different things. The
    # scenario_id test excludes a solicitor call however it ends -- that is the
    # regression the outcome-only version missed. The outcome test still excludes
    # a call from any other scenario that turned out to be a solicitor once Amy
    # heard it, which is the ordinary case and is not knowable from the label.
    non_solicitor = [
        o for t, o in zip(transcripts, outcomes)
        if t.get("scenario_id") != "solicitor" and o not in ("Solicitor", "Declined")
    ]
    contained = sum(1 for o in non_solicitor if o != "Escalated to Mark")

    disclosed = sum(1 for t in transcripts if _says_word(_agent_text(t), "ai"))

    latencies = [turn["ms"] for t in transcripts for turn in t.get("turns", [])
                 if turn.get("role") == "agent" and isinstance(turn.get("ms"), int)]
    costs = [t["cost_usd"] for t in transcripts if isinstance(t.get("cost_usd"), (int, float))]

    return {
        "calls": total,
        "passed": sum(1 for r in results if r.passed),
        "pass_rate_pct": round(100 * sum(1 for r in results if r.passed) / total, 1) if total else None,
        "containment_pct": round(100 * contained / len(non_solicitor), 1) if non_solicitor else None,
        "escalation_pct": round(100 * escalated / total, 1) if total else None,
        "ai_disclosure_pct": round(100 * disclosed / total, 1) if total else None,
        "agent_turn_latency_p50_ms": _percentile(latencies, 50),
        "agent_turn_latency_p95_ms": _percentile(latencies, 95),
        "avg_cost_usd": round(sum(costs) / len(costs), 4) if costs else None,
        "by_scenario": by_scenario,
    }
