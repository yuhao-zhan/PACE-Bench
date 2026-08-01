"""PACE-Bench positive-example LoRA SFT adaptation inspired by SEAL.

This is intentionally labelled an adaptation, not the official SEAL algorithm.
Official SEAL learns a policy that emits self-edits and trains that policy with
downstream reward (ReSTEM).  PACE-Bench instead treats each positive-score
``(prompt, generated code)`` pair as supervised data: before the next attempt it
resets LoRA and retrains from scratch on every positive pair accumulated so far.
That policy is the one documented in the PACE-Bench paper.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext
from pace_bench.evaluation.prompts import PromptBuilder

try:
    from pace_bench.evaluation.config import (
        CandidateSubmission,
        StrategyRuntime,
        StrategyStep,
    )
except ImportError:

    @dataclass
    class CandidateSubmission:  # type: ignore[no-redef]
        request: GenerationRequest | None = None
        metadata: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class StrategyStep:  # type: ignore[no-redef]
        submissions: Sequence[CandidateSubmission]
        metadata: dict[str, Any] = field(default_factory=dict)

    StrategyRuntime = Any  # type: ignore[misc,assignment]


OFFICIAL_REPOSITORY = "https://github.com/Continual-Intelligence/SEAL"
OFFICIAL_AUDIT_COMMIT = "6d9c9f9ee392c6cc618e771f399d436d190f6ca4"


def _new(record_type: type[Any], **values: Any) -> Any:
    parameters = inspect.signature(record_type).parameters
    return record_type(
        **{key: value for key, value in values.items() if key in parameters}
    )


@dataclass(frozen=True)
class PositiveExample:
    prompt: str
    code: str
    score: float
    attempt: int


class SEALMethod:
    """Reset-and-retrain positive-example LoRA SFT strategy for local HF models."""

    name = "seal"

    def __init__(
        self,
        *,
        lora_rank: int = 128,
        learning_rate: float = 1e-4,
        epochs: int = 2,
        max_sequence_length: int = 16_384,
    ) -> None:
        self.lora_rank = lora_rank
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.max_sequence_length = max_sequence_length
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompt_builder = PromptBuilder()
        self.examples: list[PositiveExample] = []
        self.training_events: list[dict[str, Any]] = []

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.examples.clear()
        self.training_events.clear()

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        if remaining_attempts < 1:
            raise ValueError("build_step requires a positive remaining_attempts budget")
        prompt = self._prompt(history)
        attempt = max((item.attempt for item in history), default=0) + 1
        request = self._request(prompt, attempt)
        return _new(
            StrategyStep,
            submissions=(
                _new(
                    CandidateSubmission, request=request, metadata={"attempt": attempt}
                ),
            ),
            metadata={"positive_examples": len(self.examples)},
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        new_examples = []
        for attempt in attempts:
            if attempt.success or attempt.score <= 0 or attempt.request is None:
                continue
            example = PositiveExample(
                prompt=attempt.request.prompt,
                code=attempt.code,
                score=attempt.score,
                attempt=attempt.attempt,
            )
            self.examples.append(example)
            new_examples.append(example)
        final_attempt = max((item.attempt for item in attempts), default=0)
        if new_examples and final_attempt < self._require_context().config.attempts:
            self._reset_and_train()

    def snapshot(self) -> dict[str, Any]:
        return {
            "official_repository": OFFICIAL_REPOSITORY,
            "official_audit_commit": OFFICIAL_AUDIT_COMMIT,
            "algorithm": "reset_lora_and_sft_on_accumulated_positive_examples",
            "positive_example_count": len(self.examples),
            "training_events": list(self.training_events),
            "lora_rank": self.lora_rank,
            "learning_rate": self.learning_rate,
            "epochs_per_retrain": self.epochs,
            "official_equivalence": False,
            "adaptation_note": (
                "PACE does not implement official self-edit generation or ReSTEM; positive "
                "Box2D-score code is direct SFT data and there are no geometric ARC augmentations."
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _prompt(self, history: Sequence[AttemptRecord]) -> str:
        context = self._require_context()
        if not history:
            return self.prompt_builder.initial(context.task_context)
        previous = history[-1]
        best = max(history, key=lambda item: item.score)
        arguments = dict(
            best_code=best.code,
            best_feedback=best.verification.feedback,
            previous_code=previous.code,
            previous_feedback=previous.verification.feedback,
            best_attempt=best.attempt,
            previous_attempt=previous.attempt,
        )
        if context.config.mode == RunMode.ADAPTATION:
            return self.prompt_builder.adaptation_revision(
                context.task_context,
                reference_code=context.reference_code or history[0].code,
                reference_feedback=context.reference_feedback
                or history[0].verification.feedback,
                **arguments,
            )
        return self.prompt_builder.revision(context.task_context, **arguments)

    def _request(self, prompt: str, attempt: int) -> GenerationRequest:
        config = self._require_context().config
        return GenerationRequest(
            prompt=prompt,
            seed=config.seed + attempt,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={"method": self.name, "attempt": attempt},
        )

    def _provider(self) -> Any:
        runtime = self.runtime
        provider = runtime.provider
        if provider is None:
            raise RuntimeError("SEAL requires StrategyRuntime.provider")
        load = getattr(provider, "_load", None)
        if not callable(load):
            raise RuntimeError(
                "SEAL requires the local-transformers provider; API models cannot be LoRA-trained"
            )
        load()
        return provider

    def _reset_and_train(self) -> None:
        """Reset LoRA, then perform response-only SFT on all accumulated examples."""

        try:
            import torch
            from peft import LoraConfig, PeftModel, get_peft_model
        except ImportError as exc:
            raise RuntimeError(
                "SEAL requires torch and peft in the local evaluation env"
            ) from exc

        provider = self._provider()
        model = provider._model
        tokenizer = provider._tokenizer
        if isinstance(model, PeftModel):
            model = model.unload()
        model = get_peft_model(
            model,
            LoraConfig(
                r=self.lora_rank,
                lora_alpha=max(16, self.lora_rank),
                lora_dropout=0.0,
                bias="none",
                task_type="CAUSAL_LM",
            ),
        )
        provider._model = model
        model.train()
        model.config.use_cache = False
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=self.learning_rate,
        )
        losses: list[float] = []
        for _ in range(self.epochs):
            for example in self.examples:
                input_ids, labels, attention_mask = self._encode_example(
                    tokenizer,
                    example.prompt,
                    example.code,
                    next(model.parameters()).device,
                )
                optimizer.zero_grad(set_to_none=True)
                output = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                output.loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [
                        parameter
                        for parameter in model.parameters()
                        if parameter.requires_grad
                    ],
                    1.0,
                )
                optimizer.step()
                losses.append(float(output.loss.detach().cpu()))
        model.eval()
        model.config.use_cache = True
        self.training_events.append(
            {
                "after_attempt": self.examples[-1].attempt,
                "examples": len(self.examples),
                "optimizer_updates": self.epochs * len(self.examples),
                "mean_loss": sum(losses) / len(losses) if losses else None,
            }
        )

    def _encode_example(
        self, tokenizer: Any, prompt: str, code: str, device: Any
    ) -> tuple[Any, Any, Any]:
        import torch

        messages = [{"role": "user", "content": prompt}]
        if hasattr(tokenizer, "apply_chat_template"):
            prefix = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            prefix = prompt + "\n"
        suffix = code + (tokenizer.eos_token or "")
        prefix_ids = tokenizer(prefix, add_special_tokens=True)["input_ids"]
        full = tokenizer(
            prefix + suffix,
            add_special_tokens=True,
            truncation=True,
            max_length=self.max_sequence_length,
            return_tensors="pt",
        )
        labels = full["input_ids"].clone()
        labels[:, : min(len(prefix_ids), labels.shape[1])] = -100
        if bool((labels != -100).sum() == 0):
            raise RuntimeError(
                "SEAL training example was truncated before the code response"
            )
        return (
            full["input_ids"].to(device),
            labels.to(device),
            full.get("attention_mask", torch.ones_like(full["input_ids"])).to(device),
        )

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("initialize() must be called before use")
        return self.context


Strategy = SEALMethod
Method = SEALMethod
