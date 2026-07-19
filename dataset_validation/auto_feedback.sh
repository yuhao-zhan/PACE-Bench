#!/bin/bash
# Claude Code version of auto_feedback.sh
# Phase 1: Forensic Analysis
# Phase 2: Feedback Optimization (uses Phase 1 results)
# Phase 3: QA Audit

# Ctrl+C kills this script AND all child processes (claude, python, etc.)
# kill -- -$$ sends signal to the entire process group (script is group leader)
_cleanup_signal() {
    echo "" >&2
    echo "🛑 Interrupted. Killing all child processes..." >&2
    kill -- -$$ 2>/dev/null       # SIGTERM to entire process group
    sleep 1
    kill -9 -- -$$ 2>/dev/null    # SIGKILL any stragglers
    exit 130
}
trap _cleanup_signal SIGINT SIGTERM

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$REPO_ROOT/scripts/resolve_task_dirs.py"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--task <spec>] [--start_from <task_id>] | [<path>]

  --task, -t   Task spec (same as evaluation/run_evaluate_parallel.py --task):
               all | category_N | category_N_MM | CategoryN_.../S_XX | tasks/...
  --start_from Start from a task id within the resolved set (e.g. S_03, K_02).
  <path>       Legacy: tasks/Category1_Statics_Equilibrium/S_06

Examples:
  $(basename "$0") --task category_1_01
  $(basename "$0") --task category_1 --start_from S_03
  $(basename "$0") --task all
  $(basename "$0") tasks/Category1_Statics_Equilibrium/S_06
EOF
}

TASK_SPEC=""
START_FROM=""
while [ $# -gt 0 ]; do
  case "$1" in
    -t|--task)
      [ -n "${2:-}" ] || { echo "Missing value for $1" >&2; exit 1; }
      TASK_SPEC="$2"
      shift 2
      ;;
    --start_from)
      [ -n "${2:-}" ] || { echo "Missing value for $1" >&2; exit 1; }
      START_FROM="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [ -n "$TASK_SPEC" ]; then
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 1
      fi
      TASK_SPEC="$1"
      shift
      ;;
  esac
done

if [ -z "$TASK_SPEC" ]; then
  usage >&2
  exit 1
fi

TASK_DIRS=()
while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  TASK_DIRS+=("$REPO_ROOT/$rel")
done < <(cd "$REPO_ROOT" && python3 "$RESOLVER" "$TASK_SPEC") || exit 1

if [ ${#TASK_DIRS[@]} -eq 0 ]; then
  echo "No task directories resolved for: $TASK_SPEC" >&2
  exit 1
fi

if [ -n "$START_FROM" ]; then
  if ! [[ "$START_FROM" =~ ^[A-Za-z]_[0-9]{2}$ ]]; then
    echo "Invalid --start_from value: $START_FROM (expected format like S_03 or K_02)" >&2
    exit 1
  fi
  FILTERED_TASK_DIRS=()
  SEEN_START=0
  for dir in "${TASK_DIRS[@]}"; do
    task_id=$(basename "$dir")
    if [ "$SEEN_START" -eq 0 ] && [ "$task_id" = "$START_FROM" ]; then
      SEEN_START=1
    fi
    if [ "$SEEN_START" -eq 1 ]; then
      FILTERED_TASK_DIRS+=("$dir")
    fi
  done
  if [ "$SEEN_START" -eq 0 ]; then
    echo "--start_from $START_FROM was not found in resolved tasks for spec: $TASK_SPEC" >&2
    exit 1
  fi
  TASK_DIRS=("${FILTERED_TASK_DIRS[@]}")
fi

# ==========================================
# MODEL CONFIGURATION
# ==========================================
MODELS=("deepseek-v4-pro")
BLACKLISTED_MODELS=""

print_claude_failure_diagnostics() {
    local exit_code="$1"
    local model="$2"
    local prompt_bytes="$3"
    local stderr_file="$4"
    local stdout_file="$5"

    echo "  [🔍] -------- Claude Code failure diagnostics --------" >&2
    echo "  [🔍] exit_code=$exit_code model=$model prompt_bytes=$prompt_bytes" >&2
    echo "  [🔍] invocation: claude -p --model \"$model\"" >&2
    echo "  [🔍] cwd=$(pwd)" >&2

    local cbin
    cbin=$(command -v claude 2>/dev/null || true)
    if [ -n "$cbin" ]; then
        echo "  [🔍] claude binary: $cbin" >&2
    else
        echo "  [🔍] claude binary: NOT FOUND in PATH" >&2
    fi

    for var in ANTHROPIC_API_KEY; do
        eval "v=\${$var:-}"
        if [ -n "$v" ]; then
            echo "  [🔍] $var is SET (length ${#v} chars)" >&2
        else
            echo "  [🔍] $var is UNSET" >&2
        fi
    done

    local sb sse
    sb=$(wc -c < "$stdout_file" 2>/dev/null | tr -d ' ' || echo 0)
    sse=$(wc -c < "$stderr_file" 2>/dev/null | tr -d ' ' || echo 0)
    echo "  [🔍] captured stdout_bytes=$sb stderr_bytes=$sse" >&2
    echo "  [🔍] -----------------------------------------" >&2
}

summarize_claude_stderr() {
    local f="$1"
    [ -f "$f" ] || return 0
    if grep -q 'overloaded_error\|429\|CAPACITY_EXHAUSTED' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Anthropic API returned 429 — model is overloaded (transient)." >&2
        return 0
    fi
    if grep -q 'invalid_request_error\|400' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Bad request (400)." >&2
        return 0
    fi
    if grep -qE '401|UNAUTHORIZED|invalid_api_key' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Auth problem. Check ANTHROPIC_API_KEY." >&2
        return 0
    fi
}

claude_should_blacklist_model() {
    local model="$1"
    local errfile="$2"
    return 1
}

run_claude_with_fallback() {
    local PROMPT_CONTENT="$1"
    local SUCCESS=false
    local OUTPUT=""
    local CLAUDE_RUN_CWD="${CLAUDE_WORKDIR:-$REPO_ROOT}"

    for MODEL in "${MODELS[@]}"; do
        if [[ " $BLACKLISTED_MODELS " =~ " $MODEL " ]]; then
            continue
        fi

        PROMPT_BYTES=${#PROMPT_CONTENT}
        echo "  [→] Calling Claude Code with model: $MODEL (prompt ~${PROMPT_BYTES} bytes)..." >&2

        TMP_ERR=$(mktemp)
        TMP_OUT=$(mktemp)
        API_START=$(date +%s)
        (
            cd "$CLAUDE_RUN_CWD" && \
            claude -p --model "$MODEL" --dangerously-skip-permissions --effort max --system-prompt "You are a helpful assistant with access to tools for reading and modifying files. ALL edits, writes, and bash commands are pre-approved — use them freely without asking. Complete the task by actively modifying files." "$PROMPT_CONTENT"
        ) >"$TMP_OUT" 2>"$TMP_ERR"
        EXIT_CODE=$?
        API_END=$(date +%s)
        API_DURATION=$((API_END - API_START))
        OUTPUT=$(cat "$TMP_OUT")
        echo "  [→] API call finished after ${API_DURATION}s (exit code $EXIT_CODE)" >&2

        if [ $EXIT_CODE -eq 0 ]; then
            SUCCESS=true
            rm -f "$TMP_ERR" "$TMP_OUT"
            break
        else
            echo "  [⚠️] Model $MODEL failed (exit $EXIT_CODE)." >&2
            summarize_claude_stderr "$TMP_ERR"
            print_claude_failure_diagnostics "$EXIT_CODE" "$MODEL" "$PROMPT_BYTES" "$TMP_ERR" "$TMP_OUT"

            LAST_RUN_DIR="${TMPDIR:-/tmp}/auto_feedback_claude_last_run"
            mkdir -p "$LAST_RUN_DIR"
            cp -f "$TMP_ERR" "$LAST_RUN_DIR/stderr.txt"
            cp -f "$TMP_OUT" "$LAST_RUN_DIR/stdout.txt"
            echo "  [ℹ️] Full stdout/stderr saved to: $LAST_RUN_DIR/{stdout.txt,stderr.txt}" >&2

            if [ -s "$TMP_OUT" ]; then
                echo "  [ℹ️] claude stdout — first 40 lines:" >&2
                head -40 "$TMP_OUT" | sed 's/^/    | /' >&2
            fi

            rm -f "$TMP_ERR" "$TMP_OUT"
        fi
    done

    if [ "$SUCCESS" = false ]; then
        echo "" >&2
        echo "========================================================" >&2
        echo "❌ FAILED: Claude Code API call failed after exhausting all models." >&2
        echo "   Check the diagnostics above for details." >&2
        echo "========================================================" >&2
        return 1
    fi

    echo "$OUTPUT"
}

run_feedback_for_task() {
    local TASK_DIR ORIGINAL_STATE_DIR REL_PATH TASK_NAME JSON_BASE JSON_FILES
    TASK_DIR="${1%/}"
    REL_PATH=$(echo "$TASK_DIR" | sed "s|^$REPO_ROOT/tasks/||")
    TASK_NAME=$(basename "$REL_PATH")
    JSON_BASE="evaluation_results/${REL_PATH}/Qwen3-8B/baseline"

    echo "📦 Backing up initial state for revision tracking..."
    ORIGINAL_STATE_DIR=$(mktemp -d)
    cp -r "$TASK_DIR/"* "$ORIGINAL_STATE_DIR/"

# ==========================================
# PHASE 1: FORENSIC ANALYSIS
# ==========================================
echo "========================================================"
echo "🔬 PHASE 1: Forensic Analysis"
echo "========================================================"

# Build JSON file list for Phase 1
JSON_FILES=""
for i in 1 2 3 4; do
    JSON_PATH="${JSON_BASE}/all_Initial_to_Stage-${i}.json"
    if [ -f "$REPO_ROOT/$JSON_PATH" ]; then
        JSON_FILES="${JSON_FILES}${JSON_PATH} "
    fi
done

if [ -z "$JSON_FILES" ]; then
    echo "  [⚠️] No evaluation JSON files found at $JSON_BASE. Skipping forensic analysis."
    JSON_FILES="${JSON_BASE}/all_Initial_to_Stage-1.json ${JSON_BASE}/all_Initial_to_Stage-2.json ${JSON_BASE}/all_Initial_to_Stage-3.json ${JSON_BASE}/all_Initial_to_Stage-4.json"
fi

read -r -d '' PROMPT_PHASE_1 << EOP1
You are a physics simulation forensic analyst. Analyze the execution logs below to determine why an LLM agent failed to solve this task.

**Task:** ${TASK_DIR}
**Rule:** Work only in this task directory. Do not touch sibling tasks or other categories.

The agent received multiple iterations of code→simulate→feedback. Your job: identify what diagnostic information was MISSING from the feedback that, if present, would have enabled success.

## Analysis Requirements

### 1. System & API Errors
Did the agent guess hidden parameters? Misuse APIs? Hit environment limitations?

### 2. Physical Reasoning Quality
Genuine multi-step reasoning, or blind parameter tweaking? Did the agent identify root causes?

### 3. Feedback Blind Spots — Six Diagnostic Dimensions
For each dimension, cite specific iterations where missing diagnostics caused failure:

**3a. Temporal Chronology** — Were events ordered by step? Was there a failure cascade narrative, or just a flat list of broken things?

**3b. Spatial Margins** — Were positions reported with distance-to-limit? (e.g., "0.15m above fail zone", not just "y=0.65m")

**3c. Load Distribution** — Were forces/stresses ranked by severity? Were stress concentration points identified? For control tasks: where did control error diverge?

**3d. Energy Flow** — (Dynamics tasks) Were energy quantities and loss mechanisms reported? Efficiency?

**3e. Constraint Profile** — Were ALL constraints listed with PASS/FAIL + margins, not just the violated one? Was there a distinction between build-time and runtime constraints?

**3f. Numerical Health** — Were NaN, Inf, extreme velocities, or solver divergence flagged?

### 4. Failure Mechanisms
Local minima? Conflicting physical properties? Did the agent oscillate between identical failing strategies because the feedback couldn't differentiate them?

### 5. Improvement Trajectory
Did the agent genuinely learn, or was score improvement random? Cite the score trajectory across iterations.

### 6. Critical Missing Diagnostics (Most Important)
List the TOP 3-5 diagnostics that would have unlocked success. For each: what reasoning step would it enable, and how can it be computed from the existing sandbox/evaluator?

**Input files:**
$JSON_FILES
EOP1

CLAUDE_WORKDIR="$TASK_DIR"
if ! OUTPUT_PHASE1=$(run_claude_with_fallback "$PROMPT_PHASE_1"); then
    echo "❌ PHASE 1 FAILED: Forensic Analysis LLM call failed." >&2
    exit 1
fi
echo "$OUTPUT_PHASE1"
echo "========================================================"

# ==========================================
# PHASE 2: FEEDBACK OPTIMIZATION
# ==========================================
echo "========================================================"
echo "🔧 PHASE 2: Forensic Feedback Optimization"
echo "========================================================"

# Build Phase 2 prompt safely: use python3 to substitute LLM output,
# avoiding unquoted heredoc expansion of $OUTPUT_PHASE1 (which can contain
# backticks / $() / ${} that bash would try to execute).
PROMPT_P2_FILE=$(mktemp)
export PROMPT_P2_PHASE1="$OUTPUT_PHASE1"
export PROMPT_P2_TASKDIR="$TASK_DIR"
export PROMPT_P2_TASKNAME="$TASK_NAME"
cat > "$PROMPT_P2_FILE" << 'EOP2'
# Phase 2: High-Resolution Diagnostic Feedback Implementation

**Task:** TASK_DIR_PLACEHOLDER
**Rule:** Work only in this task directory. Do not touch sibling tasks or other categories.

## Step 0: Understand the Interface Contract
Before writing any code, READ \`evaluation/feedback.py\` (specifically \`format_feedback()\` and \`format_granular_feedback()\`) to understand how your task's \`feedback.py\` will be called. Your code must implement the interface that the evaluation pipeline expects.

## Forensic Analysis (from Phase 1)
PHASE1_OUTPUT_PLACEHOLDER

---

## Mission
Implement this task's \`feedback.py\` to produce **forensic-quality diagnostic reports** from simulation metrics. The output must answer, for every run: WHAT happened, WHEN, WHERE, HOW CLOSE to limits, and IN WHAT ORDER events cascaded.

## The Six Diagnostic Dimensions
Cover all dimensions applicable to this task type:

**1. Temporal Event Chronology** — Ordered failure timeline with step numbers, positions, and loads. Example: "Step 342: Joint #3 at (15.2,3.1) failed at 89% of 80N limit → Step 347: Joint #7 at (16.8,3.5) failed at 112% → Step 352: collapse."

**2. Spatial Diagnostics with Margins** — Every measurement paired with its limit and margin. "Vehicle y=2.35m, +1.85m above fail-zone (0.50m)." Never report a raw value without its limit.

**3. Load & Stress Distribution** — Rank components by stress percentage (peak/limit). Label tiers: critical (>80%), elevated (50-80%), nominal (<50%). Identify stress concentration regions.

**4. Energy & Power Flow** — For dynamics tasks: stored energy → delivered energy → losses (damping, friction). Report efficiency. Skip for non-dynamics tasks.

**5. Constraint Satisfaction Profile** — ALL constraints, not just failures. For each: PASS/FAIL, margin to limit. Flag near-limit passes (>70%). Distinguish build-time from runtime constraints.

**6. Numerical Health** — Flag NaN, Inf, velocities >100 m/s, accelerations >100g, or signs of solver divergence.

## Implementation Rules

**Primary target:** Rewrite \`feedback.py\` to produce forensic diagnostics covering the Six Dimensions.

**If critical metrics are missing from the metrics dict:** You MAY add pass-through plumbing in \`evaluator.py\` (add new keys to the return dict of \`evaluate()\`) and in \`environment.py\` (add new tracking variables / getter methods). This is STRICTLY limited to:
- Adding **new keys** to the metrics dict — never removing or renaming existing keys
- Adding **new tracking variables** (e.g., \`self._peak_stress_seen\`) — never modifying existing ones
- Adding **new getter methods** (e.g., \`get_energy_loss()\`) — never changing existing method signatures or return values
- The only purpose is to surface data that already exists in the simulation but isn't being passed through

**Absolutely forbidden in evaluator.py / environment.py (zero-tolerance):**
- Modifying any existing variable, constant, default value, or physics parameter
- Changing pass/fail logic, constraint thresholds, or success criteria
- Removing or altering any existing tracking logic
- Changing function signatures of existing methods
- **Retuning:** any change to pre-existing numeric defaults or pass/fail semantics is a hard failure

**Code quality:** 2-3 decimal places. \`math.isfinite()\` guards. \`.get(key, default)\` for missing keys. Sort by severity. Clear section headers. Lines under ~120 chars.

**Forbidden in feedback output:**
- **Spoilers:** Never "you should", "consider", "try", or imply root cause. Report: "Joint #3 failed at 89% of 80N limit" — not "Joint #3 failed because the truss lacked bracing."
- **Hardcoded thresholds:** Every limit from \`metrics.get('key', default)\` — never a literal number.
- **Hallucinated metrics:** Every reported value must exist in the metrics dict.
- **Scope creep:** Do not modify \`get_improvement_suggestions\`.

## Self-Check Before Finalizing
□ Every metric I report is tracked in \`evaluator.py\`'s return dict (or newly added by me)
□ Every limit/threshold comes from \`metrics.get(...)\`, never hardcoded
□ I never say "you should", "consider", "try", or any engineering advice
□ I report margins (distance to limit), not just raw values
□ I order events chronologically, not arbitrarily
□ I sort stress/load data by severity (worst first)
□ I handle missing keys and non-finite values gracefully
□ I use 2-3 decimal precision for all floats
□ \`get_improvement_suggestions\` is untouched
□ No existing defaults or pass/fail logic outside \`feedback.py\` were changed

## Task-Type Guidance
- **S_XX (Statics):** Temporal Chronology, Spatial Margins, Load Distribution, Constraint Profile. Key: joint failure cascade, stress ranking, beam positions vs build zones.
- **K_XX (Kinematics):** Temporal Chronology, Spatial Margins, Constraint Profile. Key: distance vs target, collapse timing, joint angle extents, motor utilization.
- **D_XX (Dynamics):** Energy Flow, Spatial Margins, Temporal Chronology. Key: energy chain (spring PE→KE), loss breakdown, trajectory margins to target zone.
- **F_XX (Granular/Fluid):** Constraint Profile, Temporal Chronology, Spatial Margins, Load Distribution. Key: leakage vs limit, containment timeline, joint breakage under surge forces.
- **C_XX (Control):** Temporal Chronology, Spatial Margins, Constraint Profile. Key: control error per zone, speed vs limits, stability margins, violation timing.
- **E_XX (Exotic):** All six dimensions — unusual physics break standard intuitions, be especially thorough.

## Execution Order
1. READ \`evaluation/feedback.py\` for the interface contract
2. READ \`environment.py\` and \`evaluator.py\` to see what is currently tracked
3. If critical diagnostics are missing from the metrics dict, ADD pass-through keys in evaluator.py (and tracking variables in environment.py if needed) — **additive only**
4. IMPLEMENT \`feedback.py\` covering all applicable Six Dimensions
5. RUN test scripts to validate
6. RERUN the complete forensic inspection on newly generated real feedback after every revision. If it finds any missing, misleading, prescriptive, leaking, malformed, or runtime-failing feedback, revise and inspect again. Stop only when a fresh complete inspection performed after the last revision finds no errors and requires no further edits; a pass that changed code cannot count as final.

## Verification
1. Run the task's test scripts (e.g., \`test_initial_on_mutated.py\`)
2. Confirm: reference solution PASSES initial env, FAILS all four mutated stages
3. Inspect output: forensic data (steps, positions, margins) populated with real values, not placeholders
4. Verify limits match mutation-specific values from \`stages.py\`
5. **Full pipeline test (MANDATORY):** Test scripts exercise limited code paths. Run the full evaluation pipeline across ALL mutation stages to catch runtime errors (TypeError, ImportError, etc.) that only surface when the framework calls stages.py:
```bash
cd TASK_DIR_PLACEHOLDER/../../../.. && for stage in Stage-1 Stage-2 Stage-3 Stage-4; do echo "=== Testing Initial -> $stage ===" && python scripts/evaluation/evaluate.py --task TASK_NAME_PLACEHOLDER --model-type mock --model-name mock --max-iterations 1 --method baseline --source-env Initial --target-env "$stage" --max-steps 500 || break; done
```
If any stage fails, trace the error to its source file and fix it. Re-run until all 4 stages pass cleanly.

**CRITICAL:** Use your tools to read the files and write the code. Do not just describe what you would do.
EOP2

# Build the final prompt with python3 (safe substitution for LLM output)
PROMPT_PHASE_2=$(python3 -c "
import os
with open('$PROMPT_P2_FILE') as f:
    c = f.read()
c = c.replace('TASK_DIR_PLACEHOLDER', os.environ['PROMPT_P2_TASKDIR'])
c = c.replace('TASK_NAME_PLACEHOLDER', os.environ['PROMPT_P2_TASKNAME'])
c = c.replace('PHASE1_OUTPUT_PLACEHOLDER', os.environ['PROMPT_P2_PHASE1'])
print(c)
")
rm -f "$PROMPT_P2_FILE"

CLAUDE_WORKDIR="$TASK_DIR"
if ! OUTPUT_PHASE2=$(run_claude_with_fallback "$PROMPT_PHASE_2"); then
    echo "❌ PHASE 2 FAILED: Feedback Optimization LLM call failed." >&2
    exit 1
fi
echo "$OUTPUT_PHASE2"
echo "========================================================"

# ==========================================
# PHASE 2.5: FEEDBACK DEBLOAT
# ==========================================
echo "========================================================"
echo "✂️  PHASE 2.5: Feedback Debloat"
echo "========================================================"

# Step 1: Run reference solution on Stage-1 and Stage-4 to collect real feedback
echo "  [→] Running reference solution on Stage-1 and Stage-4 to collect real feedback..."
for stage in Stage-1 Stage-4; do
    echo "  [→] Evaluating Initial -> $stage..."
    (cd "$REPO_ROOT" && python3 evaluation/evaluate.py --task "$TASK_NAME" \
        --model-type mock --model-name mock --max-iterations 1 --method baseline \
        --source-env Initial --target-env "$stage" --max-steps 500 2>/dev/null) || true
done

# Step 2: Extract feedback from saved evaluation reports
FB_S1=$(python3 -c "
import json, os
path = os.path.join('$REPO_ROOT', 'evaluation_results', '$REL_PATH', 'mock_mock', 'baseline_process_3', 'single', 'all_Initial_to_Stage-1.json')
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    fb = data.get('history', [{}])[0].get('feedback', '')
    print(fb[:8000])
else:
    print('(no Stage-1 results)')
" 2>/dev/null)

FB_S4=$(python3 -c "
import json, os
path = os.path.join('$REPO_ROOT', 'evaluation_results', '$REL_PATH', 'mock_mock', 'baseline_process_3', 'single', 'all_Initial_to_Stage-4.json')
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    fb = data.get('history', [{}])[0].get('feedback', '')
    print(fb[:8000])
else:
    print('(no Stage-4 results)')
" 2>/dev/null)

echo "  [→] Stage-1 feedback: ${#FB_S1} chars"
echo "  [→] Stage-4 feedback: ${#FB_S4} chars"

# Step 3: Build debloat prompt (safe substitution via python3)
DEBLOAT_PROMPT_FILE=$(mktemp)
export DEBLOAT_FB_S1="$FB_S1"
export DEBLOAT_FB_S4="$FB_S4"
export DEBLOAT_TASKDIR="$TASK_DIR"
export DEBLOAT_TASKNAME="$TASK_NAME"
export DEBLOAT_REL_PATH="$REL_PATH"

cat > "$DEBLOAT_PROMPT_FILE" << 'EODEBLOAT'
# Feedback Debloat — Remove Redundancy, Keep Diagnostic Value

**Task:** DEBLOAT_TASKDIR_PLACEHOLDER
**Rule:** Work only in this task directory. Do not touch sibling tasks or other categories.

## Background
Phase 2 rewrote `feedback.py` with 6-section forensic reports + multi-moment sampling. The output is too long — much of it is noise that obscures the signal. Your job: **read the real feedback below, identify EVERY redundancy, and simplify `feedback.py`**.

## Real Feedback Output (Stage-1, first 8KB)
```
STAGE1_FEEDBACK_PLACEHOLDER
```

## Real Feedback Output (Stage-4, first 8KB)
```
STAGE4_FEEDBACK_PLACEHOLDER
```

## Simplification — Iterate Until a Fresh Inspection Is Clean

**IMPORTANT: This prompt is used across ALL task categories (Statics S_XX, Kinematics K_XX, Dynamics D_XX, Granular/Fluid F_XX, Control C_XX, Exotic E_XX). Do NOT assume task-specific physics. Instead, READ the real feedback output above and apply these GENERAL principles.**

### Principle 1: Keep 3 Moments, Delta-Report After the First
Keep the 3-moment sampling structure. Moment 1 reports full state. Moments 2 and 3 only report **what changed** from the previous moment — new events, delta in position/energy/margins. Don't repeat unchanged sections.

### Principle 2: Eliminate Cross-Section Duplication
Scan the feedback for information that appears in MULTIPLE sections. If the same data (geometry, positions, thresholds) appears in Section 3 AND Section 4 AND Section 6, keep it ONCE — in whichever section uses it first.

### Principle 3: Collapse Low-Information Lists
If the feedback lists N items of the same type (checkpoints, constraints, joints, gates) where most or all have the SAME status and only differ by a distance/percentage, collapse them to a one-line summary. Only expand items that have a DIFFERENT or ACTIONABLE status (e.g., the one that actually failed, or the one closest to being reached).

### Principle 4: Delete Speculative Math
Remove derived/speculative values that are computed from other reported numbers rather than directly measured. If the feedback reports both "current position" AND "max theoretical range = f(v₀, λ)", keep the measured value and drop the theoretical extrapolation. The agent can do its own math.

### Principle 5: Tighten Each Section
- **Energy/power sections**: Keep total energy lost + efficiency %. Drop per-mechanism decomposition unless a single mechanism dominates (>80%).
- **Constraint sections**: Report only constraints that are NEAR-LIMIT (>50% of threshold) or FAILED. Constraints at <10% utilization add no signal.
- **Numerical health**: One line unless anomalies exist. Don't report "peak = 0" or "all values finite" per variable.
- **Spatial sections**: Report distance-to-target and distance-to-nearest-failure-boundary. Drop per-checkpoint detail for checkpoints far from current position.

### Principle 6: Don't Repeat the Obvious
If the outcome line already says "fell below y=0 at step 144", the spatial section doesn't need to re-explain that y is below 0. Report the MARGIN once, and refer to it.

## Target
Reduce total feedback length by **至少50%**. The agent needs to parse the feedback quickly and find the critical diagnostic signals. A 5000-char focused report is more useful than a 18000-char report where 70% is repetition.

## Anti-Regression (Zero-Tolerance)
- Do NOT modify `evaluator.py`, `environment.py`, `stages.py`, `prompt.py`, or `renderer.py`
- Do NOT change `get_improvement_suggestions()` — leave it as-is
- All metric keys from `evaluator.py`'s return dict must remain valid
- No hardcoded numbers in feedback output — use `metrics.get()`
- No "you should"/"consider"/"try" spoiler language
- Do NOT remove any diagnostic dimension entirely — tighten, don't amputate

## Anti-Regression (Zero-Tolerance)
- Do NOT modify `evaluator.py`, `environment.py`, `stages.py`, `prompt.py`, or `renderer.py`
- Do NOT change `get_improvement_suggestions()` — leave it as-is
- All metric keys from `evaluator.py`'s return dict must remain valid
- No hardcoded numbers in feedback output — use `metrics.get()`
- No "you should"/"consider"/"try" spoiler language

## Verification
1. READ `feedback.py` fully — understand the current structure
2. EDIT `feedback.py` — implement ALL simplification rules above
3. Run both stages to verify feedback still works:
```bash
cd DEBLOAT_TASKDIR_PLACEHOLDER/../../../.. && python3 evaluation/evaluate.py --task DEBLOAT_TASKNAME_PLACEHOLDER --model-type mock --model-name mock --max-iterations 1 --method baseline --source-env Initial --target-env Stage-1 --max-steps 500 && python3 evaluation/evaluate.py --task DEBLOAT_TASKNAME_PLACEHOLDER --model-type mock --model-name mock --max-iterations 1 --method baseline --source-env Initial --target-env Stage-4 --max-steps 500
```
4. Inspect the new feedback output — is it significantly shorter? Are the key diagnostics still present?
5. Check the saved JSON — no KeyError, no ImportError
6. Rerun the complete feedback inspection on the newly generated output. If any redundancy, missing diagnostic, prescriptive language, value leak, malformed output, or runtime error remains, revise feedback.py and repeat Steps 3-6. Stop only when a fresh inspection after the last edit finds no errors and requires no further changes.
EODEBLOAT

# Substitute placeholders
DEBLOAT_PROMPT=$(python3 -c "
import os
with open('$DEBLOAT_PROMPT_FILE') as f:
    c = f.read()
c = c.replace('DEBLOAT_TASKDIR_PLACEHOLDER', os.environ['DEBLOAT_TASKDIR'])
c = c.replace('DEBLOAT_TASKNAME_PLACEHOLDER', os.environ['DEBLOAT_TASKNAME'])
c = c.replace('STAGE1_FEEDBACK_PLACEHOLDER', os.environ['DEBLOAT_FB_S1'])
c = c.replace('STAGE4_FEEDBACK_PLACEHOLDER', os.environ['DEBLOAT_FB_S4'])
print(c)
")
rm -f "$DEBLOAT_PROMPT_FILE"

# Step 4: Send to LLM
CLAUDE_WORKDIR="$TASK_DIR"
if ! OUTPUT_DEBLOAT=$(run_claude_with_fallback "$DEBLOAT_PROMPT"); then
    echo "❌ PHASE 2.5 FAILED: Feedback Debloat LLM call failed." >&2
    exit 1
fi
echo "$OUTPUT_DEBLOAT"
echo "========================================================"


# ==========================================
# GENERATE LOG / DIFF
# ==========================================
echo "========================================================"
echo "📝 Generating revision patch log..."

LOG_DIR="tasks/auto_audit_log/$REL_PATH"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/feedback.patch"

diff -ruN -x "__pycache__" "$ORIGINAL_STATE_DIR" "$TASK_DIR" > "$LOG_FILE"

if [ -s "$LOG_FILE" ]; then
    echo "✅ Success: Feedback diff saved to $LOG_FILE"
else
    echo "ℹ️ No changes were made to the files during this process."
    rm -f "$LOG_FILE"
fi

rm -rf "$ORIGINAL_STATE_DIR"

	# Generate HANDOFF.md for cross-session continuity
	HANDOFF_FILE="$LOG_DIR/HANDOFF.md"
	cat > "$HANDOFF_FILE" << EOF
# Feedback Handoff: $(basename "$TASK_DIR")
## Timestamp: $(date '+%Y-%m-%d %H:%M:%S %z')
## Task: $TASK_DIR
## Spec: $TASK_SPEC
## Status: Feedback optimization completed

## Log Files
- Feedback patch: feedback.patch
EOF

echo "📋 Handoff file generated: $HANDOFF_FILE"
echo "========================================================"
}

# ==========================================
# ARCHIVE & PRIORITY SYSTEM
# ==========================================
ARCHIVE_FILE="$REPO_ROOT/tasks/archive.json"

rank_tasks_by_4b_failure() {
    python3 -c "
import os, json, sys
task_dirs = sys.argv[1:]
results_root = os.path.join('$REPO_ROOT', 'evaluation_results')
expected_targets = ['Stage-1', 'Stage-2', 'Stage-3', 'Stage-4']
scores = []
for task_dir in task_dirs:
    category = os.path.basename(os.path.dirname(task_dir))
    task_name = os.path.basename(task_dir)
    eval_dir = os.path.join(results_root, category, task_name, 'Qwen3-4B', 'baseline_process_3')
    fail_count = 0
    for target in expected_targets:
        filename = f'all_Initial_to_{target}.json'
        any_success = False
        if os.path.isdir(eval_dir):
            for turn_dir in sorted(os.listdir(eval_dir)):
                fp = os.path.join(eval_dir, turn_dir, filename)
                if os.path.isfile(fp):
                    try:
                        with open(fp) as f:
                            if json.load(f).get('success') is True:
                                any_success = True
                                break
                    except: pass
        if not any_success:
            fail_count += 1
    scores.append((fail_count, task_dir))
scores.sort(key=lambda x: -x[0])
for count, td in scores:
    print(f'{count}|{td}')
" "${TASK_DIRS[@]}"
}

is_task_archived() {
    local task_rel="$1"
    local key="$2"
    python3 -c "
import json, sys
try:
    with open('$ARCHIVE_FILE') as f:
        data = json.load(f)
except: sys.exit(1)
sys.exit(0 if data.get('$key', {}).get('$task_rel') else 1)
" 2>/dev/null
}

mark_task_archived() {
    local task_rel="$1"
    local key="$2"
    python3 -c "
import json, os
from datetime import datetime
archive = {}
if os.path.exists('$ARCHIVE_FILE'):
    try:
        with open('$ARCHIVE_FILE') as f:
            archive = json.load(f)
    except: pass
archive.setdefault('$key', {})['$task_rel'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
os.makedirs(os.path.dirname('$ARCHIVE_FILE'), exist_ok=True)
with open('$ARCHIVE_FILE', 'w') as f:
    json.dump(archive, f, indent=2)
"
}

# Build priority-sorted task list, skipping already-archived tasks
echo "========================================================"
echo "📊 Computing task priority (4B-failure pairs first)..."
PRIORITY_LINES=$(rank_tasks_by_4b_failure)
PRIORITY_TASK_DIRS=()
SKIPPED_COUNT=0
ALL_ARCHIVED=true
while IFS='|' read -r fail_count td; do
    [ -z "$td" ] && continue
    task_name=$(basename "$td")
    category=$(basename "$(dirname "$td")")
    task_rel="${category}/${task_name}"
    # Priority label
    if [ "$fail_count" -eq 4 ]; then
        echo "  [PRIORITY 1 — 4B fails ALL 4] $task_rel"
    elif [ "$fail_count" -gt 0 ]; then
        echo "  [PRIORITY 2 — 4B fails ${fail_count}/4] $task_rel"
    else
        echo "  [PRIORITY 3 — 4B passes all] $task_rel"
    fi
    if is_task_archived "$task_rel" "feedback"; then
        echo "    ⏭️  Already archived — skipping."
        SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
        continue
    fi
    ALL_ARCHIVED=false
    PRIORITY_TASK_DIRS+=("$td")
done <<< "$PRIORITY_LINES"

echo "  Total: ${#PRIORITY_TASK_DIRS[@]} to process, $SKIPPED_COUNT skipped."
echo "========================================================"

if [ "$ALL_ARCHIVED" = true ]; then
    echo "✅ All 4B-failure tasks have been processed. Nothing to do."
    exit 0
fi

for TASK_DIR in "${PRIORITY_TASK_DIRS[@]}"; do
    task_name=$(basename "$TASK_DIR")
    category=$(basename "$(dirname "$TASK_DIR")")
    task_rel="${category}/${task_name}"
    echo "========================================================"
    echo "▶ Auto-feedback task: $TASK_DIR  (spec: $TASK_SPEC)"
    echo "========================================================"
    run_feedback_for_task "$TASK_DIR" || exit 1
    mark_task_archived "$task_rel" "feedback"
    echo "📝 Archived: $task_rel → archive.json [feedback]"
done
