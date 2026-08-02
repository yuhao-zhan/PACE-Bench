#!/usr/bin/env bash

set -o pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACE_ROOT="${PACE_ROOT:-${SCRIPT_DIR}}"
PACE_ENV="${PACE_ENV:-${SCRIPT_DIR}/../.miniforge3/envs/pace-bench-vllm}"
CONDA_SETUP="${CONDA_SETUP:-${SCRIPT_DIR}/../.miniforge3/etc/profile.d/conda.sh}"

if [[ ! -f "${CONDA_SETUP}" ]]; then
    echo "ERROR: Conda initialization script not found: ${CONDA_SETUP}" >&2
    exit 2
fi
# shellcheck disable=SC1090
source "${CONDA_SETUP}"
if ! conda activate "${PACE_ENV}"; then
    echo "ERROR: Cannot activate PACE-Bench environment: ${PACE_ENV}" >&2
    exit 2
fi

set -u

PACE_BIN="${PACE_BIN:-${PACE_ENV}/bin/pace-bench}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"

MODEL=""
METHOD=""
PORT=""
WORKERS=""
ATTEMPTS=20
RUNS=2
MAX_TOKENS=65536
TIMEOUT_SECONDS=7200
OUTPUT=""
OUTPUT_EXPLICIT=0
ENV_SELECTORS=("all")
TASK_SELECTORS=()
METHOD_OPTIONS=()
EXTRA_FLAGS=()
GENERATE_REPORT=1
DRY_RUN=0
FROM_SCRATCH=0

usage() {
    cat <<'EOF'
Usage:
  bash run_pace_vllm.sh --model MODEL --method METHOD --task SELECTOR [options]

Required:
  --model MODEL           Qwen3-4B, Qwen3-8B, Qwen3-14B, or Qwen3-32B
                          Short aliases 4B, 8B, 14B, and 32B are accepted.
  --method METHOD         For example: vanilla, reflexion, self_refine, ace,
                          reasoning_bank, or tree_of_thoughts.
  --task SELECTOR[,..]    Task/category selector. Separate multiple selectors
                          with commas, or repeat this option.
                          Examples: --task category_1,category_2
                                    --task S_01 --task K_03

Options:
  --env ENV               Stage selector; repeat to combine. Default: all for
                          adaptation, Initial for from-scratch.
  --from-scratch          Solve each task's Initial environment without a
                          reference solution. Combine with --env Stage-N to
                          solve that environment directly.
  --port PORT             Override the model's default vLLM port
  --workers N             Override model-specific concurrency
  --attempts N            Attempt budget per trajectory. Default: 20
  --runs N                Independent trajectories per selected environment. Default: 2
  --max-tokens N          Maximum output tokens. Default: 65536
  --timeout-seconds N     Per-generation timeout. Default: 7200
  --method-option K=V     Method option; repeat as needed
  --output PATH           Result root. Defaults to PACE-Bench/results, or
                          PACE-Bench/results_scratch with --from-scratch.
  --no-resume             Rerun completed result files
  --dry-run               Enumerate work without model calls
  --save-gif              Save verification GIFs
  --no-report             Do not generate report.json after evaluation
  -h, --help              Show this help

Default endpoint/concurrency mapping:
  Qwen3-4B   -> 127.0.0.1:2003, workers=24
  Qwen3-8B   -> 127.0.0.1:2004, workers=20
  Qwen3-14B  -> 127.0.0.1:2005, workers=16
  Qwen3-32B  -> 127.0.0.1:2006, workers=12

Example:
  bash run_pace_vllm.sh \
    --model Qwen3-4B \
    --method vanilla \
    --task category_1,category_2

From-scratch example:
  bash run_pace_vllm.sh \
    --model Qwen3-4B \
    --method vanilla \
    --task category_1 \
    --from-scratch
EOF
}

die() {
    echo "ERROR: $*" >&2
    exit 2
}

require_value() {
    [[ $# -ge 2 && -n "${2:-}" ]] || die "$1 requires a value"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)
            require_value "$@"
            MODEL="$2"
            shift 2
            ;;
        --method)
            require_value "$@"
            METHOD="$2"
            shift 2
            ;;
        --task)
            require_value "$@"
            IFS=',' read -r -a task_values <<< "$2"
            for task_value in "${task_values[@]}"; do
                task_value="${task_value#"${task_value%%[![:space:]]*}"}"
                task_value="${task_value%"${task_value##*[![:space:]]}"}"
                [[ -n "${task_value}" ]] || die "--task contains an empty selector"
                TASK_SELECTORS+=("${task_value}")
            done
            shift 2
            ;;
        --env)
            require_value "$@"
            if [[ "${ENV_SELECTORS[*]}" == "all" ]]; then
                ENV_SELECTORS=()
            fi
            ENV_SELECTORS+=("$2")
            shift 2
            ;;
        --port)
            require_value "$@"
            PORT="$2"
            shift 2
            ;;
        --workers)
            require_value "$@"
            WORKERS="$2"
            shift 2
            ;;
        --attempts)
            require_value "$@"
            ATTEMPTS="$2"
            shift 2
            ;;
        --runs)
            require_value "$@"
            RUNS="$2"
            shift 2
            ;;
        --max-tokens)
            require_value "$@"
            MAX_TOKENS="$2"
            shift 2
            ;;
        --timeout-seconds)
            require_value "$@"
            TIMEOUT_SECONDS="$2"
            shift 2
            ;;
        --method-option)
            require_value "$@"
            METHOD_OPTIONS+=("$2")
            shift 2
            ;;
        --output)
            require_value "$@"
            OUTPUT="$2"
            OUTPUT_EXPLICIT=1
            shift 2
            ;;
        --no-resume|--save-gif)
            EXTRA_FLAGS+=("$1")
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            EXTRA_FLAGS+=("$1")
            shift
            ;;
        --from-scratch)
            FROM_SCRATCH=1
            shift
            ;;
        --no-report)
            GENERATE_REPORT=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

[[ -n "${MODEL}" ]] || die "--model is required"
[[ -n "${METHOD}" ]] || die "--method is required"
[[ ${#TASK_SELECTORS[@]} -gt 0 ]] || die "at least one --task is required"

case "${MODEL,,}" in
    4b|qwen3-4b)
        MODEL="Qwen3-4B"
        DEFAULT_PORT=2003
        DEFAULT_WORKERS=24
        ;;
    8b|qwen3-8b)
        MODEL="Qwen3-8B"
        DEFAULT_PORT=2004
        DEFAULT_WORKERS=20
        ;;
    14b|qwen3-14b)
        MODEL="Qwen3-14B"
        DEFAULT_PORT=2005
        DEFAULT_WORKERS=16
        ;;
    32b|qwen3-32b)
        MODEL="Qwen3-32B"
        DEFAULT_PORT=2006
        DEFAULT_WORKERS=12
        ;;
    *)
        die "unsupported model: ${MODEL}"
        ;;
esac

PORT="${PORT:-${DEFAULT_PORT}}"
WORKERS="${WORKERS:-${DEFAULT_WORKERS}}"

for value in "${PORT}" "${WORKERS}" "${ATTEMPTS}" "${RUNS}" \
    "${MAX_TOKENS}" "${TIMEOUT_SECONDS}"; do
    [[ "${value}" =~ ^[0-9]+$ ]] || die "numeric options must be positive integers"
    (( value > 0 )) || die "numeric options must be greater than zero"
done

if [[ -z "${OUTPUT}" ]]; then
    if [[ "${FROM_SCRATCH}" -eq 1 ]]; then
        OUTPUT="${PACE_ROOT}/results_scratch"
    else
        OUTPUT="${PACE_ROOT}/results"
    fi
elif [[ "${OUTPUT}" != /* ]]; then
    OUTPUT="${PACE_ROOT}/${OUTPUT}"
fi

export NO_PROXY="${NO_PROXY:+${NO_PROXY},}127.0.0.1,localhost,g20,11.11.7.2"
export no_proxy="${no_proxy:+${no_proxy},}127.0.0.1,localhost,g20,11.11.7.2"
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-dummy}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}"
export PYGAME_HIDE_SUPPORT_PROMPT="${PYGAME_HIDE_SUPPORT_PROMPT:-1}"

[[ -x "${PACE_BIN}" ]] || die "pace-bench executable not found: ${PACE_BIN}"
cd "${PACE_ROOT}" || exit 1

endpoint="http://${VLLM_HOST}:${PORT}/v1"
if ! response="$(curl --noproxy '*' --fail --silent --show-error \
    --max-time 10 "${endpoint}/models")"; then
    die "vLLM endpoint is not ready: ${endpoint}"
fi
if ! RESPONSE="${response}" EXPECTED_MODEL="${MODEL}" "${PACE_ROOT}/.conda/bin/python" -c \
    'import json, os; raise SystemExit(os.environ["EXPECTED_MODEL"] not in {x["id"] for x in json.loads(os.environ["RESPONSE"])["data"]})'; then
    die "endpoint ${endpoint} does not expose expected model ${MODEL}"
fi

command=(
    "${PACE_BIN}" evaluate
)
if [[ "${FROM_SCRATCH}" -eq 1 ]]; then
    command+=(--from-scratch)
fi
for selector in "${TASK_SELECTORS[@]}"; do
    command+=(--task "${selector}")
done
for selector in "${ENV_SELECTORS[@]}"; do
    command+=(--env "${selector}")
done
command+=(
    --method "${METHOD}"
    --provider vllm
    --model "${MODEL}"
    --base-url "${endpoint}"
    --attempts "${ATTEMPTS}"
    --runs "${RUNS}"
    --workers "${WORKERS}"
    --max-tokens "${MAX_TOKENS}"
    --timeout-seconds "${TIMEOUT_SECONDS}"
)
if [[ "${OUTPUT_EXPLICIT}" -eq 1 ]]; then
    command+=(--output "${OUTPUT}")
fi
for option in "${METHOD_OPTIONS[@]}"; do
    command+=(--method-option "${option}")
done
command+=("${EXTRA_FLAGS[@]}")

echo "Experiment configuration:"
echo "  pace_env=${CONDA_PREFIX}"
echo "  model=${MODEL} method=${METHOD}"
echo "  mode=$([[ "${FROM_SCRATCH}" -eq 1 ]] && echo from-scratch || echo adaptation)"
echo "  tasks=${TASK_SELECTORS[*]} environments=${ENV_SELECTORS[*]}"
echo "  endpoint=${endpoint} workers=${WORKERS}"
echo "  attempts=${ATTEMPTS} runs=${RUNS} max_tokens=${MAX_TOKENS}"
echo "  output=${OUTPUT}"
printf 'Command:'
printf ' %q' "${command[@]}"
printf '\n'

if ! "${command[@]}"; then
    echo "Evaluation failed; partial completed JSON files remain resumable in ${OUTPUT}." >&2
    exit 1
fi

if [[ "${GENERATE_REPORT}" -eq 1 && "${DRY_RUN}" -eq 0 ]]; then
    echo "Generating report..."
    "${PACE_BIN}" report \
        --input "${OUTPUT}" \
        --output "${OUTPUT}/report.json" \
        > "${OUTPUT}/report.stdout.log"
    echo "Report: ${OUTPUT}/report.json"
fi

echo "Experiment completed successfully."
