"""Run the eval suite over a directory of transcripts and print the metrics table."""
import argparse, json, pathlib, sys
from .scorer import score_call, aggregate


def load(directory: pathlib.Path):
    return [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Score Amy call transcripts against the golden scenarios.")
    ap.add_argument("--dir", default="fixtures", help="directory of transcript JSON files")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any call fails (for CI)")
    args = ap.parse_args(argv)

    d = pathlib.Path(args.dir)
    if not d.is_dir():
        print(f"no such directory: {d}", file=sys.stderr)
        return 2

    transcripts = load(d)
    if not transcripts:
        print(f"no transcripts found in {d}", file=sys.stderr)
        return 2

    results = [score_call(t) for t in transcripts]
    metrics = aggregate(results, transcripts)

    if args.json:
        print(json.dumps({"metrics": metrics,
                          "calls": [{"call_id": r.call_id, "scenario": r.scenario_id,
                                     "passed": r.passed,
                                     "failures": [{"check": c.name, "detail": c.detail} for c in r.failures]}
                                    for r in results]}, indent=2))
        return 0 if (not args.strict or metrics["passed"] == metrics["calls"]) else 1

    print(f"\n  Amy eval suite — {metrics['calls']} calls\n")
    print(f"  {'metric':<28} value")
    print(f"  {'-'*28} -----")
    for k in ("pass_rate_pct", "containment_pct", "escalation_pct", "ai_disclosure_pct",
              "agent_turn_latency_p50_ms", "agent_turn_latency_p95_ms", "avg_cost_usd"):
        v = metrics[k]
        print(f"  {k:<28} {'-' if v is None else v}")

    print(f"\n  {'scenario':<20} pass/total")
    for sid, b in sorted(metrics["by_scenario"].items()):
        print(f"  {sid:<20} {b['pass']}/{b['total']}")

    failed = [r for r in results if not r.passed]
    if failed:
        print(f"\n  {len(failed)} failing call(s):")
        for r in failed:
            print(f"    {r.call_id}  [{r.scenario_id}]")
            for c in r.failures:
                print(f"      - {c.detail}")
    print()
    return 1 if (args.strict and failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
