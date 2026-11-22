# Reflection Brief — Harness Engineering Capstone

**Name:** Lipun Dani
**Date:** 20/11/2026

**Environment**

- Model(s): claude-haiku-4-5-20251001 
- OS / Python: Linux, Python 3.13.18
- Approx. API spend: ~$0.1332 for System 1's 8-claim run (per `summary.md`); System 2's compression calls cost ~12334+355 and ~11475+410 input/output tokens for the refund and subscription summaries respectively (per `budget.json`, dollar figure not itemized); System 4 ran fully offline via `--recorded-response`, $0 spend.

---

## Part 1 — Per-system

### System 1 — Agentic loop

1. **Loop control.** The trace for claim_01_kitchen_fire shows: turn 1 stop_reason: tool_use (calls `lookup_policy` and five record_claim_fact operations for incident details), turn 2 stop_reason: end_turn (no tool calls). Termination is decided in `claims_intake/loop.py`, in the run() function: after the initial client.messages.create(...) call, the model returns tool_use, causing the loop to execute lookup_policy and record_claim_fact tools, append their results, and continue the while True: loop. On the next iteration, the model returns end_turn, triggering the check if `response.stop_reason == "end_turn": ... return FinalState(...)`, which exits the loop and returns the completed claim state. Nothing else drives the loop condition - there is no maximum-turn limit, no explicit completion flag, and no text-based termination check.

2. **Anti-pattern.** `test_antipatterns.py::test_no_integer_literal_iteration_cap_in_loop` checks for a hardcoded iteration limit such as `for turn in range(3)` as a stopping mechanism. My run `/runs/20261120_071606`, recorded in `evidence/system1_agentic_loop/summary.md`, shows that `claim_03_water_damage` required 7 turns. Its trace in `runs/20261120_071606/traces/claim_03_water_damage.jsonl` shows clarification on turn 3, classification on turn 4, and routing on turn 6. A three-turn cap would have stopped before classification and routing, leaving the claim incomplete instead of waiting for `stop_reason: end_turn`.

3. **Tool design.** Two tools with overlapping inputs are `route_to_adjuster` and `escalate_to_human`. Both are designated as TERMINAL TOOLs, both should be called exactly once, and both accept a summary of the claim (`claim_summary` vs. `structured_summary`). Misrouting is prevented through their descriptions, which use the same confidence threshold from classify_claim: route_to_adjuster is used only when classification confidence is at least 0.6, while `escalate_to_human` is used when confidence is below 0.6 or the claim cannot be routed safely. Because the confidence score is determined earlier in the workflow, the two tools have mutually exclusive conditions and no overlap in decision-making. 

    A structured tool error also provides information that a generic string cannot. For example, `_t_lookup_policy` returns an error object such as:

    ``` json
    {
        "is_error": true,
        "error_category": "permanent",
        "is_retryable": false,
        "message": "policy_id '...' not found"
    }
    ```

    The `is_retryable: false` field tells the agent that repeating the same `lookup_policy call will not succeed. The agent can therefore request a corrected policy ID or escalate the case instead of wasting turns retrying. If the tool returned only a plain error string, the agent would not have a reliable signal about whether the failure was temporary or permanent, making intelligent recovery and routing much harder.

4. **Your numbers.** In `evidence/system1_agentic_loop/summary.md`, `claim_01_kitchen_fire` took 2 turns and cost an estimated $0.0087, using 6,381 input and 470 output tokens. Across all eight claims, my run cost $0.1332 and produced 4 routed and 4 escalated outcomes. The Exercise 3 `README.md` instead estimates about $0.05 for the run and expects 7 routed and 1 escalated. My run's `runs/20261120_071606/escalations.jsonl` shows that all four escalations were backstops because the model ended without a terminal action; the records do not establish why the model ended early or why the total cost differed from the estimate. The number of turns and tokens can affect cost: for example, my water-damage claim took 7 turns and cost $0.0319.

### System 2 — Context strategy

5. **The reduction.** From `budget.json`, the context budget decreased from 38,708 baseline tokens to 16,766 assembled tokens, a 56.69% reduction. The per-section token counts were: `case_facts` 204, `resolved_refund` 368, `resolved_subscription` 423, and `active` 15,789.

    The active section dominates the assembled context, accounting for 15,789 of 16,766 tokens (about 94% of the total assembled context). It is kept verbatim because it contains the ongoing conversation and the most recent issue the agent is currently working on. Since this content sits closest to the model's next response, preserving it without compression minimizes the risk of losing important details, misunderstanding the latest user intent, or introducing inaccuracies into the next turn. The older resolved threads (resolved_refund and resolved_subscription) can be aggressively compressed into summaries, while the active thread remains intact to maintain reliability and continuity in the conversation.

6. **Summarize vs preserve.** The rule is enforced in `compressor.py::summarize_segment: if segment.status != "resolved": raise ValueError(...)` - only `resolved` segments are sent through the compression call; the active segment is preserved byte-exact. My `evidence/system2_context_strategy/budget.json` records 368 tokens for `resolved_refund`, 423 for `resolved_subscription`, 204 for `case_facts`, and 15,789 for the active section. The assembled context totals 16,766 tokens, with the active section contributing about 94%. Preserving the active section avoids losing recent interactions, open questions, and unresolved details through summarization.

7. **Facts block.** Comparing `evidence/system2_context_strategy/eval.jsonl` with `eval_control.jsonl`, Q6 regressed when the case-facts block was removed. With the block, the model returned the exact payment-method update status `in_progress` and passed; without it, the model said the structured status token was unavailable and failed. The control tested only Q1 and Q6: Q1 passed, while Q6 failed. This result supports preserving structured facts for exact-field questions.

### System 3 — Claude Code config

8. **Path-scoped rules.** The test rule captured in `evidence/system3_claude_config/evidence_rule_tests.md` uses this glob frontmatter:

    ``` YAML
    ---
    description: Conventions for test files (co-located *.test.ts and *.test.tsx)
    paths:
      - "**/*.test.tsx"
      - "**/*.test.ts"
    ---
    ```

    This rule applies to matching test files across the repository, including tests co-located with React components or API handlers. A directory-level `CLAUDE.md` would apply only within its directory hierarchy, so covering tests in different directories could require duplicated instructions. Path-scoped rules keep that cross-cutting convention in one place.

9. **Forked skill.** The `.claude/skills/deploy-check/SKILL.md` frontmatter, captured in `evidence/system3_claude_config/evidence_rule_skill.md`, includes:

    ``` YAML
    context: fork
    argument-hint: "[target-branch] (defaults to main)"
    allowed-tools:
      - Read
      - Grep
      - Glob
      - Bash(git status:*)
      - Bash(git diff:*)
      - Bash(git log:*)
      - Bash(git rev-parse:*)
      - Bash(git ls-files:*)
      - Bash(gh pr view:*)
      - Bash(gh pr checks:*)
    ```

    The `fork` keeps verbose intermediate results out of the main conversation and returns a concise `summary`. The `read-only tool` list `limits the check` to inspection rather than `editing`, `pushing`, or `deploying`.

    `Without the fork`, intermediate output could clutter the `main context`. `Without the read-only restriction`, a deployment check could be given permissions to make unintended changes.


10. **Scope.** The System 3 `validator_output.txt` reports `OK`. The scope distinction is documented in `CLAUDE.md`:

    `Project-level`: `.claude/commands/review.md` defines the shared `/review` checklist for the team. Its contents are captured in `evidence_rule_review.md`.

    `User-level`: `~/.claude/CLAUDE.md` is the documented location for personal preferences, such as a preferred commit-message style. It is not shared through the project repository.

### System 4 — Orchestration

11. **Push work down.** The shift run printed `shift C: 0 new defects` even though the warm tier contained 40 defect rows (`fixtures/defects.json`). The indexed query is `WarmStore.defects_since()` in `shift_monitor/warm.py`: `SELECT * FROM defects WHERE ts > ? ORDER BY ts DESC LIMIT ?`, using the indexed `ts` column. `gather_new_defects` passes results directly from this SQL call to the prompt, with no Python-side filtering. SQLite applies the `WHERE` and `LIMIT` before rows reach the model, so it sees only new defects in the time window—not the full history.

12. **Crash recovery.** In the Orchestration folder, `recovery.py` compares the latest step timestamp with the current time and resumes only if the manifest still has incomplete steps and that timestamp is within the 30-minute staleness window. The decision can be expressed as:

    ```python
    stale_after = timedelta(minutes=30)
    can_resume = has_incomplete_steps and (now - latest_step_at) <= stale_after

    if can_resume:
        resume_from_manifest()
    else:
        start_fresh_run()
    ```

    The `<=` makes the boundary inclusive: a run aged exactly 30 minutes can resume, but one aged 31 minutes starts fresh. This avoids applying an old partial execution to a changed working set, such as a shift with newly arrived data. A fresh run can receive a compact summary of the interrupted run's findings, preserving useful results while recomputing decisions from current state instead of trusting stale intermediate reasoning.

13. **Small state.** Byte size of your `hot_state.json`. Why does the budget matter for a system run once per shift, indefinitely?
    → `data/hot_state.json` is 643 bytes, about 13% of the roughly 5 KB budget. The monitor reads and writes this state every shift, so the 20-hash cap enforced by `test_hotstate_rejects_more_than_20_hashes` helps prevent historical data from accumulating. The byte budget catches accidental state growth before it increases ongoing processing.

---

## Part 2 — Synthesis

*Graded on connecting two or more systems. Cite a named file/artifact from each.*

14. **Three layers.** 
    - Model: `claims_intake/tools.py` — `TOOL_SCHEMAS` is the model-facing action interface: it tells Claude which tools are available and constrains their inputs. Claude still chooses whether and when to request a tool, while the harness executes it.
    - Harness: `claims_intake/loop.py` — `run()` sends requests, dispatches tool calls, returns tool results to the model, and ends the loop when the response signals completion.
    - Orchestration: `shift_monitor/recovery.py` and `shift_monitor/manifest.py` — these manage persisted run progress and whether an interrupted run resumes or starts fresh, across invocations rather than within one model loop.

15. **Deterministic vs prompt.** In System 1, `tools.py` rejects a routing or escalation request if a terminal action has already been recorded. This code-enforced check prevents a claim from being both routed and escalated.

    By contrast, `system_prompt.py` guides Claude to ask for clarification when claim details are genuinely ambiguous. My run `summary.md`(eg `/evidence/system1_agentic_loop`) shows that the water-damage claim required one clarification before being routed.

16. **Context, two faces.**  System 2 manages context within a conversation: it summarizes older resolved threads while preserving structured case facts and the active conversation. My `budget.json` shows a reduction from 38,708 to 16,766 tokens (56.69%); the active section remained at 15,789 tokens and the case-facts block at 204 tokens.

    System 4 manages context between shift runs. It reloads a compact `hot_state.json` snapshot and uses `warm.py` to retrieve only defects after a specified timestamp, up to 50 rows. My `hot_state.json` evidence shows a 643-byte snapshot, below the 5,120-byte limit.

    Both minimize what the model must process while retaining useful information. `System 2` does this by summarizing and preserving parts of a transcript; `System 4` does it by persisting structured state and filtering stored data before each invocation.


17. **Reliability you can't see in one run.** System 4’s recovery test checks that an incomplete run resumes at 30 minutes but starts fresh at 31 minutes. `pytest_S4.log` records:

    ``` YAML
    test_recovery_decide_truth_table[30-False-resume] PASSED
    test_recovery_decide_truth_table[31-False-fresh] PASSED
    ```

    A successful shift without a crash would not exercise this boundary. Testing it before shipping reduces the risk of resuming stale work or unnecessarily restarting a recent run.

18. **Blast radius.** In `System 1`, a mistake could record incorrect claim facts or send a claim to the wrong adjuster queue, delaying review. The tools write routing or escalation records, while `session.py` holds each claim’s facts and outcome. In my run `summary.md`, 4 of 8 claims were routed and 4 escalated.

    The per-claim kill switch is the budget check in `loop.py`: `budget.py` raises an error when input-token or elapsed-time limits are exceeded. The defaults are `500,000 input tokens` and `180 seconds per claim`.

    Separately, `tools.py` rejects a second terminal action, and `run.py` escalates a claim if Claude finishes without one. The budget is checked between turns, so it cannot undo an incorrect action already taken or guarantee immediate interruption of an ongoing call.

---

## Part 3 — Honest assessment

19. **What broke.** Issues with running the project due to python version mismatch. Installed dependencies on `python version - 3.13` but running those dependencies on `3.10` which showed `ModuleNotFoundError: No module named 'anthropic`. 
    
    While testing (eg - `Build a Claims Intake Agent with a stop_reason-Driven Loop\exercises\03-dynamic-decomposition\solution`) it displayed errors missing dependency. So checked `python --version` to verify and fixed it by explicitly using `/voc/data/py313-venv/bin/activate`, which installed everything perfectly (`python version - 3.13`) without any trouble.

20. **What you'd change.** In `System 4`, I would replace the 50-defect query limit with paginated processing. `warm.py` returns only the newest 50 matching defects; if more exist, some could be missed. My `shift_run_output.txt` showed 0 new defects, so it did not test that high-volume case. Pagination would keep each prompt manageable while allowing all matching defects to be processed.
