# amy-evals

A regression suite for a production AI voice agent.

**Amy** is an inbound voice agent I run on Retell, wired to Make, HubSpot, and Google Sheets. She
answers a real phone line: **+1 (817) 519-8552**. Call her.

This repo scores her behavior against a golden set of scenarios, deterministically, and prints a
metrics table. It runs from a clean clone with no API key and no cost.

```
$ python -m amy_evals.run --dir fixtures

  Amy eval suite — 9 calls

  metric                       value
  ---------------------------- -----
  pass_rate_pct                66.7
  containment_pct              87.5
  escalation_pct               11.1
  ai_disclosure_pct            100.0
  agent_turn_latency_p50_ms    780
  agent_turn_latency_p95_ms    1130
  avg_cost_usd                 0.1933

  3 failing call(s):
    fx-007  [asks_to_book]
      - agent said forbidden phrase 'let me check the calendar'
      - outcome 'Booked' not in ('Link sent', 'Referred to website')
```

**Those three failures are planted.** Three fixtures encode regressions I want the suite to catch: an
agent that claims it can book, one that offers to send a text, and one that files a CRM record for a
solicitor. A suite that only ever reports green has not been shown to work.

## Why this exists

The agent already had a **Tier 1 canary** — a Make scenario polling
`GET /get-phone-number/+18175198552` every six hours and alerting if the number stops pointing at the
right agent. My own build-verification doc names what that misses:

> **Tier 2 synthetic canary.** Tier 1 does not prove the line answers.

and the failure-mode table has the row: *"Line bound but audio/Twilio dead — **Not detected.**
Requires Tier 2 outbound test call."*

I deferred Tier 2 on economics — daily testing is ~$4/mo, six-hourly is ~$15–18/mo, and there was no
paying client on the line. This repo is that gap closed, and then extended: from *does it answer* to
*does it answer correctly, across six scenarios, every time.*

## Why the scorer is not an LLM judge

It would have been faster to hand each transcript to a model and ask "did the agent do the right
thing." The published measurement on that approach is bad. Across five judge models and five prompt
strategies, no configuration exceeded **~0.65 AUROC** on τ²-bench, and judges scored **0.54** on
API-call traces — near chance (arXiv:2606.09863). The error analysis is the interesting part: judges
key on *confident closing language* rather than on verified state. An agent that sounds sure gets
scored as correct.

So every check here is a string or state assertion against a rule quoted from the agent's own system
prompt. The prompt says:

> Never say any of the following: "I can get you booked", "let me check the calendar", "I'll get you
> scheduled", "what day works", "I have an opening", "I'll text you the link"

Those are literal assertions in [`amy_evals/scenarios.py`](amy_evals/scenarios.py). A failure names
the phrase and the rule. It is arguable, reproducible, and does not depend on a model's mood.

Where a judgement genuinely needs semantics — *was this caller actually frustrated?* — that lives in
the scenario label, not in inference at scoring time.

## The scenarios

Transcribed from the agent's system prompt and verification doc, not invented here.

| Scenario | Expected |
|---|---|
| `new_prospect` | Qualify, email the booking link or point at the site |
| `asks_to_book` | **Decline.** Amy has no calendar access; payment and scheduling happen together at checkout |
| `asks_for_text` | **Decline.** Amy has no SMS capability; offer email or the website |
| `frustrated_caller` | Escalate on sentiment, take a callback number, **do not attempt a booking** |
| `solicitor` | One-sentence decline, end the call, **no CRM record** |
| `ai_skeptic` | Disclose honestly; escalate if the caller is irritated rather than curious |

Declining is the pass condition on two of these. An agent that helpfully books an appointment it
cannot honor is worse than one that says no.

## Metrics, and one denominator decision worth stating

Everything in the table is computed from transcripts. Nothing is asserted.

**Containment excludes solicitors from the denominator.** A declined spam call is neither contained
nor escalated, and counting it as a win would inflate the number. That choice is enforced by a test:
[`test_solicitors_excluded_from_containment_denominator`](tests/test_scorer.py).

## Honest limits

- **The fixtures are synthetic.** I wrote them to encode the rules in the prompt. They are not real
  customer calls, contain no real names or numbers, and the metrics table above is therefore a
  demonstration of the harness — not a measurement of production traffic.
- **The live layer is opt-in.** [`amy_evals/live.py`](amy_evals/live.py) fetches real calls from
  Retell and re-implements the Tier 1 binding check in code. It needs `RETELL_API_KEY` and costs
  money per call. Nothing else in the repo does.
- **Real calls come back unlabelled.** `scenario_id` is the thing you are testing against, so it
  cannot be inferred from the call itself. Production calls must be labelled before scoring.
  Guessing the label would reintroduce exactly the judgement problem this design avoids.
- **No CI.** Six tests, run them yourself.

## Running it

```bash
python -m amy_evals.run --dir fixtures            # the table above
python -m amy_evals.run --dir fixtures --json     # machine-readable
python -m amy_evals.run --dir fixtures --strict   # exit 1 on any failure

python tests/run_tests.py                         # 6 tests, no pytest required

# optional, needs a key and spends money:
export RETELL_API_KEY=...
python -m amy_evals.live --check-binding +18175198552 --agent-id agent_xxx
python -m amy_evals.live --fetch 25
```

Python 3.9+. No third-party dependencies.

---

*Built by [Mark Laird](https://markslaird.com) · [LinkedIn](https://www.linkedin.com/in/markslaird/)*
