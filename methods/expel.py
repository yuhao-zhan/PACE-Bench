"""Insights-only ExpeL adaptation for PACE-Bench source-to-target transfer.

Official ExpeL learns both rules and retrievable trajectories from training-task
rollouts.  PACE-Bench deliberately transfers only distilled rules from the source
environment: raw source code/trajectories can anchor a target design to obsolete
physics.  The rule set is frozen during target evaluation and ranked by a
configurable embedding function.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext, StrategyRuntime, StrategyStep
from pace_bench.evaluation.prompts import PromptBuilder
from pace_bench.evaluation.providers import load_object


Embedder = Callable[[str], Sequence[float]]
DEFAULT_EXPEL_EMBEDDING_MODEL = "princeton-nlp/sup-simcse-roberta-large"


class SupSimCSEEmbedder:
    """Lazy Sup-SimCSE encoder required by the PACE paper adaptation."""

    def __init__(self, model_name: str, device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device
        self._tokenizer: Any = None
        self._model: Any = None

    def __call__(self, text: str) -> Sequence[float]:
        self._load()
        import torch

        encoded = self._tokenizer(
            text,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        encoded = {key: value.to(self._model.device) for key, value in encoded.items()}
        with torch.no_grad():
            output = self._model(**encoded)
        vector = getattr(output, "pooler_output", None)
        if vector is None:
            vector = output.last_hidden_state[:, 0]
        vector = torch.nn.functional.normalize(vector.float(), p=2, dim=-1)
        return vector[0].detach().cpu().tolist()

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "Paper-aligned ExpeL retrieval requires torch and transformers"
            ) from exc
        device = self.device
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name).to(device).eval()


class ExpeLStrategy:
    """Extract source-rollout rules once, then retrieve relevant rules per attempt."""

    name = "expel"

    def __init__(
        self,
        *,
        retrieval_top_k: int = 5,
        max_rules: int = 20,
        expel_rules: list[str] | None = None,
        expel_source_rollout: Any = None,
        expel_source_rollout_path: str | None = None,
        expel_embedder: str | None = None,
        expel_embedding_model: str = DEFAULT_EXPEL_EMBEDDING_MODEL,
        expel_embedding_device: str = "auto",
    ) -> None:
        if retrieval_top_k < 1 or max_rules < 1:
            raise ValueError("retrieval_top_k and max_rules must be positive")
        self.retrieval_top_k = retrieval_top_k
        self.max_rules = max_rules
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompts = PromptBuilder()
        self.rules: list[str] = []
        self.embedder: Embedder | None = None
        self._rule_vectors: list[Sequence[float]] = []
        self.supplied_rules = list(expel_rules) if expel_rules is not None else None
        self.source_rollout = expel_source_rollout
        self.source_rollout_path = expel_source_rollout_path
        self.embedder_specification = expel_embedder
        self.embedding_model = expel_embedding_model
        self.embedding_device = expel_embedding_device

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.embedder = _load_embedder(
            self.embedder_specification,
            model_name=self.embedding_model,
            device=self.embedding_device,
        )
        supplied = self.supplied_rules
        if isinstance(supplied, list):
            self.rules = _dedupe(str(rule) for rule in supplied if str(rule).strip())[
                : self.max_rules
            ]
        else:
            rollout = _load_source_rollout(
                context,
                inline=self.source_rollout,
                configured_path=self.source_rollout_path,
            )
            self.rules = self._extract_rules(rollout)
        self._rule_vectors = (
            [self.embedder(rule) for rule in self.rules] if self.embedder else []
        )

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        context, _ = self._require_ready()
        prompt = _vanilla_prompt(self.prompts, context, history)
        query = context.task_context["task_description"]
        if history:
            query += "\n" + history[-1].verification.feedback
        retrieved = self._retrieve(query)
        if retrieved:
            rules = "\n".join(
                f"{index}. {rule}" for index, rule in enumerate(retrieved, 1)
            )
            prompt = f"""# ExpeL Source-Environment Insights

The following distilled rules were learned from rollout experience in the source
environment. Transfer the physical insight, but do not assume its old numbers,
geometry, timing, or raw code remain valid in the mutated target environment.

{rules}

{prompt}"""
        attempt = history[-1].attempt + 1 if history else 1
        request = self._request(prompt, attempt=attempt, purpose="candidate")
        return StrategyStep.one(request, label="expel-candidate")

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        """Target attempts do not mutate ExpeL's frozen source-derived rule set."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "adaptation": "source-rollout-insights-only",
            "retrieval_top_k": self.retrieval_top_k,
            "max_rules": self.max_rules,
            "rule_count": len(self.rules),
            "embedding": (
                getattr(self.embedder, "model_name", None)
                or ("configured" if self.embedder else "lexical-jaccard")
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _extract_rules(self, rollout: str) -> list[str]:
        context, runtime = self._require_ready()
        if not rollout.strip():
            return []
        prompt = f"""You are the insight-extraction stage of ExpeL. Distill concise,
general rules from source-environment rollout experience. Contrast successful and
failed attempts when both appear. Rules must capture reusable physical reasoning,
design, control, and debugging lessons, not source-specific numbers or raw code.
Return only JSON: {{"rules": ["rule 1", "rule 2"]}}. Produce at most {self.max_rules} rules.

# Task
{context.task_context['task_description']}

# Source-Environment Rollout
{rollout}"""
        request = self._request(prompt, attempt=0, purpose="source-insight-extraction")
        response = runtime.generate_auxiliary(request, purpose="expel-insights")
        rules = _parse_rules(response.text)
        return _dedupe(rules)[: self.max_rules]

    def _retrieve(self, query: str) -> list[str]:
        if not self.rules:
            return []
        if self.embedder and self._rule_vectors:
            query_vector = self.embedder(query)
            scored = [
                (_cosine(query_vector, vector), index)
                for index, vector in enumerate(self._rule_vectors)
            ]
        else:
            query_tokens = _tokens(query)
            scored = [
                (_jaccard(query_tokens, _tokens(rule)), index)
                for index, rule in enumerate(self.rules)
            ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [self.rules[index] for _, index in scored[: self.retrieval_top_k]]

    def _request(self, prompt: str, *, attempt: int, purpose: str) -> GenerationRequest:
        context, _ = self._require_ready()
        config = context.config
        return GenerationRequest(
            prompt=prompt,
            seed=config.seed + attempt,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={"attempt": attempt, "method": self.name, "purpose": purpose},
        )

    def _require_ready(self) -> tuple[StrategyContext, StrategyRuntime]:
        if self.context is None or self.runtime is None:
            raise RuntimeError("ExpeLStrategy must be initialized before use")
        return self.context, self.runtime


def _load_source_rollout(
    context: StrategyContext, *, inline: Any = None, configured_path: str | None = None
) -> str:
    if inline is not None:
        return _format_rollout(inline)
    if configured_path:
        path = Path(str(configured_path)).expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                f"Configured ExpeL source rollout does not exist: {path}"
            )
        if path.suffix.lower() in {".json", ".jsonl"}:
            if path.suffix.lower() == ".jsonl":
                values = [
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                return _format_rollout(values)
            return _format_rollout(json.loads(path.read_text(encoding="utf-8")))
        return path.read_text(encoding="utf-8")
    if context.reference_code:
        return f"""Outcome: SUCCESS in the source environment
Code:
```python
{context.reference_code}
```
The benchmark reference solution passed its source environment."""
    return ""


def _format_rollout(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def _load_embedder(
    specification: Any, *, model_name: str, device: str
) -> Embedder | None:
    if specification is None:
        return SupSimCSEEmbedder(model_name, device)
    if specification == "lexical":
        return None
    if not isinstance(specification, str):
        raise TypeError("expel_embedder must be a dotted import string")
    loaded = load_object(specification)
    instance = loaded() if isinstance(loaded, type) else loaded
    if callable(instance):
        return instance
    encode = getattr(instance, "encode", None)
    if callable(encode):
        return encode
    raise TypeError("Configured ExpeL embedder must be callable or expose encode(text)")


def _parse_rules(text: str) -> list[str]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict) and isinstance(value.get("rules"), list):
            return [str(rule).strip() for rule in value["rules"] if str(rule).strip()]
    except json.JSONDecodeError:
        pass
    rules: list[str] = []
    for line in stripped.splitlines():
        match = re.match(r"\s*(?:[-*]|\d+[.)]|ADD\s+\d+:)\s*(.+)", line, re.IGNORECASE)
        if match:
            rules.append(match.group(1).strip())
    return rules


def _dedupe(values: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value)).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z_][a-z0-9_]+", text.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    size = min(len(left), len(right))
    if not size:
        return 0.0
    dot = sum(float(left[i]) * float(right[i]) for i in range(size))
    left_norm = math.sqrt(sum(float(left[i]) ** 2 for i in range(size)))
    right_norm = math.sqrt(sum(float(right[i]) ** 2 for i in range(size)))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _vanilla_prompt(
    builder: PromptBuilder,
    context: StrategyContext,
    history: Sequence[AttemptRecord],
) -> str:
    if not history:
        return builder.initial(context.task_context)
    previous = history[-1]
    best = max(history, key=lambda item: item.score)
    if context.config.mode == RunMode.ADAPTATION:
        reference = history[0]
        return builder.adaptation_revision(
            context.task_context,
            reference_code=context.reference_code or reference.code,
            reference_feedback=context.reference_feedback
            or reference.verification.feedback,
            best_code=best.code,
            best_feedback=best.verification.feedback,
            previous_code=previous.code,
            previous_feedback=previous.verification.feedback,
            best_attempt=best.attempt,
            previous_attempt=previous.attempt,
        )
    return builder.revision(
        context.task_context,
        best_code=best.code,
        best_feedback=best.verification.feedback,
        previous_code=previous.code,
        previous_feedback=previous.verification.feedback,
        best_attempt=best.attempt,
        previous_attempt=previous.attempt,
    )


Method = ExpeLStrategy
Strategy = ExpeLStrategy
