# PACE-Bench

**PACE-Bench: Benchmarking Physics Adaptation via Code Evolution in Dynamic Environments** evaluates whether a language-model agent can adapt an executable physical design after its environment changes.

<p align="center">
  <img src="assets/pace_bench_motivation.png" alt="Static physical design versus adaptation under changing physics" width="720">
</p>

## Overview

PACE-Bench tests whether a language-model solver can adapt executable Python structures and controllers when the physical environment changes. A solver starts from an `Initial` solution, observes Box2D evaluation feedback in a mutated environment, and revises its code.

Each task contains one `Initial` environment and four mutated stages. Reference solutions verify that the source design fails each mutation while every target remains solvable. The benchmark supports API-hosted or local models, external methods, and black-box coding agents.

| Property | Count |
| --- | ---: |
| Physics categories | 6 |
| Benchmark tasks | 36 |
| Environments per task | 5 |
| Total environments | 180 |
| Initial-to-mutated pairs | 144 |

The categories are statics, kinematics, dynamics, granular/fluid interaction, control, and exotic physics.

![All 36 PACE-Bench tasks](assets/pace_bench_tasks.png)

## Repository layout

```text
PACE-Bench/
├── assets/                         # README figures
├── dataset_validation/             # dataset-construction audit prompts
├── methods/                        # paper-aligned research method plug-ins
├── src/
│   ├── custom_extension.py         # external provider/method example
│   └── pace_bench/
│       ├── agents/                 # isolated coding-Agent runtime and gateway
│       ├── cli/                    # one CLI parser and console entry point
│       ├── core/                   # shared types, paths, errors, physics, rendering
│       ├── evaluation/             # model/method benchmark runtime
│       │   ├── engine.py           # one attempt loop for every run mode
│       │   ├── providers.py        # API, local, mock, and external backends
│       │   ├── results.py          # compact JSON storage and compatibility reader
│       │   ├── metrics.py          # pair/run aggregation and analysis metrics
│       │   ├── prompt_data/        # shared demonstrations and framing
│       │   └── verification/       # safety checks and Box2D verification
│       ├── tasks/
│       │   ├── categories/
│       │   │   ├── Category1_Statics_Equilibrium/
│       │   │   ├── Category2_Kinematics_Linkages/
│       │   │   ├── Category3_Dynamics_Energy/
│       │   │   ├── Category4_Granular_FluidInteraction/
│       │   │   ├── Category5_Cybernetics_Control/
│       │   │   └── Category6_ExoticPhysics/
│       │   ├── demos/basic/        # tutorial demo; not benchmark data
│       │   ├── registry.py         # task discovery and selectors
│       │   └── stage_prompt.py     # mutation suffixes and variable inventories
│       └── __init__.py             # small public package surface
├── requirements.txt                # dependency manifest
└── pyproject.toml                  # package and CLI metadata
```

Each category contains six self-contained `TASK_ID/` directories. Every task keeps its environment, evaluator, feedback, prompt, renderer, stage definitions, and reference solutions together; the detailed module contract appears in [Architecture notes](#architecture-notes).

## Installation

PACE-Bench targets Python 3.10 and is run from a cloned checkout. `requirements.txt` ends with `-e .`, which installs this checkout and registers `pace-bench`; no PyPI release is required.

### Conda

```bash
git clone https://github.com/yuhao-zhan/PACE-Bench.git
cd PACE-Bench
conda create -n pace-bench python=3.10 -y
conda activate pace-bench
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### uv

Install [uv](https://docs.astral.sh/uv/), then run:

```bash
git clone https://github.com/yuhao-zhan/PACE-Bench.git
cd PACE-Bench
uv venv .venv --python 3.10
source .venv/bin/activate        # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### Verify

```bash
pace-bench --help
pace-bench list --task S_01
pace-bench validate --task all --contracts-only
pace-bench evaluate --task S_01 --env Stage-1 \
  --method vanilla --provider mock --model mock --attempts 1 \
  --runs 1 --output results/smoke --no-resume
```

For headless Linux:

```bash
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy
export PYGAME_HIDE_SUPPORT_PROMPT=1
```

## Evaluate a model

| Provider | Use |
| --- | --- |
| `vllm` | Recommended local/cluster inference through a vLLM server |
| `openai-compatible` | OpenAI API or another compatible HTTP endpoint |
| `local-transformers` | Direct in-process Hugging Face/Transformers loading |
| `mock` | Deterministic tests and dry runs |
| `package.module:Class` | External provider |

### API-hosted model

```bash
export OPENAI_API_KEY=<your-key>
pace-bench evaluate --task S_01 --env Stage-1 \
  --method vanilla --provider openai-compatible --model <model-name> \
  --attempts 20 --runs 2 --output results/my-run
```

For another compatible server, add `--base-url http://host:port/v1` or set `OPENAI_BASE_URL`.

### vLLM (recommended for local models)

Run vLLM in its own Linux/GPU environment or on a serving host, following the [vLLM installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/). PACE-Bench connects over HTTP, so `vllm` is deliberately not part of the benchmark's cross-platform `requirements.txt`.

```bash
# Serving host; install vLLM according to its hardware-specific instructions.
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct \
  --dtype auto --generation-config vllm

# Benchmark host; the default endpoint is http://127.0.0.1:8000/v1.
pace-bench evaluate --task K_03 --env Stage-2 \
  --method vanilla --provider vllm \
  --model Qwen/Qwen2.5-Coder-7B-Instruct \
  --attempts 20 --runs 2 --output results/qwen-vllm
```

`--model` must match the model ID exposed by vLLM (or its configured `--served-model-name`). For a remote server, pass `--base-url http://host:port/v1` or set `VLLM_BASE_URL`. If the server uses `vllm serve --api-key ...`, pass the same value with `--api-key` or `VLLM_API_KEY`. Without server authentication, PACE-Bench supplies only the placeholder required by the OpenAI client. `--workers N` may issue concurrent trajectories to the shared server; size it for the server's capacity.

### Direct Transformers loading

```bash
pace-bench evaluate --task K_03 --env Stage-2 \
  --method vanilla --provider local-transformers --model /path/to/model \
  --device cuda:0 --attempts 20
```

Use `--device mps`, `--device cpu`, or `--devices cuda:0,cuda:1 --workers 2` as appropriate.

### Select work

```bash
# One category, all target stages
pace-bench evaluate --task category_3 --env all \
  --provider openai-compatible --model <model-name>

# Explicit tasks and stages
pace-bench evaluate --task S_01 --task K_01 \
  --env Stage-1 --env Stage-3 --provider openai-compatible --model <model-name>

# Enumerate all 144 pairs without model calls
pace-bench evaluate --task all --env all --provider mock --model mock \
  --runs 1 --dry-run

# Solve Initial without a source reference
pace-bench evaluate --task D_01 --env Initial --from-scratch \
  --provider openai-compatible --model <model-name>
```

## Evaluate a coding agent as a black box

`pace-bench evaluate` controls revision prompts for a model; `pace-bench agent` lets a tool-using agent manage its own files, context, memory, and later prompts. Both receive the same initial adaptation request, few-shot demonstration, Initial reference, and attempt-0 feedback, and both use the same verifier, diagnostics, valid-submission budget, and result schema.

The trusted host keeps all task/environment source. The isolated Agent container receives only `AGENT_PROMPT.md`, `TASK.md`, `initial_solution.py`, editable `solution.py`, and the authenticated `pace-submit` client.

```mermaid
flowchart LR
    A[Isolated Codex / Claude / custom Agent] -->|solution.py| G[Credential and evaluator gateway]
    G --> V[Trusted PACE-Bench verifier]
    V --> B[Target Box2D environment]
    B -->|score and standard feedback| G
    G --> A
    G -->|real credential stays here| P[Model API]
```

### Prerequisites and isolation

- Complete the normal installation, start Docker Desktop/Engine, and confirm `docker info` works.
- Use a dedicated API key; account-login files such as `~/.codex/auth.json` are not mounted.
- The Agent has a read-only root, one writable workspace, no repository/Docker-socket mount, dropped capabilities, resource limits, and an internal-only network.
- A gateway reaches only the selected model API and evaluator session; real keys remain in the gateway while the Agent sees placeholders.
- The built-in image pins Codex and Claude CLI versions; record overrides made with `--codex-version`, `--claude-version`, or `--rebuild-image`.

### Codex

```bash
export CODEX_API_KEY=<dedicated-openai-api-key>
pace-bench agent --task S_01 --env Stage-1 --agent codex \
  --model <codex-model> --attempts 20 --runs 2 --timeout-seconds 3600 \
  --output results/codex-s01
```

`OPENAI_API_KEY` is accepted as a fallback. Codex runs non-interactively with `codex exec --ephemeral`; project rules, MCP servers, and web search are not loaded.

### Claude Code

```bash
export ANTHROPIC_API_KEY=<dedicated-anthropic-api-key>
pace-bench agent --task K_03 --env Stage-2 --agent claude \
  --model <claude-model-or-alias> --attempts 20 --max-turns 200 \
  --timeout-seconds 3600 --output results/claude-k03
```

Claude runs in non-interactive print mode with telemetry, updates, `WebSearch`, and `WebFetch` disabled.

### Custom Agent

A custom image must run from `/workspace`, read `$PACE_AGENT_PROMPT_FILE` and `$PACE_AGENT_TASK_FILE`, write `solution.py`, call `$PACE_AGENT_SUBMIT solution.py`, and stop on success or exhausted budget. It must contain Python 3 for `pace-submit`.

```bash
docker build -t my-physics-agent:latest path/to/my-agent
pace-bench agent --task D_01 --env Stage-3 --agent custom \
  --image my-physics-agent:latest \
  --agent-command "my-agent --prompt {prompt_file}" \
  --model my-agent-model --attempts 20 --output results/my-agent
```

`--agent-command` is parsed as arguments and supports `{prompt_file}`, `{task_file}`, and `{workspace}`. A hosted custom Agent can use `--custom-base-url` and `--custom-api-key-env`; inside the container it reads `PACE_AGENT_API_BASE` and the placeholder `PACE_AGENT_API_KEY`.

### Prompts, submissions, and results

The default `AGENT_PROMPT.md` starts with the vanilla model's exact initial request, then adds only the Agent execution contract. Replace it with `--prompt-file my_agent_prompt.md` without changing benchmark feedback or scoring.

```bash
./pace-submit --status        # no budget consumed
./pace-submit solution.py     # verify one candidate
```

Malformed or structurally unusable submissions are rejected without consuming the valid-submission budget; valid code that fails construction, runtime, constraints, or physics consumes one attempt normally. Accepted submissions use the same compact trajectory schema as model runs. Use `--run-index` for another run or `--overwrite` intentionally.

The isolation path blocks ordinary Agent access to benchmark source, but it is not a general multi-tenant sandbox. Use a dedicated evaluator host without unrelated secrets, keep Docker patched, use short-lived keys, and never expose the evaluator port publicly.

## Bring your own model or method

External extensions can use `package.module:Class`; see [`src/custom_extension.py`](src/custom_extension.py). A short name such as `--method reflexion` loads the corresponding version-controlled `methods/reflexion.py` plug-in. The repository includes Reflexion, Self-Refine, ACE, ExpeL, ReasoningBank/MaTTS, Tree of Thoughts, CodeEvolve, SEAL, RAGEN, and TTT-Discover; [`methods/METHODS_AUDIT.md`](methods/METHODS_AUDIT.md) records their paper adaptations, official-code comparisons, defaults, and reproduction caveats.

```bash
pace-bench evaluate --task S_01 --env Stage-1 \
  --provider custom_extension:CustomModel --model my-model \
  --method custom_extension:CustomMethod --attempts 2

# Custom methods/my_search.py exporting Method
pace-bench evaluate --task S_01 --env Stage-1 \
  --provider openai-compatible --model <model-name> \
  --method my_search --method-option beam_width=3 \
  --method-option use_memory=true --attempts 20
```

A provider implements `generate(GenerationRequest) -> GenerationResult` and `close()`. A simple method may implement the original one-request interface shown in `custom_extension.py`. Search, memory, or training methods can implement the typed V2 hooks `initialize(context, runtime)`, `build_step(history, remaining_attempts)`, `observe(attempts)`, `snapshot()`, and `finalize(result)`. A step may submit one candidate or a batch; the engine truncates it to the remaining budget, validates every candidate, and records every Box2D verification as one attempt. The runtime separately audits auxiliary LLM calls, which do not consume sandbox attempts. Repeated `--method-option KEY=VALUE` arguments are JSON-decoded and saved with the run configuration.

Vanilla Previous-One + Best remains the primary baseline and all methods inherit the same paper-wide generation defaults (`temperature=0.7`, `top_p=0.95`, and 65,536 output tokens). Method-specific search, memory, and training parameters follow the paper adaptation notes. Plug-ins must not import `evaluation_old/`, access task source through side channels, or perform unrecorded verification. SEAL, RAGEN, and TTT-Discover require the local-transformers provider for LoRA updates; the official CodeEvolve subprocess path additionally requires its external CLI.

## Validation and results

```bash
pace-bench list                                      # tasks and environments
pace-bench validate --task all --contracts-only     # imports/contracts
pace-bench validate --task S_01                     # one reference matrix
pace-bench validate --task all                      # full 36-task validation
pace-bench report --input results/my-run \
  --output results/my-run/report.json                # aggregate JSON results
```

`--runs K` executes `K` complete trajectories for every selected task pair in model or Agent mode. Paper reproduction defaults to two 20-attempt runs per pair, with `temperature=0.7`, `top_p=0.95`, and at most 65,536 output tokens for every method and auxiliary model call. Model-generation seeds deterministically combine the base `--seed`, run index, attempt index, and retry index. `--run-index` can select the first Agent run index. The CLI and `pace-bench report` calculate pair-level `Pass@1` through `Pass@K`, where `Pass@k` means that at least one of the pair's first `k` trajectories succeeds.

`--output` selects an experiment root. JSON is always saved; `--save-gif` additionally saves one GIF for every verified attempt, including adaptation attempt 0. The JSON and GIF trees intentionally mirror one another:

```text
results/<experiment>/
├── json/<task>/<model>/<method>/run-<N>/Initial_to_Stage-<K>.json
└── gif/<task>/<model>/<method>/run-<N>/Initial_to_Stage-<K>/
    ├── attempt-00.gif
    ├── attempt-01.gif
    └── ...
```

One schema `2.0` JSON represents one task-pair trajectory. It stores identity and run configuration; per-attempt code and hash, score, success, error category, failure reason, hard-constraint violations, essential structural/progress signals, token use, timing, and artifacts; plus a compact analysis block. Strategy state, batch decisions, and candidate-versus-auxiliary call totals are stored as compact JSON-safe audit metadata. Full prompts, raw responses, formatted feedback, tracebacks, coordinates, and stress arrays are omitted.

`pace-bench report` preserves every generic metric used by the former result plots and tables: Pass@k across independent runs; pass and score curves by attempt; score deviation; attempts and adaptation efficiency; prompt/completion cost; best-code size; error taxonomy; early/middle/late code similarity and radicality; budget saturation; stage/model/category/strategy breakdowns; model scale; strategy cost/Pareto data and Cohen's kappa; mutation counts; and reference-solution similarity. The report includes an explicit `legacy_metric_coverage` map from old metric names to current JSON paths. Removed-method, VLM, CE, and paper-specific plot emitters are intentionally not runtime features; their underlying generic measurements remain available. Schema `1.0` and older unversioned result JSON remain readable.

Completed JSON resumes by default; use `--no-resume` to rerun. For reproducibility, report the model revision, hardware, base seed, attempt budget, number of runs, temperature, top-p, maximum tokens, and display/headless setting.

## Architecture notes

The evaluation engine owns attempt accounting and verification; providers generate text, while methods construct single or batched requests and observe recorded attempts. The strategy runtime exposes audited auxiliary generation without exposing a second verification path. `evaluation/verification/` separates candidate safety, task loading, simulation, diagnostics, and verifier coordination because those pieces have different security and lifecycle responsibilities.

### Task prompts and shared prompt data

Each task's `prompt.py` defines its description, criteria, visible geometry, constraints, and primitive API. `stages.py` applies environment-specific updates without exposing Invisible values; this is the authoritative context for all 180 environments. `tasks/stage_prompt.py` generates the canonical, value-free mutation suffix from each task's union of mutated variable names, and the task registry rejects any mutated environment whose suffix diverges from that shared format.

`evaluation/prompt_data/` contains task-independent baseline fragments, not task/environment definitions:

| File | Role |
| --- | --- |
| `initial_demonstration.md` | From-scratch few-shot analysis/code example |
| `revision_demonstration.md` | Iterative diagnosis-and-fix example |
| `adaptation_setting.md` | Initial-to-target framing |
| `adaptation_demonstration.md` | Complete mutation-adaptation example |

The vanilla model and default Agent receive the applicable shared fragment in their identical initial request. Later, vanilla uses Previous-One + Best while the Agent manages its own history. Editing these files changes both default initial protocols.

### Task module contract

| File | Responsibility |
| --- | --- |
| `agent.py` | Initial and four stage reference solutions |
| `environment.py` | Box2D world, primitives, mutable physics, tracking |
| `evaluator.py` | Success/failure, score, constraints, raw metrics |
| `feedback.py` | Objective formatting of measured metrics |
| `prompt.py` | Task statement, exposed values, and criteria |
| `renderer.py` | Evaluation-neutral visualization |
| `stages.py` | Mutations and visibility-aware prompt updates |

Keeping these modules local makes task physics auditable without forcing all tasks into one abstraction.

### Dataset construction validation

The three reusable prompts in `dataset_validation/` correspond to the three **Dataset Construction Details** subsections in the paper appendix:

| Appendix subsection | Reusable prompt | Purpose |
| --- | --- | --- |
| Module Auditing | [`module_auditing_prompt.md`](dataset_validation/module_auditing_prompt.md) | Cross-module, prompt-exposure, suffix, runtime, and reference audit. |
| Difficulty Escalation | [`difficulty_escalation_prompt.md`](dataset_validation/difficulty_escalation_prompt.md) | Monotonic mutation hardening that maximizes required solution adaptation while preserving reference solvability. |
| Feedback Design | [`feedback_design_prompt.md`](dataset_validation/feedback_design_prompt.md) | Failure forensics, measurement-backed diagnostics, and feedback debloating. |

These Markdown prompts document the construction-time workflows and are not public evaluation entry points.

## Scope, security, and license

PACE-Bench models 2D rigid-body systems in Box2D; it does not cover 3D/deformable physics, full fluids, perception, navigation, or multi-agent coordination. Prompts and feedback are currently English-only.

Generated code is statically checked and executed with a restricted namespace, but evaluators should still use a dedicated host without unrelated credentials. Contributions must preserve physics, reference behavior, exposure rules, seeds, timing, budgets, and canonical pair identities. New comparison methods should use the narrow plug-in interface and document any departure from their paper or official implementation.

PACE-Bench is released under the [MIT License](LICENSE).
