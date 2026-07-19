#!/bin/bash
# Claude Code version of auto_difficulty_escalation.sh
# Escalate task difficulty until Qwen3-4B can no longer pass the task pair.
# to kill the process: `pkill -9 -f "/bin/bash ./auto_difficulty_escalation.sh --task all"`

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$REPO_ROOT/scripts/resolve_task_dirs.py"

# ==========================================
# CONFIGURATION
# ==========================================
MODELS=("deepseek-v4-pro")
BLACKLISTED_MODELS=""

# Maximum escalation rounds per pair before giving up
MAX_ROUNDS=3

# Qwen3-4B evaluation settings
Qwen3_4B_MODEL_NAME="${Qwen3_4B_MODEL_NAME:-/home/test/testdata/models/Qwen3-4B}"
# API_BASE and CUDA_VISIBLE_DEVICES are auto-selected by select_least_loaded_gpu()
Qwen3_4B_API_BASE="${Qwen3_4B_API_BASE:-}"  # auto-detected if empty
Qwen3_4B_API_PARALLEL="${Qwen3_4B_API_PARALLEL:-1}"
Qwen3_4B_MAX_ITERATIONS="${Qwen3_4B_MAX_ITERATIONS:-20}"
Qwen3_4B_NUM_TRIALS="${Qwen3_4B_NUM_TRIALS:-3}"

# GPU pool: "gpu_id:port" pairs to load-balance across
Qwen3_4B_GPU_POOL="${Qwen3_4B_GPU_POOL:-5:2205,6:2206,7:2207}"

# SSH target for evaluation (vllm server host). Empty = run locally.
EVAL_SSH_HOST="${EVAL_SSH_HOST:-}"

# Python binary to use on the evaluation host (may need conda env path)
EVAL_PYTHON="${EVAL_PYTHON:-/home/test/test1709/miniconda3/bin/python3}"

# Target stage filter (empty = all stages). Example: "Stage-1"
TARGET_STAGE="${TARGET_STAGE:-}"

DRY_RUN=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--task <spec>] [--start_from <task_id>] [--max-rounds <n>] [--target-stage <stage>] [--dry-run]

  --task, -t        Task spec (same as evaluation/run_evaluate_parallel.py --task):
                    all | category_N | category_N_MM | CategoryN_.../S_XX | tasks/...
  --start_from      Start from a task id within the resolved set (e.g. S_03, K_02).
  --max-rounds      Max escalation rounds per pair (default: $MAX_ROUNDS).
  --target-stage    Only escalate a specific stage (Stage-1, Stage-2, Stage-3, Stage-4).
  --dry-run         Print what WOULD be escalated without making changes.

Examples:
  $(basename "$0") --task category_1_01
  $(basename "$0") --task category_1 --start_from S_03
  $(basename "$0") --task all --max-rounds 5
  $(basename "$0") --task category_1_01 --target-stage Stage-2 --dry-run
EOF
}

# ==========================================
# ARGUMENT PARSING
# ==========================================
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
    --max-rounds)
      [ -n "${2:-}" ] || { echo "Missing value for $1" >&2; exit 1; }
      MAX_ROUNDS="$2"
      shift 2
      ;;
    --target-stage)
      [ -n "${2:-}" ] || { echo "Missing value for $1" >&2; exit 1; }
      TARGET_STAGE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

# ==========================================
# TASK RESOLUTION
# ==========================================
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
# CLAUDE CODE HELPERS
# ==========================================
print_claude_failure_diagnostics() {
    local exit_code="$1"
    local model="$2"
    local prompt_bytes="$3"
    local stderr_file="$4"
    local stdout_file="$5"

    echo "  [🔍] -------- Claude Code failure diagnostics --------" >&2
    echo "  [🔍] exit_code=$exit_code model=$model prompt_bytes=$prompt_bytes" >&2
    echo "  [🔍] invocation: claude -p --model \"$model\" -p \"<prompt ${prompt_bytes} bytes>\"" >&2
    echo "  [🔍] cwd=$(pwd)" >&2
    echo "  [🔍] shell: $BASH_VERSION" >&2

    local cbin
    cbin=$(command -v claude 2>/dev/null || true)
    if [ -n "$cbin" ]; then
        echo "  [🔍] claude binary: $cbin" >&2
        _cv=$(timeout 8 claude -v 2>&1 | tr '\n' ' ' || true)
        echo "  [🔍] claude -v: ${_cv:-<failed>}" >&2
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

    for p in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY NO_PROXY no_proxy; do
        eval "pv=\${$p:-}"
        if [ -n "$pv" ]; then
            echo "  [🔍] $p is set (length ${#pv})" >&2
        fi
    done

    local sb sse
    sb=$(wc -c < "$stdout_file" 2>/dev/null | tr -d ' ' || echo 0)
    sse=$(wc -c < "$stderr_file" 2>/dev/null | tr -d ' ' || echo 0)
    echo "  [🔍] captured stdout_bytes=$sb stderr_bytes=$sse" >&2

    if command -v curl >/dev/null 2>&1; then
        _curl_out=$(curl -sS -m 6 -o /dev/null -w "%{http_code}" "https://www.google.com" 2>&1) || _curl_out="curl_error:${_curl_out}"
        echo "  [🔍] connectivity: https://www.google.com -> ${_curl_out}" >&2
    else
        echo "  [🔍] connectivity: (curl not installed; skipped)" >&2
    fi

    if [ "${AUTO_ESCALATE_VERBOSE:-0}" = "1" ]; then
        echo "  [🔍] AUTO_ESCALATE_VERBOSE=1: env names containing ANTHROPIC/PROXY (values hidden):" >&2
        env | grep -iE '^(ANTHROPIC|HTTP_|HTTPS_|ALL_|NO_)' | while IFS= read -r line; do
            name="${line%%=*}"
            echo "  [🔍]   ${name}=<hidden>" >&2
        done || true
    fi
    echo "  [🔍] Tip: AUTO_ESCALATE_VERBOSE=1 ./auto_difficulty_escalation.sh ... for extra env listing" >&2
    echo "  [🔍] -----------------------------------------" >&2
}

summarize_claude_stderr() {
    local f="$1"
    [ -f "$f" ] || return 0
    if grep -q 'overloaded_error\|429\|CAPACITY_EXHAUSTED' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Anthropic API returned 429 — model is overloaded (transient). Retry later or try next model in fallback list." >&2
        return 0
    fi
    if grep -q 'invalid_request_error\|400' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Bad request (400). Check API key and request format." >&2
        return 0
    fi
    if grep -qE '401|UNAUTHORIZED|invalid_api_key' "$f" 2>/dev/null; then
        echo "  [📌] Plain summary: Auth problem. Check ANTHROPIC_API_KEY." >&2
        return 0
    fi
}

claude_stderr_is_transient() {
    local f="$1"
    [ -f "$f" ] || return 1
    grep -qE 'overloaded_error|429|CAPACITY_EXHAUSTED' "$f" 2>/dev/null
}

claude_should_blacklist_model() {
    local model="$1"
    local errfile="$2"
    if claude_stderr_is_transient "$errfile"; then
        return 1
    fi
    return 0
}

run_claude_with_fallback() {
    local PROMPT_CONTENT="$1"
    local CLAUDE_RUN_CWD="${2:-$REPO_ROOT}"
    local SUCCESS=false
    local OUTPUT=""

    for MODEL in "${MODELS[@]}"; do
        if [[ " $BLACKLISTED_MODELS " =~ " $MODEL " ]]; then
            continue
        fi

        PROMPT_BYTES=${#PROMPT_CONTENT}
        echo "  [→] Calling Claude Code with model: $MODEL (prompt ~${PROMPT_BYTES} bytes)..." >&2

        TMP_OUT=$(mktemp)
        API_START=$(date +%s)
        # Merge stdout+stderr, stream both to terminal in real-time,
        # while capturing everything to TMP_OUT for diagnostics on failure.
        (
            cd "$CLAUDE_RUN_CWD" && \
            claude -p --model "$MODEL" --dangerously-skip-permissions --effort max --system-prompt "You are a helpful assistant with access to tools for reading and modifying files. ALL edits, writes, and bash commands are pre-approved — use them freely without asking. Complete the task by actively modifying files." "$PROMPT_CONTENT"
        ) 2>&1 | tee "$TMP_OUT"
        EXIT_CODE=${PIPESTATUS[0]}
        API_END=$(date +%s)
        API_DURATION=$((API_END - API_START))
        OUTPUT=$(cat "$TMP_OUT")
        echo "  [→] API call finished after ${API_DURATION}s (exit code $EXIT_CODE) at $(date '+%H:%M:%S')" >&2

        if [ $EXIT_CODE -eq 0 ]; then
            SUCCESS=true
            rm -f "$TMP_OUT"
            break
        else
            echo "  [⚠️] Model $MODEL failed (exit $EXIT_CODE)." >&2
            summarize_claude_stderr "$TMP_OUT"
            print_claude_failure_diagnostics "$EXIT_CODE" "$MODEL" "$PROMPT_BYTES" "$TMP_OUT" "$TMP_OUT"

            LAST_RUN_DIR="${TMPDIR:-/tmp}/auto_escalate_claude_last_run"
            mkdir -p "$LAST_RUN_DIR"
            cp -f "$TMP_OUT" "$LAST_RUN_DIR/output.txt"
            echo "  [ℹ️] Full output saved to: $LAST_RUN_DIR/output.txt" >&2

            if [ -s "$TMP_OUT" ]; then
                echo "  [ℹ️] claude output — first 60 lines:" >&2
                OUT_LINES=$(wc -l < "$TMP_OUT")
                if [ "$OUT_LINES" -le 60 ]; then
                    sed 's/^/    | /' "$TMP_OUT" >&2
                else
                    sed -n '1,35p' "$TMP_OUT" | sed 's/^/    | /' >&2
                    echo "    | ... ($OUT_LINES lines total, truncated) ..." >&2
                    tail -n 25 "$TMP_OUT" | sed 's/^/    | /' >&2
                fi
            else
                echo "  [ℹ️] claude output: (empty)" >&2
            fi

            if claude_should_blacklist_model "$MODEL" "$TMP_OUT"; then
                echo "  [🚫] Adding $MODEL to blacklist (skipped for the rest of this script run)." >&2
                BLACKLISTED_MODELS="$BLACKLISTED_MODELS $MODEL "
            else
                echo "  [ℹ️] Not blacklisting $MODEL — transient error; explicit models still apply on next try." >&2
            fi
            rm -f "$TMP_OUT"
        fi
    done

    if [ "$SUCCESS" = false ]; then
        echo "  [❌] FATAL ERROR: All models failed. Stopping loop." >&2
        exit 1
    fi

    echo "$OUTPUT"
}

# ==========================================
# 4B SUCCESS PAIR DETECTION
# ==========================================
# Usage: find_4b_success_pairs <task_dir>
# Output: one line per pair: "source|target"
# A pair requires escalation if:
#   - ANY turn has success=true (4B can still pass), OR
#   - result file is MISSING from ALL 3 turns (not yet evaluated)
find_4b_success_pairs() {
    local TASK_DIR="$1"
    local TASK_NAME
    TASK_NAME=$(basename "$TASK_DIR")
    local CATEGORY
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")

    python3 -c "
import os, json, re

task_dir = '$TASK_DIR'
category = '$CATEGORY'
task_name = '$TASK_NAME'
scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname(task_dir)))
results_root = os.path.join(scripts_dir, 'evaluation_results')
rel_path = os.path.join(category, task_name)
eval_dir = os.path.join(results_root, rel_path, 'Qwen3-4B', 'baseline_process_3')

expected_targets = ['Stage-1', 'Stage-2', 'Stage-3', 'Stage-4']
turn_names = ['1', '2', '3']
pattern = re.compile(r'^all_(.+)_to_(.+)\.json$')

# pair_turns: (source, target) -> {turn_name: success_bool}
pair_turns = {}

if os.path.isdir(eval_dir):
    for turn_dir in turn_names:
        turn_path = os.path.join(eval_dir, turn_dir)
        if not os.path.isdir(turn_path):
            continue
        for fn in os.listdir(turn_path):
            m = pattern.match(fn)
            if not m:
                continue
            source, target = m.group(1), m.group(2)
            pair_key = (source, target)
            if pair_key not in pair_turns:
                pair_turns[pair_key] = {}
            filepath = os.path.join(turn_path, fn)
            try:
                with open(filepath) as f:
                    data = json.load(f)
                pair_turns[pair_key][turn_dir] = data.get('success', False)
            except Exception:
                pass

# Collect all unique source envs from discovered pairs
all_sources = set()
for (src, tgt) in pair_turns:
    all_sources.add(src)

# Fill in completely missing pairs (no result files at all in any turn)
for source in all_sources:
    for target in expected_targets:
        pair_key = (source, target)
        if pair_key not in pair_turns:
            pair_turns[pair_key] = {}

# If no results exist at all (eval_dir missing or empty), assume 4B can pass
# ALL pairs and escalate everything.
if not pair_turns:
    for target in expected_targets:
        print(f'Initial|{target}')
else:
    # Report pairs that need escalation:
    #   - missing from all turns, OR
    #   - any existing turn has success=true
    for (source, target) in sorted(pair_turns.keys()):
        turns = pair_turns[(source, target)]
        if not turns:
            # No result files at all → needs evaluation + possible escalation
            print(f'{source}|{target}')
        elif any(v is True for v in turns.values()):
            # 4B passed in at least one turn → needs escalation
            print(f'{source}|{target}')
"
}

# Check if a specific pair still has 4B success after re-evaluation
# Usage: check_pair_still_success <task_dir> <source> <target>
# Returns 0 (true/success) if ANY turn has success=true, 1 (false) if all fail
check_pair_still_success() {
    local TASK_DIR="$1"
    local SOURCE="$2"
    local TARGET="$3"
    local TASK_NAME CATEGORY
    TASK_NAME=$(basename "$TASK_DIR")
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")

    python3 -c "
import os, json

category = '$CATEGORY'
task_name = '$TASK_NAME'
source = '$SOURCE'
target = '$TARGET'
scripts_dir = os.path.dirname(os.path.dirname(os.path.dirname('$TASK_DIR')))
results_root = os.path.join(scripts_dir, 'evaluation_results')
rel_path = os.path.join(category, task_name)
eval_dir = os.path.join(results_root, rel_path, 'Qwen3-4B', 'baseline_process_3')

if not os.path.isdir(eval_dir):
    print('NO_RESULTS')
    exit(1)

filename = f'all_{source}_to_{target}.json'
any_success = False
turns_found = 0

for turn_dir in sorted(os.listdir(eval_dir)):
    turn_path = os.path.join(eval_dir, turn_dir)
    if not os.path.isdir(turn_path):
        continue
    filepath = os.path.join(turn_path, filename)
    if not os.path.isfile(filepath):
        continue
    turns_found += 1
    try:
        with open(filepath) as f:
            data = json.load(f)
        if data.get('success') is True:
            any_success = True
            print(f'turn_{turn_dir}: success=True')
        else:
            print(f'turn_{turn_dir}: success=False')
    except Exception as e:
        print(f'turn_{turn_dir}: error={e}')

if turns_found == 0:
    print('NO_RESULTS_FOUND')
    exit(2)

if any_success:
    print('OVERALL: STILL_SUCCESS')
    exit(0)
else:
    print('OVERALL: ESCALATION_SUCCESSFUL')
    exit(1)
"
}

# Delete evaluation results for a specific pair
# Usage: delete_pair_results <task_dir> <source> <target>
delete_pair_results() {
    local TASK_DIR="$1"
    local SOURCE="$2"
    local TARGET="$3"
    local TASK_NAME CATEGORY
    TASK_NAME=$(basename "$TASK_DIR")
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")

    local RESULTS_DIR="$REPO_ROOT/evaluation_results/$CATEGORY/$TASK_NAME/Qwen3-4B/baseline_process_3"
    local FILENAME="all_${SOURCE}_to_${TARGET}.json"

    if [ ! -d "$RESULTS_DIR" ]; then
        echo "  [ℹ️] No results directory at $RESULTS_DIR"
        return 0
    fi

    local deleted=0
    for turn_dir in "$RESULTS_DIR"/*/; do
        [ -d "$turn_dir" ] || continue
        local f="$turn_dir/$FILENAME"
        if [ -f "$f" ]; then
            echo "  [🗑️] Deleting: $f"
            rm -f "$f"
            deleted=$((deleted + 1))
        fi
    done

    if [ "$deleted" -gt 0 ]; then
        echo "  [✅] Deleted $deleted result file(s) for $SOURCE -> $TARGET"
    else
        echo "  [ℹ️] No result files found to delete for $SOURCE -> $TARGET"
    fi
}

# ==========================================
# GPU LOAD-BALANCING
# ==========================================
# Lock directory for GPU mutex (prevents duplicate requests on same GPU)
GPU_LOCK_DIR="${TMPDIR:-/tmp}/auto_escalate_gpu_locks"
mkdir -p "$GPU_LOCK_DIR" 2>/dev/null

# Acquire an exclusive lock on a GPU (mkdir is atomic).
# Usage: acquire_gpu_lock <gpu_id> && echo "locked"
acquire_gpu_lock() {
    local gpu_id="$1"
    local lock_dir="$GPU_LOCK_DIR/gpu_${gpu_id}"
    mkdir "$lock_dir" 2>/dev/null
}

# Release a previously acquired GPU lock.
release_gpu_lock() {
    local gpu_id="$1"
    [ -n "$gpu_id" ] || return 0
    rmdir "$GPU_LOCK_DIR/gpu_${gpu_id}" 2>/dev/null
}

# Query nvidia-smi for GPU utilization on the configured pool,
# then select the least-loaded GPU that we can acquire an exclusive lock on.
# Output: "GPU_ID PORT" (space-separated). Lock is held on return.
# Caller MUST call release_gpu_lock $GPU_ID after evaluation.
select_least_loaded_gpu() {
    # Parse GPU pool: "5:2205,6:2206,7:2207"
    local gpu_entries
    IFS=',' read -ra gpu_entries <<< "$Qwen3_4B_GPU_POOL"

    # Build sorted list of GPUs by utilization (lowest first)
    local -a gpu_list=()

    for entry in "${gpu_entries[@]}"; do
        local gpu_id="${entry%%:*}"
        local port="${entry##*:}"

        # Quick check: is vllm reachable on this port?
        if ! curl -s -m 2 "http://127.0.0.1:${port}/v1/models" >/dev/null 2>&1; then
            echo "  [🔍] GPU $gpu_id (port $port): vllm not reachable, skipping" >&2
            continue
        fi

        # Get GPU utilization from nvidia-smi
        local util
        util=$(nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader 2>/dev/null \
               | grep "^${gpu_id}," | cut -d',' -f2 | tr -d ' %' || echo "")
        if [ -z "$util" ]; then
            util=0
        fi

        echo "  [🔍] GPU $gpu_id (port $port): ${util}% util" >&2
        gpu_list+=("$util:$gpu_id:$port")
    done

    if [ ${#gpu_list[@]} -eq 0 ]; then
        echo "  [❌] No reachable GPU/vllm found in pool: $Qwen3_4B_GPU_POOL" >&2
        return 1
    fi

    # Sort by utilization (lowest first)
    local sorted
    sorted=$(printf '%s\n' "${gpu_list[@]}" | sort -t: -k1 -n)

    # Try each GPU in order of utilization until we get a lock
    while IFS=: read -r util gpu_id port; do
        if acquire_gpu_lock "$gpu_id"; then
            echo "  [🔒] Acquired lock on GPU $gpu_id (port $port) — ${util}% util" >&2
            echo "$gpu_id $port"
            return 0
        fi
        echo "  [🔒] GPU $gpu_id is locked by another process, trying next..." >&2
    done <<< "$sorted"

    echo "  [❌] All GPUs in pool are locked by other processes. Try again later." >&2
    return 1
}

# ==========================================
# EVALUATION RUNNER
# ==========================================
# Run Qwen3-4B evaluation for a specific pair.
# Launches 3 turns in PARALLEL. If any turn finishes first with success=true,
# immediately kills the other turns (early termination).
# Usage: run_qwen3_4b_evaluation <task_dir> <source> <target>
# Returns: 0 if all turns fail (escalation worked), 1 if any turn succeeds
run_qwen3_4b_evaluation() {
    local TASK_DIR="$1"
    local SOURCE="$2"
    local TARGET="$3"
    local TASK_NAME CATEGORY
    TASK_NAME=$(basename "$TASK_DIR")
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")
    # evaluate.py now accepts bare task IDs (S_01, K_03, ...) — no conversion needed
    local TASK_SPEC="$TASK_NAME"
    local PAIR_LABEL="${SOURCE}_to_${TARGET}"

    echo "  [🚀] Running Qwen3-4B evaluation for: $TASK_SPEC :: $PAIR_LABEL"
    echo "  [🚀] Model: $Qwen3_4B_MODEL_NAME, ${Qwen3_4B_NUM_TRIALS} turns in PARALLEL"

    # Auto-select least loaded GPU if API_BASE not explicitly set.
    # Each turn independently picks its own GPU (with lock) to spread load.
    local EVAL_GPU_POOL_USED=""
    if [ -n "${Qwen3_4B_API_BASE:-}" ]; then
        EVAL_GPU_POOL_USED="manual"
    fi

    # Clean stale GPU locks from previous crashed runs
    for _d in "$GPU_LOCK_DIR"/gpu_*; do
        [ -d "$_d" ] && rmdir "$_d" 2>/dev/null && echo "  [🧹] Cleaned stale lock: $(basename $_d)"
    done

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "  [🔍] DRY RUN: Would launch 3 parallel evaluation processes (each on its own GPU)."
        return 0
    fi

    # Launch 3 turns in parallel — each turn picks its own GPU
    local TURN_PIDS=()
    local TURN_GPUS=()

    local RESULT_DIR="$REPO_ROOT/evaluation_results/$CATEGORY/$TASK_NAME/Qwen3-4B/baseline_process_3"

    for turn in $(seq 1 $Qwen3_4B_NUM_TRIALS); do
        local TURN_DIR="$RESULT_DIR/$turn"
        mkdir -p "$TURN_DIR"

        (
            # Each turn independently selects + locks its own GPU
            if [ -n "${Qwen3_4B_API_BASE:-}" ]; then
                MY_API_BASE="$Qwen3_4B_API_BASE"
                MY_GPU="${Qwen3_4B_GPU:-7}"
            else
                MY_GPU="" MY_PORT=""
                IFS=',' read -ra _entries <<< "$Qwen3_4B_GPU_POOL"
                _gpu_list=()
                for _entry in "${_entries[@]}"; do
                    _gpu="${_entry%%:*}" _port="${_entry##*:}"
                    curl -s -m 2 "http://127.0.0.1:${_port}/v1/models" >/dev/null 2>&1 || continue
                    _util=$(nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader 2>/dev/null | grep "^${_gpu}," | cut -d',' -f2 | tr -d ' %' || echo "0")
                    [ -z "$_util" ] && _util=0
                    _gpu_list+=("${_util}:${_gpu}:${_port}")
                done
                if [ ${#_gpu_list[@]} -eq 0 ]; then
                    echo "[T$turn] ❌ No reachable GPU" >&2; exit 1
                fi
                _sorted=$(printf '%s\n' "${_gpu_list[@]}" | sort -t: -k1 -n)
                while IFS=: read -r _util _gpu _port; do
                    if mkdir "$GPU_LOCK_DIR/gpu_${_gpu}" 2>/dev/null; then
                        MY_GPU="$_gpu" MY_PORT="$_port"
                        echo "[T$turn] 🔒 GPU $_gpu (port $_port, ${_util}%)" >&2
                        break
                    fi
                done <<< "$_sorted"
                if [ -z "$MY_GPU" ]; then
                    echo "[T$turn] ❌ All GPUs locked" >&2; exit 1
                fi
                MY_API_BASE="http://127.0.0.1:${MY_PORT}/v1"
            fi

            trap "rmdir '$GPU_LOCK_DIR/gpu_${MY_GPU}' 2>/dev/null" EXIT

            cd "$REPO_ROOT" && \
            export API_BASE="$MY_API_BASE" && \
            export CUDA_VISIBLE_DEVICES=$MY_GPU && \
            $EVAL_PYTHON evaluation/evaluate.py \
              --task "$TASK_SPEC" \
              --model-type openai \
              --model-name "$Qwen3_4B_MODEL_NAME" \
              --max-iterations $Qwen3_4B_MAX_ITERATIONS \
              --method baseline \
              --context all \
              --granularity process_3 \
              --source-env "$SOURCE" \
              --target-env "$TARGET" \
              --turn "$turn" \
              --max-steps 500 \
              --no-skip-complete 2>&1 | sed "s/^/[T$turn] /"
        ) &
        TURN_PIDS+=($!)
        echo "  [▶] Turn $turn started (PID ${TURN_PIDS[-1]})"
    done

    # Monitor: poll for completion. If any turn succeeds, kill the rest.
    local ANY_SUCCESS=0
    local DONE_COUNT=0
    local DECLARED=0

    while [ $DONE_COUNT -lt $Qwen3_4B_NUM_TRIALS ]; do
        sleep 5  # poll interval

        # Check each running turn
        for i in "${!TURN_PIDS[@]}"; do
            local pid="${TURN_PIDS[$i]}"
            local turn=$((i + 1))
            [ "$pid" = "DONE" ] && continue

            # Check if process still alive
            local pid_alive=0
            if kill -0 "$pid" 2>/dev/null; then
                pid_alive=1
            fi

            # Check result file regardless of whether process is alive
            # (result is written just before exit; we must not miss it)
            local RESULT_FILE="$RESULT_DIR/$turn/all_${SOURCE}_to_${TARGET}.json"
            local success="False"
            if [ -f "$RESULT_FILE" ]; then
                success=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d.get('success', False))" 2>/dev/null || echo "False")
            fi

            # If process exited, mark it done
            if [ "$pid_alive" -eq 0 ]; then
                TURN_PIDS[$i]="DONE"
                DONE_COUNT=$((DONE_COUNT + 1))
                echo "  [✓] Turn $turn finished (PID $pid) — success=$success"
            fi

            # Early termination: if ANY turn succeeded, kill the rest immediately
            if [ "$success" = "True" ] && [ "$DECLARED" -eq 0 ]; then
                DECLARED=1
                ANY_SUCCESS=1
                echo "  [🏁] Turn $turn SUCCEEDED — killing other turns immediately!"
                for j in "${!TURN_PIDS[@]}"; do
                    local other_pid="${TURN_PIDS[$j]}"
                    [ "$other_pid" = "DONE" ] && continue
                    [ "$other_pid" = "$pid" ] && continue
                    kill "$other_pid" 2>/dev/null && echo "  [✗] Killed turn $((j + 1)) (PID $other_pid)"
                    TURN_PIDS[$j]="DONE"
                done
                break 2  # exit both loops
            fi
        done
    done

    # Cleanup: kill any stragglers (SIGTERM so trap EXIT releases GPU locks)
    for pid in "${TURN_PIDS[@]}"; do
        [ "$pid" = "DONE" ] && continue
        kill "$pid" 2>/dev/null
    done
    sleep 1  # give traps time to fire

    # Print turn summaries and determine final outcome from result FILES
    # (not just the monitoring loop — turns can finish between poll cycles)
    echo "  [📊] Turn results:"
    local RESULTS_FOUND=0
    local ANY_SUCCESS_FROM_FILES=0
    for turn in $(seq 1 $Qwen3_4B_NUM_TRIALS); do
        local RESULT_FILE="$RESULT_DIR/$turn/all_${SOURCE}_to_${TARGET}.json"
        if [ -f "$RESULT_FILE" ]; then
            RESULTS_FOUND=$((RESULTS_FOUND + 1))
            local success score
            success=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d.get('success', False))" 2>/dev/null || echo "N/A")
            score=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d.get('best_score', 'N/A'))" 2>/dev/null || echo "N/A")
            echo "    Turn $turn: success=$success, best_score=$score"
            if [ "$success" = "True" ]; then
                ANY_SUCCESS_FROM_FILES=1
            fi
        else
            echo "    Turn $turn: no result file (crashed / GPU lock failed / killed early)"
        fi
    done

    if [ "$RESULTS_FOUND" -eq 0 ]; then
        echo "  [❌] No turn produced a result file — evaluation did not run."
        return 2
    fi

    if [ "$ANY_SUCCESS_FROM_FILES" -eq 1 ]; then
        echo "  [⚠️] Qwen3-4B PASSED — needs more escalation."
        return 1
    fi

    echo "  [✅] All ${RESULTS_FOUND} turns failed — escalation successful."
    return 0
}

# ==========================================
# ESCALATION PROMPT BUILDER
# ==========================================
build_escalation_prompt() {
    local TASK_DIR="$1"
    local TARGET_STAGE_ID="$2"
    local ROUND="$3"
    local TASK_NAME CATEGORY TASK_ID
    TASK_NAME=$(basename "$TASK_DIR")
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")
    TASK_ID="${CATEGORY}/${TASK_NAME}"

    cat <<-ENDPROMPT
# Difficulty Escalation for Mutated Task Stage

## Task Directory
$TASK_DIR

## Target Stage
$TARGET_STAGE_ID (Escalation Round $ROUND of max $MAX_ROUNDS)

## Background
The current mutated environment stage \`$TARGET_STAGE_ID\` in \`stages.py\` is too easy — a weak baseline model can still pass it. Your job is to **maximally** increase the difficulty of this stage. We want to succeed in **ONE round** — do the hardest escalation you can within constraints. Re-escalation wastes time.

**Goal: make this stage as difficult as physically possible while remaining reference-solvable, and maximize the semantic solution distance from the Initial reference and from the other stage references.** PACE-Bench evaluates Initial-to-stage adaptation, so a stage that can be solved by lightly retuning or reusing the Initial design is insufficiently differentiated.

## Critical Constraints (Zero-Tolerance)

1. **Only mutate existing variables** — Use ONLY physical variables that already appear in \`environment.py\`, \`evaluator.py\`, or the existing stages.py mutations. Do NOT introduce physics variables that don't exist in the simulation engine.
2. **Only modify stages.py and agent.py** — Do NOT change \`environment.py\`, \`evaluator.py\`, \`renderer.py\`, or \`feedback.py\`.
3. **Preserve initial solution** — \`build_agent()\` and \`agent_action()\` for the initial environment MUST still pass the initial environment.
4. **Stage-specific solutions** — If \`build_agent_N()\` / \`agent_action_N()\` exist for this stage in \`agent.py\`, they MUST be updated to pass the escalated stage.
5. **Initial reference MUST fail** — The initial reference solution MUST fail on the escalated mutated stage.
6. **UNIFORM_SUFFIX principle** — The \`task_description_suffix\` in stages.py must be uniform across ALL 4 stages (Stage-1 through Stage-4). It must list the UNION of all physical variables that have been modified across ANY of the 4 stages. The suffix must ONLY list variable names as generic warnings (e.g., "Joint torque resilience: The maximum torque..."). NEVER include specific numeric values or directions in the suffix.
7. **Prompt synchronization** — If a changed Constraint or Visible variable is explicitly numeric in the prompt, update it through the existing stage prompt-update mechanism in stages.py using the "(originally OLD_VALUE)" format. If the variable was not previously exposed numerically, do NOT add it. Invisible non-constraints remain numerically hidden.

## Solution-Distance Objective (Critical)

- Force substantial changes in the physical mechanism, construction topology/geometry, primitive usage, load path, control policy, timing, or another task-relevant design dimension.
- Make each stage reference differ substantially from the Initial reference and, where physically possible, from the other stage references. Later stages should generally require a larger departure from Initial.
- Prefer a new reasoning strategy over uniform scaling of dimensions, forces, gains, or timing constants.
- Judge semantic physical difference, not cosmetic code churn: renaming, formatting, comments, reordered statements, duplicated code, and arbitrary constant changes do not count.
- Treat one unchanged or lightly retuned solution passing several stages as evidence of under-differentiated mutations. Cross-stage reference transfer is a diagnostic, not an automatic failure when robustness is physically legitimate.
- Maximize solution distance only within the existing objective, variables, primitives, visibility rules, numerical stability, and reference solvability. Never make code different merely for appearance or expose privileged stage constants.

## Escalation Strategy — AIM FOR ONE-SHOT SUCCESS

**Mindset:** You have ONE chance to make this hard enough. Do the most aggressive escalation the constraints allow. If the task still passes evaluation, we have to re-run everything — costly and slow.

**Prohibited:** Do NOT just incrementally scale existing parameters (e.g., +10% gravity). That is a guaranteed re-escalation.

**Required — Push to Extremes:**

- **Every stage may mutate one or multiple existing variables.** Push them toward physically valid near-breaking extremes and prefer the valid mutation that forces the largest semantic redesign rather than assuming Stage-1 or Stage-2 must be single-variable.

- **Difficulty must increase monotonically:** Stage-4 > Stage-3 > Stage-2 > Stage-1. Later stages may combine conflicting extreme changes, but do not weaken any non-target stage. The initial reference MUST fail, while each stage-specific reference should use a legitimate physical workaround rather than brute-force duplication.

**Information Hiding:** Do NOT spoon-feed the changed values. The agent must discover them through trial. The UNIFORM_SUFFIX must list variables GENERICALLY — never specific values or directions.

## Verification (MANDATORY — Execute in This Order)

### 1. Read the current state
Read \`stages.py\`, \`environment.py\`, \`evaluator.py\`, \`prompt.py\`, and \`agent.py\` to understand the current physics variables, constraints, and reference solutions.

### 2. Escalate the target stage
Modify ONLY the \`$TARGET_STAGE_ID\` entry in \`stages.py\`. If stage-specific reference solutions exist in \`agent.py\`, update them to solve the escalated stage.

### 3. Update UNIFORM_SUFFIX if needed
If you introduced a variable that was not previously in the union of all mutated variables, update the UNIFORM_SUFFIX in ALL 4 stages to include it (with a generic description, never a numeric value).

### 4. Run reference solution tests
\`\`\`bash
cd $REPO_ROOT && python3 tasks/test_reference_solutions.py --task $TASK_NAME
\`\`\`
Expected results:
- Initial reference solution PASSES on Initial env
- Initial reference solution FAILS on ALL 4 mutated stages (Stage-1 through Stage-4)
- Each stage-specific reference solution (if exists) PASSES on its corresponding env

If any of these fail, FIX the issue and re-run until all pass.

### 5. Run pipeline compile check
\`\`\`bash
cd $REPO_ROOT && python3 -c "
import sys; sys.path.insert(0, '.')
from evaluation.evaluate_cross_mutated import get_all_stages, get_reference_solution
all_envs = get_all_stages('$TASK_ID')
print(f'get_all_stages OK: {len(all_envs)} stages')
for env_j in all_envs:
    print(f\"  stage={env_j['stage_id']} desc_len={len(env_j.get('task_description','') or '')}\")
ref = get_reference_solution('$TASK_ID', 'Initial')
print(f'get_reference_solution OK: {len(ref)} bytes')
# Exercise all update_task_description_* functions
import importlib
stages_mod = importlib.import_module('tasks.${CATEGORY}.${TASK_NAME}.stages')
for name in dir(stages_mod):
    obj = getattr(stages_mod, name)
    if callable(obj) and 'update_task_description' in name:
        for env_j in all_envs:
            try:
                desc = env_j.get('task_description', '') or ''
                result = obj(desc, env_j.get('terrain_config', {}), env_j.get('terrain_config', {}), env_j.get('physics_config', {}), env_j.get('physics_config', {}), stage=env_j)
                if result is None:
                    print(f'  WARNING: {name}() returned None for stage {env_j[\"stage_id\"]}')
            except Exception as e:
                print(f'  FAIL: {name}() crashed on stage {env_j[\"stage_id\"]}: {type(e).__name__}: {e}')
print('All stages.py functions exercised successfully.')
"
\`\`\`

### 6. Run mock evaluation pipeline test
\`\`\`bash
cd $REPO_ROOT && python3 evaluation/evaluate.py --task '$TASK_ID' --model-type mock --model-name mock --max-iterations 1 --method baseline --source-env Initial --target-env '$TARGET_STAGE_ID' --max-steps 500
\`\`\`
If this fails with ANY runtime error (TypeError, ImportError, AttributeError, KeyError, etc.), trace it to source, explain root cause, and FIX. Re-run until pass.

### 7. Enforce low solution similarity
Compare the Initial reference with every stage reference and compare stage references pairwise. If the overall code structure, template, construction, or controller is still very similar and only numeric constants differ, return to Step 2, escalate again, revise the reference, and rerun Steps 4-7. Continue until Initial-to-stage and pairwise stage solution similarity is relatively low. Do not stop by merely reporting high similarity. Cross-stage reference transfer may expose a near-universal lightly retuned solution, but legitimate physical robustness is not an automatic failure.

## Fix Mandate
For every violation or test failure, use the Edit tool to fix it IMMEDIATELY. Do not just describe — the Edit call must appear in your response. If no issues in a category, state "No issues for [category]".

## Self-Check Before Finalizing
□ I only modified variables that exist in environment.py/evaluator.py
□ I only changed stages.py and agent.py (no other files)
□ The initial reference solution still passes the Initial environment
□ The initial reference solution FAILS on all 4 mutated stages
□ Stage-specific reference solutions (if any) pass their corresponding stages
□ UNIFORM_SUFFIX is identical across all 4 stages
□ UNIFORM_SUFFIX lists ALL mutated variables generically (no numeric values)
□ Changed Constraint/Visible values use the stage prompt updater and "(originally...)" format; Invisible non-constraints remain hidden
□ Difficulty increases monotonically from Stage-1 through Stage-4, with one or multiple mutations allowed at every stage
□ Each stage requires substantial semantic changes from the Initial solution, and stage references differ from one another wherever physically valid
□ Solution distance comes from mechanism/topology/control changes, not cosmetic edits or trivial parameter retuning
□ I repeated escalation and validation until solution similarity became relatively low; I did not stop after only describing high similarity
□ test_reference_solutions.py passes
□ evaluate.py mock pipeline passes
ENDPROMPT
}

# ==========================================
# MAIN ESCALATION FUNCTION
# ==========================================
run_escalation_for_task() {
    local TASK_DIR="${1%/}"
    local TASK_NAME CATEGORY
    TASK_NAME=$(basename "$TASK_DIR")
    CATEGORY=$(basename "$(dirname "$TASK_DIR")")

    echo "📦 Backing up initial state for revision tracking..."
    local ORIGINAL_STATE_DIR
    ORIGINAL_STATE_DIR=$(mktemp -d)
    cp -r "$TASK_DIR/"* "$ORIGINAL_STATE_DIR/"

    echo ""
    echo "========================================================"
    echo "▶ Difficulty Escalation for: $TASK_DIR"
    echo "========================================================"

    # Step 1: Find 4B-success pairs (store in array to avoid subshell)
    echo ""
    echo "🔍 Scanning for Qwen3-4B success pairs..."
    local PAIRS_OUTPUT
    PAIRS_OUTPUT=$(find_4b_success_pairs "$TASK_DIR")
    if [ -z "$PAIRS_OUTPUT" ]; then
        echo "  [✅] No 4B-success pairs found for this task. Skipping."
        return 0
    fi

    # Build array of pairs
    local PAIRS_ARRAY=()
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        PAIRS_ARRAY+=("$line")
        local src="${line%%|*}"
        local tgt="${line##*|}"
        echo "  [🎯] Found 4B-success pair: $src -> $tgt"
    done <<< "$PAIRS_OUTPUT"

    # Filter by TARGET_STAGE if set
    if [ -n "$TARGET_STAGE" ]; then
        local FILTERED_ARRAY=()
        for pair_entry in "${PAIRS_ARRAY[@]}"; do
            local tgt="${pair_entry##*|}"
            if [ "$tgt" = "$TARGET_STAGE" ]; then
                FILTERED_ARRAY+=("$pair_entry")
            fi
        done
        if [ ${#FILTERED_ARRAY[@]} -eq 0 ]; then
            echo "  [ℹ️] No pairs match target-stage filter: $TARGET_STAGE"
            return 0
        fi
        PAIRS_ARRAY=("${FILTERED_ARRAY[@]}")
        echo "  [🔍] Filtered to target stage: $TARGET_STAGE (${#PAIRS_ARRAY[@]} pair(s))"
    fi

    # Process each pair (for loop avoids subshell, preserves state)
    local PAIR_ENTRY
    for PAIR_ENTRY in "${PAIRS_ARRAY[@]}"; do
        local SRC="${PAIR_ENTRY%%|*}"
        local TGT="${PAIR_ENTRY##*|}"
        escalate_single_pair "$TASK_DIR" "$SRC" "$TGT"
    done

    # Generate escalation diff patch
    local REL_PATH LOG_DIR DIFF_FILE
    REL_PATH="${CATEGORY}/${TASK_NAME}"
    LOG_DIR="tasks/auto_audit_log/$REL_PATH"
    mkdir -p "$LOG_DIR"
    DIFF_FILE="$LOG_DIR/escalation.patch"
    diff -ruN -x "__pycache__" "$ORIGINAL_STATE_DIR" "$TASK_DIR" > "$DIFF_FILE"
    if [ -s "$DIFF_FILE" ]; then
        echo "✅ Escalation diff saved to $DIFF_FILE"
    else
        echo "ℹ️ No changes were made to the files during escalation."
        rm -f "$DIFF_FILE"
    fi
    rm -rf "$ORIGINAL_STATE_DIR"
}

escalate_single_pair() {
    local TASK_DIR="$1"
    local SOURCE="$2"
    local TARGET="$3"
    local TASK_NAME
    TASK_NAME=$(basename "$TASK_DIR")

    echo ""
    echo "========================================================"
    echo "🔧 Escalating pair: $TASK_NAME :: $SOURCE -> $TARGET"
    echo "========================================================"

    local ROUND=1
    while [ $ROUND -le $MAX_ROUNDS ]; do
        echo ""
        echo "----------------------------------------------------------"
        echo "  Round $ROUND / $MAX_ROUNDS for $TASK_NAME :: $SOURCE -> $TARGET"
        echo "----------------------------------------------------------"

        if [ "$DRY_RUN" -eq 1 ]; then
            echo "  [🔍] DRY RUN: Would escalate $TARGET in $TASK_DIR (round $ROUND)"
            echo "  [🔍] DRY RUN: Would then delete results and re-evaluate."
            break
        fi

        # --- Phase 1: Escalate difficulty via Claude Code ---
        echo ""
        echo "  [🧠] Phase 1: Sending escalation prompt to Claude Code..."

        local ESCALATION_PROMPT
        ESCALATION_PROMPT=$(build_escalation_prompt "$TASK_DIR" "$TARGET" "$ROUND")
        local PROMPT_BYTES
        PROMPT_BYTES=${#ESCALATION_PROMPT}

        echo "  [📤] Prompt size: ~${PROMPT_BYTES} bytes"
        echo "  --- PROMPT PREVIEW (first 500 chars) ---"
        echo "${ESCALATION_PROMPT:0:500}"
        echo "  --- END PROMPT PREVIEW ---"

        local OUTPUT
        # NOTE: run_claude_with_fallback streams output to terminal in real-time.
        # We capture its stdout for the classification step, but must also check
        # that it actually succeeded (exit 1 inside $() only kills the subshell).
        set -o pipefail
        OUTPUT=$(run_claude_with_fallback "$ESCALATION_PROMPT" "$TASK_DIR")
        local CLAUDE_EXIT=$?
        set +o pipefail

        if [ "$CLAUDE_EXIT" -ne 0 ] || [ -z "$OUTPUT" ]; then
            echo ""
            echo "  [❌] Claude Code escalation FAILED (exit=$CLAUDE_EXIT, output=${#OUTPUT} bytes)."
            echo "  [❌] Check ANTHROPIC_API_KEY / API connectivity. Stopping."
            exit 1
        fi

        echo ""
        echo "  [📥] Claude Code response (${#OUTPUT} bytes):"
        echo "  =========================================="
        echo "$OUTPUT" | head -100
        if [ "${#OUTPUT}" -gt 10000 ]; then
            echo "  ... (output truncated, full in memory) ..."
        fi
        echo "  =========================================="

        # --- Phase 2: Delete old evaluation results for this pair ---
        echo ""
        echo "  [🗑️] Phase 2: Deleting old Qwen3-4B results for $SOURCE -> $TARGET..."
        delete_pair_results "$TASK_DIR" "$SOURCE" "$TARGET"

        # --- Phase 3: Run Qwen3-4B evaluation (3 turns parallel, early-terminate on success) ---
        echo ""
        echo "  [🚀] Phase 3: Running Qwen3-4B evaluation (3 turns parallel)..."
        run_qwen3_4b_evaluation "$TASK_DIR" "$SOURCE" "$TARGET"
        local EVAL_EXIT=$?

        # --- Phase 4: Interpret result ---
        # 0 = all turns produced results and failed (escalation worked)
        # 1 = at least one turn succeeded (needs more escalation)
        # 2 = no turn produced any result (infra failure, retry)
        if [ $EVAL_EXIT -eq 0 ]; then
            echo ""
            echo "  [🎉] SUCCESS! Qwen3-4B can no longer pass $TASK_NAME :: $SOURCE -> $TARGET"
            echo "  [🎉] Escalation completed in $ROUND round(s)."
            break
        elif [ $EVAL_EXIT -eq 2 ]; then
            echo ""
            echo "  [⚠️] Evaluation infra failure (no results produced). Retrying in 30s..."
            sleep 30
            # Don't increment round — this wasn't a real evaluation
        else
            echo ""
            echo "  [🔄] Qwen3-4B STILL passes this pair. Escalation round $ROUND was insufficient."
            ROUND=$((ROUND + 1))
        fi
    done

    if [ $ROUND -gt $MAX_ROUNDS ]; then
        echo ""
        echo "  [⚠️] WARNING: Reached maximum rounds ($MAX_ROUNDS) without success."
        echo "  [⚠️] $TASK_NAME :: $SOURCE -> $TARGET may still be solvable by Qwen3-4B."
    fi

    # --- Generate handoff log ---
    local REL_PATH LOG_DIR HANDOFF_FILE
    REL_PATH="${CATEGORY}/${TASK_NAME}"
    LOG_DIR="tasks/auto_audit_log/$REL_PATH"
    mkdir -p "$LOG_DIR"
    HANDOFF_FILE="$LOG_DIR/escalation_handoff.md"

    cat > "$HANDOFF_FILE" << EOF
# Difficulty Escalation Handoff: $TASK_NAME
## Timestamp: $(date '+%Y-%m-%d %H:%M:%S %z')
## Task: $TASK_DIR
## Pair: $SOURCE -> $TARGET
## Spec: $TASK_SPEC
## Total Rounds: $ROUND
## Last Status: $(if [ $ROUND -le $MAX_ROUNDS ]; then echo "SUCCESS - 4B no longer passes"; else echo "INCOMPLETE - max rounds reached"; fi)
## Log Files
- Escalation handoff: escalation_handoff.md
EOF
    echo "📋 Handoff file generated: $HANDOFF_FILE"
}

# ==========================================
# MAIN LOOP
# ==========================================
echo "========================================================"
echo "Auto Difficulty Escalation"
echo "========================================================"
echo "Task spec:        $TASK_SPEC"
echo "Max rounds:       $MAX_ROUNDS"
echo "Target stage:     ${TARGET_STAGE:-all}"
echo "Dry run:          $DRY_RUN"
echo "Eval SSH host:    ${EVAL_SSH_HOST:-local}"
echo "Tasks resolved:   ${#TASK_DIRS[@]}"
echo "========================================================"
echo ""

if [ "$DRY_RUN" -eq 1 ]; then
    echo "🔍 DRY RUN MODE — No changes will be made."
    echo ""
fi

OVERALL_START=$(date +%s)
TASKS_PROCESSED=0
TASKS_SKIPPED=0

for TASK_DIR in "${TASK_DIRS[@]}"; do
    TASK_NAME=$(basename "$TASK_DIR")
    echo "========================================================"
    echo "▶ Processing: $TASK_NAME  (${TASKS_PROCESSED}/${#TASK_DIRS[@]} done)"
    echo "========================================================"

    run_escalation_for_task "$TASK_DIR"
    TASKS_PROCESSED=$((TASKS_PROCESSED + 1))
done

OVERALL_END=$(date +%s)
OVERALL_DURATION=$((OVERALL_END - OVERALL_START))

echo ""
echo "========================================================"
echo "✅ Auto Difficulty Escalation Complete"
echo "========================================================"
echo "Tasks processed:  $TASKS_PROCESSED"
echo "Total duration:   ${OVERALL_DURATION}s ($((OVERALL_DURATION / 60))m $((OVERALL_DURATION % 60))s)"
echo "========================================================"
