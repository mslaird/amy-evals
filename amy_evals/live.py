"""Optional live layer: pull real calls from Retell and score them.

This is the Tier 2 half of the canary described in the CloudAurum build
verification doc. Tier 1 (an existing Make scenario, every 6 hours) checks that
the phone number is still bound to the right agent. It cannot tell you whether
the line actually answers, or whether the agent behaved correctly once it did.
This module closes that gap.

Requires RETELL_API_KEY. Costs money per call if you use --place. Everything in
scorer.py runs without this module, without a key, and without spending
anything -- that is deliberate.
"""
import os, sys, json, pathlib, urllib.request, urllib.error

API_BASE = "https://api.retellai.com"


def _key():
    k = os.environ.get("RETELL_API_KEY")
    if not k:
        raise SystemExit(
            "RETELL_API_KEY is not set.\n"
            "The offline suite does not need it:  python -m amy_evals.run --dir fixtures"
        )
    return k


def _get(path):
    req = urllib.request.Request(f"{API_BASE}{path}",
                                 headers={"Authorization": f"Bearer {_key()}"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def check_number_binding(number: str, expected_agent_id: str) -> dict:
    """Tier 1 equivalent, in code rather than in a Make scenario.

    Mirrors Make scenario 5968245: GET /get-phone-number/<number> and alert if
    the inbound agent id is not what we expect.
    """
    data = _get(f"/get-phone-number/{number}")
    actual = data.get("inbound_agent_id")
    return {"number": number, "expected_agent_id": expected_agent_id,
            "actual_agent_id": actual, "bound_correctly": actual == expected_agent_id}


def fetch_calls(limit: int = 50) -> list:
    """Fetch recent calls. Shapes them into the transcript format scorer.py expects.

    NOTE: scenario_id cannot be inferred from a real call -- it is the label you
    are testing against. Real calls come back with scenario_id=None and must be
    labelled before scoring, either by hand or by the scenario the live runner
    placed. Scoring unlabelled production calls is not supported on purpose: it
    would mean guessing intent, which is the thing an LLM judge does badly.
    """
    raw = _get(f"/list-calls?limit={limit}")
    out = []
    for c in (raw if isinstance(raw, list) else raw.get("calls", [])):
        turns = [{"role": "agent" if t.get("role") in ("agent", "assistant") else "caller",
                  "content": t.get("content", "")}
                 for t in (c.get("transcript_object") or [])]
        out.append({
            "call_id": c.get("call_id"),
            "scenario_id": None,
            "turns": turns,
            "post_call": (c.get("call_analysis") or {}).get("custom_analysis_data") or {},
            "crm_record_written": None,
            "cost_usd": (c.get("call_cost") or {}).get("combined_cost"),
        })
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-binding", metavar="NUMBER")
    ap.add_argument("--agent-id")
    ap.add_argument("--fetch", type=int, metavar="N", help="fetch N recent calls to ./live/")
    a = ap.parse_args(argv)

    if a.check_binding:
        if not a.agent_id:
            raise SystemExit("--check-binding requires --agent-id")
        r = check_number_binding(a.check_binding, a.agent_id)
        print(json.dumps(r, indent=2))
        return 0 if r["bound_correctly"] else 1

    if a.fetch:
        d = pathlib.Path("live"); d.mkdir(exist_ok=True)
        calls = fetch_calls(a.fetch)
        for c in calls:
            (d / f"{c['call_id']}.json").write_text(json.dumps(c, indent=2) + "\n")
        print(f"wrote {len(calls)} calls to {d}/ — label scenario_id on each before scoring")
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
