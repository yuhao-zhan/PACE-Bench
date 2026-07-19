#!/bin/bash
# Claude Code version of auto_audit.sh
# to kill the process: `pkill -9 -f "/bin/bash ./auto_audit.sh --task all"`

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$REPO_ROOT/scripts/resolve_task_dirs.py"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--task <spec>] [--start_from <task_id>] | [<path>]

  --task, -t   Task spec (same as evaluation/run_evaluate_parallel.py --task):
               all | category_N | category_N_MM | CategoryN_.../S_XX | tasks/...
  --start_from Start from a task id within the resolved set (e.g. S_03, K_02).
               Useful when --task expands to multiple tasks (e.g. category_1).
  <path>       Legacy: tasks/Category1_Statics_Equilibrium/S_01

Examples:
  $(basename "$0") --task category_1_01
  $(basename "$0") --task category_1 --start_from S_03
  $(basename "$0") --task all
  $(basename "$0") tasks/Category1_Statics_Equilibrium/S_01
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
# Model configuration
MODELS=("deepseek-v4-pro")

# Global variable to track models that have failed (quota or crash) during this run
BLACKLISTED_MODELS=""

# When claude exits non-zero: print why-it-failed hints (never prints secret values).
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

    if [ "${AUTO_AUDIT_VERBOSE:-0}" = "1" ]; then
        echo "  [🔍] AUTO_AUDIT_VERBOSE=1: env names containing ANTHROPIC/PROXY (values hidden):" >&2
        env | grep -iE '^(ANTHROPIC|HTTP_|HTTPS_|ALL_|NO_)' | while IFS= read -r line; do
            name="${line%%=*}"
            echo "  [🔍]   ${name}=<hidden>" >&2
        done || true
    fi
    echo "  [🔍] Tip: AUTO_AUDIT_VERBOSE=1 ./auto_audit.sh ... for extra env listing" >&2
    echo "  [🔍] -----------------------------------------" >&2
}

# One-line plain-English hint from stderr
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

# Return 0 if we should blacklist this model after failure; 1 if we should not.
claude_should_blacklist_model() {
    local model="$1"
    local errfile="$2"
    if claude_stderr_is_transient "$errfile"; then
        return 1
    fi
    return 0
}

# Function to run Claude Code with model fallback
run_claude_with_fallback() {
    local PROMPT_CONTENT="$1"
    local SUCCESS=false
    local OUTPUT=""
    local CLAUDE_RUN_CWD="${CLAUDE_WORKDIR:-$REPO_ROOT}"

    for MODEL in "${MODELS[@]}"; do
        # Check if the model is in the blacklist
        if [[ " $BLACKLISTED_MODELS " =~ " $MODEL " ]]; then
            # Skip blacklisted models silently
            continue
        fi

        PROMPT_BYTES=${#PROMPT_CONTENT}
        echo "  [→] Calling Claude Code with model: $MODEL (prompt ~${PROMPT_BYTES} bytes)..." >&2

        # Capture stdout and stderr separately
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
        echo "  [→] API call finished after ${API_DURATION}s (exit code $EXIT_CODE) at $(date '+%H:%M:%S')" >&2

        if [ $EXIT_CODE -eq 0 ]; then
            SUCCESS=true
            rm -f "$TMP_ERR" "$TMP_OUT"
            break
        else
            echo "  [⚠️] Model $MODEL failed (exit $EXIT_CODE)." >&2
            summarize_claude_stderr "$TMP_ERR"
            print_claude_failure_diagnostics "$EXIT_CODE" "$MODEL" "$PROMPT_BYTES" "$TMP_ERR" "$TMP_OUT"

            LAST_RUN_DIR="${TMPDIR:-/tmp}/auto_audit_claude_last_run"
            mkdir -p "$LAST_RUN_DIR"
            cp -f "$TMP_ERR" "$LAST_RUN_DIR/stderr.txt"
            cp -f "$TMP_OUT" "$LAST_RUN_DIR/stdout.txt"
            echo "  [ℹ️] Full stdout/stderr saved to: $LAST_RUN_DIR/{stdout.txt,stderr.txt}" >&2

            if [ -s "$TMP_OUT" ]; then
                echo "  [ℹ️] claude stdout (errors sometimes appear here) — first 60 lines:" >&2
                OUT_LINES=$(wc -l < "$TMP_OUT")
                if [ "$OUT_LINES" -le 60 ]; then
                    sed 's/^/    | /' "$TMP_OUT" >&2
                else
                    sed -n '1,35p' "$TMP_OUT" | sed 's/^/    | /' >&2
                    echo "    | ... ($OUT_LINES lines total, truncated) ..." >&2
                    tail -n 25 "$TMP_OUT" | sed 's/^/    | /' >&2
                fi
            else
                echo "  [ℹ️] claude stdout: (empty)" >&2
            fi

            echo "  [ℹ️] claude stderr — full stream:" >&2
            ERR_LINES=$(wc -l < "$TMP_ERR")
            if [ "$ERR_LINES" -le 120 ]; then
                sed 's/^/    | /' "$TMP_ERR" >&2
            else
                echo "    | --- stderr (first 60 lines of $ERR_LINES) ---" >&2
                sed -n '1,60p' "$TMP_ERR" | sed 's/^/    | /' >&2
                echo "    | --- stderr (last 60 lines) ---" >&2
                tail -n 60 "$TMP_ERR" | sed 's/^/    | /' >&2
            fi

            if claude_should_blacklist_model "$MODEL" "$TMP_ERR"; then
                echo "  [🚫] Adding $MODEL to blacklist (skipped for the rest of this script run)." >&2
                BLACKLISTED_MODELS="$BLACKLISTED_MODELS $MODEL "
            else
                echo "  [ℹ️] Not blacklisting $MODEL — transient error; explicit models still apply on next try." >&2
            fi
            rm -f "$TMP_ERR" "$TMP_OUT"
        fi
    done

    if [ "$SUCCESS" = false ]; then
        echo "  [❌] FATAL ERROR: All models failed. Stopping loop." >&2
        rm -rf "$ORIGINAL_STATE_DIR" # Cleanup on fail
        exit 1
    fi

    # Echo the clean output back to the caller
    echo "$OUTPUT"
}

run_auto_audit_for_task() {
    local TASK_DIR="${1%/}"
    local ORIGINAL_STATE_DIR

    echo "📦 Backing up initial state..."
    ORIGINAL_STATE_DIR=$(mktemp -d)
    cp -r "$TASK_DIR/"* "$ORIGINAL_STATE_DIR/"

    # Write detailed prompt to temp file so TASK_DIR expansion is guaranteed correct
    local PROMPT_FILE=$(mktemp)

	cat > "$PROMPT_FILE" <<-'ENDPROMPT'
	# Objective
	Conduct a strict, exhaustive audit of the current task directory.
	YOUR SPECIFIC TASK TO AUDIT: TASK_DIR_PLACEHOLDER
	Your working directory is this task root. All file paths must be relative to `.`.

	## Anti-Laziness Rule
	Do NOT stop after finding 1 or 2 errors. You must provide an EXHAUSTIVE, line-by-line enumeration of EVERY SINGLE violation.

	## Variable Classification (Critical)

	### 1. CONSTRAINT VARIABLE — MUST have numeric value in prompt.py
	A variable that defines an absolute maximum, minimum, or failure threshold required to solve the task. Examples: max structure mass, max joint torque, motor_max_torque, overheat_limit, time_budget, gate positions, target coordinates.
	- Invisible constraints (e.g., motor_max_torque) STILL need numeric values in prompt.py.

	### 2. INVISIBLE NON-CONSTRAINT — NEVER numeric in prompt.py
	Background physics that cannot be visually observed. If ANY numeric value appears in prompt.py → DELETE the number or delete the line.
	Affected: gravity, linear_damping, angular_damping, wind_amplitude, wind_omega, constant_force_x, constant_force_y, drain_velocity_factor, slip_backward_force.
	- Example VIOLATION: "- **Gravity**: |g_y| = 3.0 m/s²" → DELETE THIS LINE.
	- Example VIOLATION: "drain factor of 0.5 per simulation step" → remove the "0.5".
	- Example VIOLATION: "constant backward horizontal force of 28.0N" → remove the "28.0".
	- Qualitative descriptions (e.g., "sap kinetic energy") are allowed; numeric values are not.

	### 3. VISIBLE VARIABLE — MUST have numeric value in prompt.py
	Observable physical properties explicitly mentioned in the prompt. Examples: gate positions, target zone, initial craft position.

	### 4. _CE MODE — Skip, not a violation

	## Audit Steps

	### Step 1: Cross-Module Consistency
	Review environment.py, evaluator.py, feedback.py, prompt.py, stages.py, renderer.py. All modules must be logically consistent — physics mechanics in environment.py MUST align with evaluation logic and prompt descriptions. Document any discrepancy, conflict, or misaligned physics across ALL modules.

	### Step 2: Invisible Non-Constraint Sweep
	Line by line in prompt.py: find and DELETE any numeric value of: gravity, linear_damping, angular_damping, wind_amplitude, wind_omega, constant_force_x, constant_force_y, drain_velocity_factor, slip_backward_force.

	### Step 3: Constraint Completeness
	Scan environment.py for ALL hardcoded constraint numbers. Each must appear with explicit numeric value in prompt.py. Add any missing — do not stop at the first found.

	### Step 4: Mutation Sync
	For each stages.py mutation, verify the "NEW_VALUE (originally OLD_VALUE)" format is correctly applied when a Constraint/Visible variable changes.
	For every regex or string replacement used by update_task_description_for_visible_changes, execute the updater against the exact base task description through the real prompt path. Use re.subn() or an equivalent explicit match count and require exactly the intended number of replacements (normally one per field); zero matches and unintended multiple matches are violations. Test Stage-1 through Stage-4 independently and assert that the final prompt contains the target value plus original-value annotation, removes the stale unannotated value, leaves unrelated text unchanged, and never inserts a numeric Invisible non-constraint. A function returning without an exception is NOT proof that its replacement worked.

	### Step 5: UNIFORM_SUFFIX Tone
	The suffix must ONLY list variable names as generic warnings (e.g., "Atmospheric properties may differ"). NEVER specific values or directions. Document every instance where UNIFORM_SUFFIX fails this rule.

	### Step 6: Runtime Pipeline Verification (MANDATORY)
	Steps 1-5 are static analysis. Runtime errors (TypeError, ImportError, AttributeError, etc.) only surface when the evaluation framework actually calls your code. This step catches those.

	Run the full cross-mutation pipeline at demo scale across ALL stages (Initial → Stage-1 through Stage-4). Use the mock model (no API cost, instant):
	```bash
	cd TASK_DIR_PLACEHOLDER/../../../.. && for stage in Stage-1 Stage-2 Stage-3 Stage-4; do echo "=== Testing Initial -> $stage ===" && python scripts/evaluation/evaluate.py --task TASK_NAME_PLACEHOLDER --model-type mock --model-name mock --max-iterations 1 --method baseline --source-env Initial --target-env "$stage" --max-steps 500 || break; done
	```
	If any stage fails, trace the error to its source file and fix it with the Edit tool. Re-run until all 4 stages pass. Pay special attention to stages.py — its functions are called by the framework on every mutation but are often never exercised by the task's own test scripts.

	## Fix Mandate
	For every violation found, use the Edit tool to fix it IMMEDIATELY. Do not just describe — the Edit call must appear in your response. If no violations in a category, state "No violations found for [Category]".
	After any edit, restart the COMPLETE audit from Step 1 on the updated files. If the next inspection finds any error, fix it and restart again. Stop only after a fresh complete audit performed after the last revision finds zero violations, requires no edits, and passes all runtime checks. An inspection that changed files cannot count as the final CLEAN pass.
	ENDPROMPT


    # Replace placeholders with actual values
    local TASK_NAME
    TASK_NAME=$(basename "$TASK_DIR")
    sed -i "s|TASK_DIR_PLACEHOLDER|${TASK_DIR}|g" "$PROMPT_FILE"
    sed -i "s|TASK_NAME_PLACEHOLDER|${TASK_NAME}|g" "$PROMPT_FILE"
    PROMPT=$(cat "$PROMPT_FILE")
    rm -f "$PROMPT_FILE"

    # ==========================================
    # EXECUTION LOOP
    # ==========================================
    local ITERATION=1
    while true; do
        echo "========================================================"
        echo "🔄 Iteration $ITERATION: Running audit on $TASK_DIR..."
        echo "========================================================"
        echo ""

        echo "📤 Sending prompt to Claude (${#PROMPT} bytes)..."
        echo "--- PROMPT PREVIEW (first 500 chars) ---"
        echo "${PROMPT:0:500}"
        echo "--- END PROMPT PREVIEW ---"
        echo ""

        CLAUDE_WORKDIR="$TASK_DIR"
        OUTPUT=$(run_claude_with_fallback "$PROMPT")

        echo "📥 Raw output from Claude (${#OUTPUT} bytes):"
        echo "=========================================="
        echo "$OUTPUT"
        echo "=========================================="
        echo ""

        # Check if files actually changed
        local DIFF_COUNT DIFF_FILE
        DIFF_FILE=$(mktemp)
        diff -ruN -x "__pycache__" "$ORIGINAL_STATE_DIR" "$TASK_DIR" > "$DIFF_FILE"
        DIFF_COUNT=$(wc -l < "$DIFF_FILE")

        echo "🔍 File change detection:"
        echo "  Original state: $ORIGINAL_STATE_DIR"
        echo "  Current state:  $TASK_DIR"
        echo "  Diff lines:     $DIFF_COUNT"

        if [ "$DIFF_COUNT" -gt 0 ]; then
            echo "  ✅ Files were modified! Diff preview:"
            head -30 "$DIFF_FILE"
            if [ "$DIFF_COUNT" -gt 30 ]; then
                echo "  ... ($(($DIFF_COUNT - 30)) more diff lines)"
            fi
        else
            echo "  ⚠️  WARNING: No files were modified despite the report!"
        fi
        echo ""

        if [ "$DIFF_COUNT" -eq 0 ]; then
            echo "🛠️  Forcing model to output exact Edit commands..."

            local FIX_PROMPT
            FIX_PROMPT="You are still working only inside ${TASK_DIR}.
You previously audited ${TASK_DIR} and found violations but did NOT actually call the Edit tool.
Here is your previous audit report:

$OUTPUT

Now produce ONLY the exact Edit commands needed, in this format (one per line):
EDIT: file=\"relative/path/filename.py\" old_string=\"EXACT_old_text\" new_string=\"EXACT_new_text\"
The file path MUST be relative to the CURRENT task root only. Valid examples: \"prompt.py\", \"stages.py\", \"subdir/file.py\".
Do NOT use absolute paths. Do NOT prefix with \"tasks/\". Do NOT repeat the task directory name in the path.
If no edits needed, reply exactly: NO_EDITS_NEEDED"

            local FIX_OUTPUT
            FIX_OUTPUT=$(run_claude_with_fallback "$FIX_PROMPT")

            echo "--- Model edit commands response ---"
            echo "$FIX_OUTPUT"
            echo "------------------------------------"
            echo ""

            if echo "$FIX_OUTPUT" | grep -q "NO_EDITS_NEEDED"; then
                echo "Model confirmed: no edits needed. Treating as CLEAN."
            else
                echo "Parsing and applying Edit commands..."
                echo "$FIX_OUTPUT" | grep "^EDIT:" | while IFS= read -r line; do
                    local EDIT_FILE OLD_STR NEW_STR
                    EDIT_FILE=$(echo "$line" | sed 's/^EDIT: file="//' | sed 's/".*//')
                    OLD_STR=$(echo "$line" | sed 's/.*old_string="//' | sed 's/".*new_string="/|||/g' | cut -d'|' -f1)
                    NEW_STR=$(echo "$line" | sed 's/.*new_string="//' | sed 's/"$//')
                    if [ -n "$EDIT_FILE" ] && [ -n "$OLD_STR" ] && [ -n "$NEW_STR" ]; then
                        echo "  Applying: $EDIT_FILE"
                        echo "  old: $OLD_STR"
                        echo "  new: $NEW_STR"
                        # Security: reject absolute paths and path-escaping attempts.
                        # Path-escaping check: contains ../ or ends with /..
                        if [[ "$EDIT_FILE" == /* ]] || [[ "$EDIT_FILE" == *"/.."* ]]; then
                            echo "  ❌ Rejected unsafe path in EDIT command: $EDIT_FILE"
                            continue
                        fi

                        # Always extract just the filename — the model may return any of:
                        #   - "stages.py"                         → stages.py (correct)
                        #   - "tasks/Category2_Kinematics_Linkages/K_04/stages.py" → stages.py (stripped)
                        #   - "Category2_Kinematics_Linkages/K_04/stages.py"        → stages.py (basename)
                        local EDIT_FILE_CLEAN
                        EDIT_FILE_CLEAN=$(basename "${EDIT_FILE#tasks/}")
                        FULL_PATH="$TASK_DIR/$EDIT_FILE_CLEAN"
                        if [ -f "$FULL_PATH" ]; then
                            cp "$FULL_PATH" "$FULL_PATH.bak"
                            if echo "$OLD_STR" | grep -q '|||'; then
                                local OLD_PART1 OLD_PART2
                                OLD_PART1=$(echo "$OLD_STR" | cut -d'|' -f1)
                                OLD_PART2=$(echo "$OLD_STR" | cut -d'|' -f2)
                                sed -i "s|$OLD_PART1|$NEW_STR|g" "$FULL_PATH"
                            else
                                sed -i "s|$OLD_STR|$NEW_STR|g" "$FULL_PATH"
                            fi
                            echo "  ✅ Applied: $EDIT_FILE"
                        else
                            echo "  ❌ File not found: $FULL_PATH"
                        fi
                    fi
                done
            fi
            echo ""
        fi

        rm -f "$DIFF_FILE"

        echo "========================================================"
        echo "🧠 Evaluating LLM Response for Completion Status..."

        local CLASSIFY_PROMPT
        CLASSIFY_PROMPT="You are classifying the following audit report for ${TASK_DIR}.

$OUTPUT

Did the auditor find ANY violations?
- If ZERO violations found (stated 'No violations' for all categories), reply CLEAN.
- If ANY violations found or fixed, or report is ambiguous, reply DIRTY.
Reply with ONLY the word CLEAN or DIRTY."

        local CLASSIFICATION
        CLASSIFICATION=$(run_claude_with_fallback "$CLASSIFY_PROMPT")
        CLASSIFICATION=$(echo "$CLASSIFICATION" | xargs)

        echo "Classification Result: [$CLASSIFICATION]"

        if [ "$CLASSIFICATION" = "CLEAN" ]; then
            echo "✅ Task $TASK_DIR is clean! Breaking loop."
            break
        else
            echo "⚠️  Violations found. Restarting audit..."
            ITERATION=$((ITERATION+1))
        fi
    done

    # ==========================================
    # GENERATE LOG / DIFF
    # ==========================================
    echo "========================================================"
    echo "📝 Generating revision patch log..."

    local REL_PATH LOG_DIR LOG_FILE HANDOFF_FILE
    REL_PATH=$(echo "$TASK_DIR" | sed "s|^$REPO_ROOT/||" | sed 's|^tasks/||')
    LOG_DIR="tasks/auto_audit_log/$REL_PATH"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/revisions.patch"

    diff -ruN -x "__pycache__" "$ORIGINAL_STATE_DIR" "$TASK_DIR" > "$LOG_FILE"

    if [ -s "$LOG_FILE" ]; then
        echo "✅ Success: Revisions saved to $LOG_FILE"
    else
        echo "ℹ️ No changes were made to the files during this audit."
        rm -f "$LOG_FILE"
    fi

    rm -rf "$ORIGINAL_STATE_DIR"

    HANDOFF_FILE="$LOG_DIR/HANDOFF.md"
    cat > "$HANDOFF_FILE" <<- 'EOF'
	# Audit Handoff
	## Timestamp: TIMESTAMP_PLACEHOLDER
	## Task: TASK_DIR_PLACEHOLDER
	## Spec: SPEC_PLACEHOLDER
	## Total Iterations: ITER_PLACEHOLDER
	## Last Run Status: CLEAN
	## Log Files
	- Revision patch: revisions.patch
	EOF
    sed -i "s|TIMESTAMP_PLACEHOLDER|$(date '+%Y-%m-%d %H:%M:%S %z')|g" "$HANDOFF_FILE"
    sed -i "s|TASK_DIR_PLACEHOLDER|${TASK_DIR}|g" "$HANDOFF_FILE"
    sed -i "s|SPEC_PLACEHOLDER|${TASK_SPEC}|g" "$HANDOFF_FILE"
    sed -i "s|ITER_PLACEHOLDER|${ITERATION}|g" "$HANDOFF_FILE"

    echo "📋 Handoff file generated: $HANDOFF_FILE"
    echo "========================================================"
}

# ==========================================
# ARCHIVE & PRIORITY SYSTEM
# ==========================================
ARCHIVE_FILE="$REPO_ROOT/tasks/archive.json"

# Compute 4B-failure count per task for priority sorting.
# Returns "N|TASK_DIR" per line, sorted by N descending (more failures = higher priority).
# Pairs with NO evaluation results also count as priority (unevaluated tasks go first).
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
    local task_rel="$1"   # e.g. Category5_Cybernetics_Control/C_03
    local key="$2"        # "audit" or "feedback"
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
    if is_task_archived "$task_rel" "audit"; then
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
    echo "▶ Auto-audit task: $TASK_DIR  (spec: $TASK_SPEC)"
    echo "========================================================"
    run_auto_audit_for_task "$TASK_DIR" || exit 1
    mark_task_archived "$task_rel" "audit"
    echo "📝 Archived: $task_rel → archive.json [audit]"
done
