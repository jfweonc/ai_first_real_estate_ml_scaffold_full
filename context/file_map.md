# File Map (top-level prompts include only what’s needed)
- .agents/* : role prompts and guardrails
- contracts/* : schemas & policies (source of truth)
- context/* : project goals, phases, tech stack
- bus/* : RFC/Proposal/Critique/Decision JSON (+ capabilities.jsonl)
- docs/* : backlog, runbooks, roles, ADRs
- tools/* : agent runner, patch applier, capability reviewer, conductor
- src/relml/* : minimal CLI and utilities (agents will extend)
- tests/* : prompt contract tests for agent outputs
