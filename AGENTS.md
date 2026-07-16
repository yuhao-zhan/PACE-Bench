# Repository Guidelines

PACE-Bench is a Python 3.10+ Box2D benchmark installed from `src/`. Keep the public surface small: `pace-bench evaluate` selects the task, target environment, model provider, and method, while `pace-bench agent` runs one coding agent in the black-box container protocol. The repository ships only the Previous-One + Best vanilla method; external methods and model providers use dotted imports.

Task physics lives under `src/pace_bench/tasks/categories/`. Do not rewrite task-local `agent.py`, `environment.py`, `evaluator.py`, `feedback.py`, `prompt.py`, `renderer.py`, or `stages.py` for cosmetic consistency.

## Commands

- `python -m pip install -r requirements.txt` installs the complete environment.
- `pace-bench list` lists the 36 tasks and environments.
- `pace-bench evaluate --task S_01 --env Stage-1 --provider mock --model mock` runs one pair.
- `pace-bench evaluate --task all --env all --provider mock --model mock --dry-run` enumerates 144 pairs.
- `pace-bench agent --task S_01 --env Stage-1 --agent custom --agent-command <command>` runs one isolated coding-agent session.
- `pace-bench validate --task S_01` validates one task's reference contract.
- `python -m compileall -q src` checks syntax.

## Invariants

Treat `Initial_to_Stage-1`-style pairs as evaluation identities. Adaptation attempt 0 evaluates the Initial reference in the target; revisions consume the feedback budget. Retry structurally invalid model output, then stop that pair. A valid candidate that fails simulation remains a normal iteration.

Constraint variables take exposure priority, visible geometry is exposed, and invisible non-constraints never reveal numeric values. Every stage suffix lists the union of mutated names without values or directions. Preserve physics constants, constraints, seeds, time steps, maximum-step semantics, reference behavior, scoring, and simulator cleanup.

Use four spaces, type public boundaries, use `pathlib.Path`, and surface errors. Avoid import-time pygame, model, GPU, or network initialization. Never commit credentials, results, model files, caches, private paper content, or generated GIF/PDF artifacts.

Agent containers must never mount the repository, task package, host credentials, or Docker socket. Keep real API keys in the per-run gateway, preserve valid-submission accounting, and return only the standard compact feedback to the Agent; full metrics stay in the trusted result JSON.
