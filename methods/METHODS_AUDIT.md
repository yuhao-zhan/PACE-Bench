# PACE-Bench Experimental Method Audit

These version-controlled scripts are research strategy plug-ins kept separate from
the benchmark runtime. Each exports a `Method` class and targets the V2 strategy
runtime (`initialize`, `build_step`, `observe`, `snapshot`, `finalize`). Audit
performed 2026-08-01 against the paper's `Method Adaptation Details` and the
official repositories linked below.

## Paper authority and shared protocol

The PACE paper is authoritative whenever its adaptation differs from an official
method repository or an earlier local experiment. Every candidate and auxiliary
backbone call inherits the run configuration: temperature `0.7`, top-p `0.95`, and
at most `65,536` output tokens by default. Every task pair uses a 20-attempt budget
and two independent runs unless the evaluator explicitly overrides those values.
Method-specific seed offsets create independent candidates but do not change the
shared sampling parameters.

### Alignment summary

| Method | Paper adaptation status |
| --- | --- |
| Vanilla | Aligned: one verified revision per attempt, Previous-One + Best history. |
| Reflexion | Aligned: 3-8 sentence reflections, FIFO limit 3. |
| Self-Refine | Aligned: at most 5 unverified inner refinements, one outer verification. |
| ACE | Aligned: Generator, Reflector, Curator, and structured playbook deltas. |
| ExpeL | Aligned: source-only distilled rules are retrieved with lazy Sup-SimCSE by default; `expel_embedder=lexical` is smoke-test only. |
| ReasoningBank/MaTTS | Mechanism and `k=2` batching aligned; exact cross-mutation reproduction requires a configured instruction-aware embedder and persisted memory input/path. |
| Tree of Thoughts | Aligned PACE adaptation: `b=3`, `n=2`, verifier-scored beam search. |
| CodeEvolve | The official subprocess bridge matches the paper execution path; the CLI-loaded in-process V2 class is an engine-safe approximation and must not be reported as the paper CodeEvolve result. |
| SEAL | Aligned PACE adaptation: reset LoRA and retrain over all positive-score pairs before the next candidate. |
| RAGEN | Aligned PACE adaptation: 5 updates × 2 episodes × 2 turns, rank 64, LR `1e-5`, 2 PPO epochs. |
| TTT-Discover | Aligned PACE adaptation: 5 iterations × 4 rollouts, 50 training epochs, rank 32, LR `4e-5`. |

## Reflexion — `methods.reflexion:Method`

- Official implementation: <https://github.com/noahshinn/reflexion>
- Audited components: HotPotQA reflection prompts and programming immediate
  Reflexion loop.
- Preserved mechanism: environment feedback is converted into verbal reflection,
  then episodic reflections guide a later candidate without parameter updates.
- PACE adaptation: the environment signal is Box2D score/feedback; reflection is a
  3-8 sentence physical diagnosis and repair plan. At most three reflections are
  retained FIFO and inserted before the task description, as specified in the
  PACE paper. The auxiliary call uses the same configured backbone runtime.
- Intentional deviation: task-specific ReAct actions, unit-test executors, and
  HotPotQA/ALFWorld memory formats are not copied.

## Self-Refine — `methods.self_refine:Method`

- Official implementation: <https://github.com/madaan/self-refine>
- Audited components: GSM feedback loop plus task-specific feedback and iterate
  modules.
- Preserved mechanism: one backbone is generator, feedback provider, and refiner;
  inner revisions receive no sandbox verification and stop on `It is correct.`.
- PACE adaptation: every benchmark attempt runs up to five distinct
  feedback-then-refine cycles, then verifies only the final candidate. A response
  that declares correctness while also providing a replacement is not accepted as
  a clean stop.
- Intentional deviation: the official repository contains task-specific variants;
  GSM emits feedback and corrected code in one response, while other tasks expose
  separate feedback/iterate components. PACE uses separate calls so the two roles
  and their token use remain auditable. The outer Box2D feedback is available only
  to the next benchmark attempt, not to the current inner loop.

## ACE — `methods.ace:Method`

- Official implementation: <https://github.com/ace-agent/ace>
- Audited components: `ACE`, Generator, Reflector, Curator, prompts, and playbook
  utilities.
- Preserved mechanism: Generator reads an itemized playbook, Reflector converts
  execution feedback into lessons and helpful/harmful tags, and Curator proposes
  incremental deltas instead of rewriting the entire context.
- PACE adaptation: candidate generation stays in the benchmark runtime; Reflector
  and Curator are auxiliary calls to the same backbone. The strategy owns a typed,
  serializable playbook and deterministically applies ADD, UPDATE, MERGE, and DELETE
  operations, helpful/harmful counters, and budget pruning.
- Corrective deviation: the audited official checkout advertises the four delta
  operations, but its current `apply_curator_operations` implementation fully
  applies only ADD. This script implements the complete advertised delta lifecycle
  so updates do not silently disappear. It does not import the ACE package or alter
  `sys.path`.

## ExpeL — `methods.expel:Method`

- Official implementation: <https://github.com/LeapLabTHU/ExpeL>
- Audited components: experience gathering, success/failure comparison, rule
  operations, embedding retrieval, and evaluation-time memory injection.
- Preserved mechanism: rollout experience is distilled into general rules, then
  relevant rules are retrieved by similarity at inference time.
- PACE adaptation: rules are extracted only from the current task's source
  environment rollout and frozen during target evaluation. Only insights are
  injected—never raw trajectories or source code—because mutated physics can make
  literal source designs misleading. A reference solution is a minimal successful
  source rollout when no explicit rollout is configured.
- Intentional deviation: official ExpeL trains across many tasks and retrieves both
  rules and trajectories. PACE's pair-based, insights-only transfer follows the
  paper adaptation. Retrieval lazily loads the paper-specified Sup-SimCSE model;
  `expel_embedder` may instead select a dotted-import callable. The explicit
  `lexical` option is retained only for lightweight orchestration smoke tests.
  There are no bundled rollout files or ExpeL/LangChain imports.

## ReasoningBank / MaTTS — `methods.reasoning_bank:Method`

- Official implementation: <https://github.com/google-research/reasoning-bank>
- Audited components: memory induction, instruction-aware retrieval, memory
  management, parallel induction, and MaTTS pipeline.
- Preserved mechanism: structured title/description/content memories are induced
  from successful and failed trajectories; MaTTS contrastively distills multiple
  verified trajectories; retrieval guides later candidates.
- PACE adaptation: Box2D success or score at least 99 supplies the correctness
  signal. Single-trajectory induction produces at most three items and parallel
  induction at most five; both inherit the paper-wide sampling settings. State is
  serializable through `snapshot` and can be restored with
  `reasoning_bank_memory` or an explicit JSONL path.
- Important configuration correction: `retrieval_top_k` (default 5) controls
  recalled memories, while `matts_k` (paper-run default 2) controls candidate batch
  width. They are not the same parameter. Each MaTTS batch is capped by
  `remaining_attempts`, so every
  sandbox verification consumes exactly one benchmark interaction and partial
  final batches cannot exceed the 20-attempt budget.
- Intentional deviation: the embedding backend is configurable via
  `reasoning_bank_embedder`; deterministic lexical retrieval is the dependency-free
  fallback. No Google Cloud client, Qwen/SimCSE model, GPU, cache path, or port is
  initialized at import time.

## Local configuration keys

These options belong in the evaluator's strategy/method configuration metadata:

| Method | Keys |
| --- | --- |
| Reflexion | `reflection_limit` |
| Self-Refine | `inner_steps` |
| ACE | `playbook_token_budget`, `ace_initial_playbook` |
| ExpeL | `retrieval_top_k`, `max_rules`, `expel_rules`, `expel_source_rollout`, `expel_source_rollout_path`, `expel_embedder`, `expel_embedding_model`, `expel_embedding_device` |
| ReasoningBank | `retrieval_top_k`, `matts_k`, `max_memory_items`, `reasoning_bank_memory`, `reasoning_bank_memory_path`, `reasoning_bank_embedder` |
| Tree of Thoughts | `beam_width`, `children_per_parent` |
| CodeEvolve | `executable`, `num_islands`, `population_size`, `exploration_rate`, `migration_interval`, `migration_rate`, `evaluation_timeout_seconds` |
| SEAL | `lora_rank`, `learning_rate`, `epochs`, `max_sequence_length` |
| RAGEN | `episodes_per_update`, `turns_per_episode`, `lora_rank`, `learning_rate`, `ppo_epochs`, `clip_low`, `clip_high`, `max_sequence_length` |
| TTT-Discover | `group_size`, `training_epochs`, `puct_c`, `archive_size`, `lora_rank`, `learning_rate`, `max_sequence_length` |

Embedding dotted imports must resolve to a callable `embed(text) -> sequence[float]`
or an object exposing `encode(text)`. Paths are read only when explicitly supplied;
the method scripts never guess developer/server locations.

## Tree of Thoughts — `tree_of_thoughts.py`

- Official implementation: <https://github.com/princeton-nlp/tree-of-thought-llm>,
  audited at `8050e67d0e3a0fddc424d7fa5801538722a4c4cc`.
- The official BFS loop generates children for every retained state, evaluates every
  child by value/vote, and greedily retains `n_select_sample` states. PACE preserves
  that generate/evaluate/select structure with code revisions as thoughts and the
  Box2D score as the state value.
- Every `beam_width * children_per_parent` child is a separate `CandidateSubmission`.
  Partial final layers are deterministically truncated to the remaining attempt
  budget. No hidden final verification or uncounted Phase-2 refinement remains.
- This is not exact official equivalence: an objective physics verifier replaces
  LLM value/vote calls, and task-specific textual thought decompositions are absent.

## CodeEvolve — `codeevolve.py`

- Official implementation: <https://github.com/inter-co/science-codeevolve>, audited
  at `c077959e1ab24b060aaa6d4c563bca2e9cbe8617`.
- The official system has island populations, tournament selection, inspiration
  programs, crossover/mutation prompts, optional prompt co-evolution, migration,
  checkpoints, and a CLI-owned evaluator. The recovered PACE wrapper's repeated outer
  rounds and extra final-best verification were not part of that loop and obscured
  the attempt budget.
- The benchmark-facing V2 method now keeps an explicit size-8 population, tournament
  parent choice, two inspirations, lineage, and island metadata in one file. Each
  child is generated and verified once by the PACE engine. This is the runnable PACE
  in-process adaptation, not a claim of exact official process/migration equivalence.
- `run_official_codeevolve` remains as an audit/reproduction bridge for an externally
  installed official CLI. Its evaluator writes every fitness call to a JSONL ledger;
  it must not be mixed with the V2 loop because doing so would double-verify candidates.

## SEAL — `seal.py`

- Official implementation: <https://github.com/Continual-Intelligence/SEAL>, audited
  at `6d9c9f9ee392c6cc618e771f399d436d190f6ca4`.
- Official SEAL learns to generate self-edits (data and update directives), applies
  SFT, and optimizes the self-edit policy through downstream reward/ReSTEM. The old
  PACE implementation was materially simpler and must not be described as faithful
  official SEAL.
- The paper's PACE adaptation is implemented honestly: positive Box2D-score
  `(prompt, code)` pairs accumulate; LoRA is reset before each training event and
  retrained from scratch over all accumulated positives with response-only loss.
  There are no ARC geometric augmentations, self-edit policy, or ReSTEM loop.
- Weight updates require the local-transformers provider plus `torch` and `peft`.
  Optional dependencies are loaded only after a positive example exists.

## RAGEN — `ragen.py`

- Official implementation: <https://github.com/mll-lab-nu/RAGEN>, audited at
  `20daedc47558e000f7de912b060646bf2e8026bd`.
- Official StarPO treats a multi-turn interaction as a trajectory, constructs masks
  over assistant turns, and performs RL with trajectory/group outcomes. The recovered
  PACE code built per-turn samples but assigned every sample `episode_idx = 0`; that
  collapses cross-episode grouping and is not valid trajectory-level GRPO.
- The consolidated method advances two independent two-turn episodes, computes one
  total return per episode, normalizes those complete returns across episodes, assigns
  the same episode advantage to both turns, and applies asymmetric PPO clipping
  (`0.2/0.28`) for two epochs. Five four-verification updates fit a 20-attempt run.
- This remains a reduced single-task LoRA adaptation (rank 64, LR `1e-5`), not the
  official distributed veRL/full-training scale.

## TTT-Discover — `ttt_discover.py`

- Official implementation: <https://github.com/test-time-training/discover>, audited
  at `6c40e82dab9d5de7416ac873ad5cd3106084aaed`.
- The PACE paper specifies five iterations of four rollouts and 50 training epochs
  per non-constant update. The implementation follows that paper adaptation even
  where the official repository organizes online updates differently. The final
  group is still recorded, but training is skipped when no later candidate can
  benefit from the update.
- The old PACE code defaulted to fixed-beta entropic advantages and did not carry the
  official state archive/PUCT sampler. The new file solves adaptive beta to target
  `KL(q || uniform) = log(2)`, computes leave-one-out entropic advantages, maintains
  PUCT visit/best-descendant statistics, and expands from selected feedback states.
- PACE uses four rollouts, LoRA rank 32, learning rate `4e-5`, and 50 training
  epochs. Constant-reward groups produce no update; the next iteration continues
  feedback-conditioned PUCT expansion instead of inventing a gradient.

## Verification status for this audit

- All five scripts pass Python bytecode compilation and focused undefined-name/static
  checks in the core PACE environment.
- Pure numerical behavior for adaptive beta, entropic advantages, trajectory GRPO,
  and V2 batch budget construction is exercised without GPU dependencies.
- Mock-provider CLI smokes verify loader/runtime/Box2D integration. Actual LoRA
  optimizer updates were not claimed as empirically validated here because this host
  run did not load a trainable CUDA model or the optional `peft` stack.
