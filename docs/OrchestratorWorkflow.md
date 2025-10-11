# Orchestrator Workflow (Local Coding Loop + GPT-5 Handoff)

This repo supports a repeatable loop for local coding (Steps 3–6) and a clean
handoff back to GPT-5 for planning (Steps 1–3). Guarded diff application and a
small CLI keep the loop reliable.

## Canonical Steps

Step 1 – Emit  
Capture current state: git diff, quick test traces, env pins, and a phase
manifest reference.

Step 2 – Request  
Ask GPT-5 for a Context Digest + Plan (no code).

Step 3a – Plan (local)  
Freeze the plan: targets, acceptance, constraints.

Step 3b – Patch (local)  
Produce/collect patches for the plan’s targets (use the local "Patch Mode"
diff plugin).

Step 4 – Apply  
Guarded apply of unified diffs to allowlisted targets only (from the phase
manifest).

Step 5 – Test  
Run focused acceptance tests first; summarize.

Step 6 – Status & Handoff  
Write `.ai/status.md` and a paste-ready planning request for GPT-5. Optionally
call the GPT-5 API directly.

## When to Use Copy-Paste vs API

- **Copy-Paste**: fastest, zero dependencies. Use when experimenting or when
  API access is unavailable.
- **API Call**: repeatable, logged. Use when you want a durable record and
  low-friction iterations. Requires `OPENAI_API_KEY` and network access.

## One-Command Examples

- Emit current state:
  - `python -m orchestrator.cli emit`
- Create an empty plan request skeleton for GPT-5 to fill:
  - `python -m orchestrator.cli plan-request`
- Build a paste-ready planning request (includes truncated `git diff` and last
  quick test output):
  - `python -m orchestrator.cli make-request`
- (Optional) Call the GPT-5 API to capture a response automatically:
  - `python -m orchestrator.cli call-gpt5`
- Apply a local patch guarded by the phase manifest:
  - `python -m orchestrator.cli apply patches/0001.diff`
- Run focused tests (manifest acceptance if present; otherwise quick check):
  - `python -m orchestrator.cli test`
- Write status & next-step guidance:
  - `python -m orchestrator.cli status`

## Supporting Files

- `phases/phase_current_manifest.yaml`: Declares allowed `targets`, optional
  `acceptance` tests, and constraints.
- `.ai/context.toml`: Context pins aligned with the manifest.
- `.ai/bus/notice.json`: Output of `emit`.
- `.ai/bus/request_for_gpt5.txt`: Paste-ready planning request body.
- `.ai/plan/phase_plan.json`: Plan skeleton or GPT-5 output.
- `.ai/plan/gpt5_response.json`: Raw GPT-5 API response (optional).
- `.ai/status.md`: Status and handoff summary.

## Safety & Guardrails

- `apply` refuses any path not listed in the manifest `targets`.
- Absolute paths and `..` traversal are blocked.
- Python files are AST-parsed before writing; if available, you can manually
  run `ruff --diff` for extra confidence (not required).
