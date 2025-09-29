# Real Estate ML — AI-First Scaffold (Manager + Multi-Agent)

This repo starts **from zero code** and lets AI agents (Manager, PM, Architect, Backend, Test, Data/ML, SRE/Sec) produce the implementation. You drive it from VS Code tasks and the tiny `tools/agent_runner.py` script.

## Quick start

### 0) Requirements
- Python 3.11+
- VS Code (recommended) with access to two assistants:
  - **GPT-5 (Thinking)** for Manager/PM/Architect/Sec/SRE/Data-ML
  - **Codex** (code agent) for Backend/Test/Frontend
- Git + Make (optional on Windows)

### 1) Install
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pre-commit install
```

### 2) Optional: Configure environment
```bash
cp .env.sample .env
```

### 3) Open in VS Code
Run **Tasks: Run Task** → `Agent: Manager — Start RFC`

### 4) Generate your first RFC
```bash
python tools/agent_runner.py --role manager   --goal "Design SCD2 for listing_history + promotion/monitoring hooks"   --files context/phase_plan.md context/file_map.md contracts/roles.schema.json   --engine gpt5 --emit rfc
# Copy the printed prompt into your GPT-5 chat. Save the returned RFC JSON to bus/rfc/...
```

### 5) Proposals → Critiques → Decision (≤2 rounds)
Use the VS Code tasks for Architect/Test, save outputs under `bus/`, then run Manager Decide.

### 6) Generate code patches
Agents return **unified diffs**. Apply them:
```bash
python tools/apply_patch.py --diff path/to/patch.diff
```

### 7) Validate agent outputs (prompt tests)
```bash
pytest -q
```

### 7.1) Test-first workflow (TDD)
1) Run **Agent: Test — Generate Phase 0.5 Tests** (or route Test via Manager).  
2) Apply the returned **unified diff** (tests will initially **fail**).  
3) Route **Backend** to implement; apply its diff.  
4) Re-run `pytest -q` (CI also runs `ruff`, `mypy`, and `pytest` with ≥90% coverage).

> Tip: initial spec tests are marked `xfail` where appropriate so your main branch isn’t red until the slice is actively implemented. Remove `xfail` as soon as you start coding the slice.

### 8) Capability governance
Temporary (YELLOW) auto-extensions are logged in `bus/capabilities.jsonl`. Review at phase gates:
```bash
python tools/capability_review.py --since 2025-09-01 --out reports/capability_review.md
```
