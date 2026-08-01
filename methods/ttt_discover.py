"""PACE-Bench paper adaptation of TTT-Discover.

Each of five budgeted iterations submits four Box2D candidates, computes
leave-one-out entropic advantages, and—when rewards differ—runs 50 LoRA training
epochs with the importance-sampling objective. Feedback-conditioned PUCT expansion
selects the state for the next candidate group.
"""

from __future__ import annotations

import inspect
import math
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


OFFICIAL_REPOSITORY = "https://github.com/test-time-training/discover"
OFFICIAL_AUDIT_COMMIT = "6c40e82dab9d5de7416ac873ad5cd3106084aaed"


def _new(record_type: type[Any], **values: Any) -> Any:
    parameters = inspect.signature(record_type).parameters
    return record_type(
        **{key: value for key, value in values.items() if key in parameters}
    )


def _softmax(values: Sequence[float]) -> list[float]:
    maximum = max(values)
    exponentials = [math.exp(value - maximum) for value in values]
    total = sum(exponentials)
    return [value / total for value in exponentials]


def solve_adaptive_beta(
    rewards: Sequence[float], *, target_kl: float = math.log(2.0), beta_max: float = 1e6
) -> float:
    """Find beta such that KL(softmax(beta*r) || uniform) is target_kl."""

    if len(rewards) < 2 or max(rewards) - min(rewards) < 1e-12:
        return 0.0
    target = min(target_kl, math.log(len(rewards)) - 1e-9)

    def divergence(beta: float) -> float:
        probabilities = _softmax([beta * value for value in rewards])
        return sum(
            probability * math.log(max(probability * len(rewards), 1e-300))
            for probability in probabilities
        )

    low, high = 0.0, 1.0
    while high < beta_max and divergence(high) < target:
        high *= 2.0
    high = min(high, beta_max)
    for _ in range(60):
        middle = (low + high) / 2.0
        if divergence(middle) < target:
            low = middle
        else:
            high = middle
    return high


def adaptive_entropic_advantages(rewards: Sequence[float]) -> tuple[list[float], float]:
    """Official leave-one-out entropic advantages with an adaptive beta."""

    if not rewards:
        return [], 0.0
    beta = solve_adaptive_beta(rewards)
    shifted = [value - max(rewards) for value in rewards]
    exponentials = [math.exp(beta * value) for value in shifted]
    if len(rewards) == 1:
        return [0.0], beta
    advantages = []
    for index, value in enumerate(exponentials):
        leave_one_out = (sum(exponentials) - value) / (len(exponentials) - 1)
        advantages.append(value / (leave_one_out + 1e-12) - 1.0)
    return advantages, beta


@dataclass
class ArchiveNode:
    attempt: AttemptRecord
    visits: int = 0
    best_child_score: float | None = None
    parent_attempt: int | None = None

    @property
    def q_value(self) -> float:
        return (
            self.best_child_score
            if self.best_child_score is not None
            else self.attempt.score
        )


class TTTDiscoverMethod:
    name = "ttt_discover"

    def __init__(
        self,
        *,
        group_size: int = 4,
        training_epochs: int = 50,
        puct_c: float = 1.0,
        archive_size: int = 1_000,
        lora_rank: int = 32,
        learning_rate: float = 4e-5,
        max_sequence_length: int = 16_384,
    ) -> None:
        if group_size < 2 or training_epochs < 1:
            raise ValueError("group_size must be >=2 and training_epochs positive")
        self.group_size = group_size
        self.training_epochs = training_epochs
        self.puct_c = puct_c
        self.archive_size = archive_size
        self.lora_rank = lora_rank
        self.learning_rate = learning_rate
        self.max_sequence_length = max_sequence_length
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompt_builder = PromptBuilder()
        self.archive: dict[int, ArchiveNode] = {}
        self.selected_parent: ArchiveNode | None = None
        self.online_steps = 0
        self.total_verifications = 0
        self.training_events: list[dict[str, Any]] = []

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.archive.clear()
        self.selected_parent = None
        self.online_steps = 0
        self.total_verifications = 0
        self.training_events.clear()

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        if remaining_attempts <= 0:
            raise ValueError("build_step requires a positive remaining_attempts budget")
        self._seed_archive(history)
        self.selected_parent = self._sample_puct_parent()
        count = min(self.group_size, remaining_attempts)
        prompt = self._prompt_from_parent(self.selected_parent.attempt, history)
        config = self._require_context().config
        submissions = []
        for sample_index in range(count):
            request = GenerationRequest(
                prompt=prompt,
                seed=config.seed + (self.online_steps + 1) * 10_000 + sample_index,
                temperature=config.temperature,
                top_p=config.top_p,
                max_tokens=config.max_tokens,
                metadata={
                    "method": self.name,
                    "online_step": self.online_steps + 1,
                    "sample": sample_index,
                    "parent_attempt": self.selected_parent.attempt.attempt,
                },
            )
            submissions.append(
                _new(CandidateSubmission, request=request, metadata=request.metadata)
            )
        return _new(
            StrategyStep,
            submissions=tuple(submissions),
            metadata={
                "online_step": self.online_steps + 1,
                "parent_attempt": self.selected_parent.attempt.attempt,
                "verification_cost": len(submissions),
            },
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        batch = list(attempts)
        if not batch:
            return
        parent = self.selected_parent
        if parent is None:
            raise RuntimeError(
                "observe() called before build_step() selected a PUCT parent"
            )
        parent.visits += 1
        parent.best_child_score = max(
            [parent.best_child_score or float("-inf"), *[item.score for item in batch]]
        )
        for attempt in batch:
            self.archive[attempt.attempt] = ArchiveNode(
                attempt=attempt, parent_attempt=parent.attempt.attempt
            )
        self._prune_archive()
        rewards = [item.score / 100.0 for item in batch]
        advantages, beta = adaptive_entropic_advantages(rewards)
        self.total_verifications += len(batch)
        self.online_steps += 1
        final_attempt = max((item.attempt for item in batch), default=0)
        if final_attempt >= self._require_context().config.attempts:
            self.training_events.append(
                {
                    "step": self.online_steps,
                    "rewards": rewards,
                    "adaptive_beta": beta,
                    "advantages": advantages,
                    "skipped": "no later candidate after final budget",
                }
            )
            return
        if any(abs(value) > 1e-9 for value in advantages):
            mean_loss = self._importance_sampling_update(batch, advantages)
            self.training_events.append(
                {
                    "step": self.online_steps,
                    "rewards": rewards,
                    "adaptive_beta": beta,
                    "advantages": advantages,
                    "training_epochs": self.training_epochs,
                    "mean_loss": mean_loss,
                }
            )
        else:
            self.training_events.append(
                {
                    "step": self.online_steps,
                    "rewards": rewards,
                    "adaptive_beta": beta,
                    "advantages": advantages,
                    "skipped": "constant_reward_group; next step expands from PUCT archive",
                }
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "official_repository": OFFICIAL_REPOSITORY,
            "official_audit_commit": OFFICIAL_AUDIT_COMMIT,
            "algorithm": "puct_archive_plus_adaptive_entropic_online_lora_rl",
            "online_iterations": self.online_steps,
            "training_epochs": self.training_epochs,
            "total_verifications": self.total_verifications,
            "group_size": self.group_size,
            "archive_size": len(self.archive),
            "training_events": list(self.training_events),
            "lora_rank": self.lora_rank,
            "learning_rate": self.learning_rate,
            "official_equivalence": False,
            "adaptation_note": (
                "PACE uses four rollouts and in-process HF LoRA rather than the official "
                "64x8 Tinker service batch. The paper-specified 50 training epochs are "
                "applied after each non-constant group when another candidate can benefit."
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _seed_archive(self, history: Sequence[AttemptRecord]) -> None:
        for attempt in history:
            self.archive.setdefault(attempt.attempt, ArchiveNode(attempt=attempt))
        if not self.archive:
            raise RuntimeError(
                "TTT-Discover requires a reference or previous attempt as state"
            )

    def _sample_puct_parent(self) -> ArchiveNode:
        nodes = list(self.archive.values())
        values = [node.attempt.score for node in nodes]
        scale = max(max(values) - min(values), 1e-6)
        ranked = sorted(
            range(len(nodes)), key=lambda index: values[index], reverse=True
        )
        rank_weight = {index: len(nodes) - rank for rank, index in enumerate(ranked)}
        weight_sum = sum(rank_weight.values())
        total_visits = sum(node.visits for node in nodes)

        def score(index: int) -> float:
            node = nodes[index]
            prior = rank_weight[index] / weight_sum
            bonus = (
                self.puct_c
                * scale
                * prior
                * math.sqrt(1.0 + total_visits)
                / (1.0 + node.visits)
            )
            return node.q_value + bonus

        return nodes[max(range(len(nodes)), key=score)]

    def _prompt_from_parent(
        self, parent: AttemptRecord, history: Sequence[AttemptRecord]
    ) -> str:
        context = self._require_context()
        best = max(self.archive.values(), key=lambda node: node.attempt.score).attempt
        arguments = dict(
            best_code=best.code,
            best_feedback=best.verification.feedback,
            previous_code=parent.code,
            previous_feedback=parent.verification.feedback,
            best_attempt=best.attempt,
            previous_attempt=parent.attempt,
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

    def _prune_archive(self) -> None:
        if len(self.archive) <= self.archive_size:
            return
        keep = sorted(
            self.archive.values(), key=lambda node: node.attempt.score, reverse=True
        )[: self.archive_size]
        self.archive = {node.attempt.attempt: node for node in keep}

    def _provider(self) -> Any:
        provider = self.runtime.provider if self.runtime is not None else None
        load = getattr(provider, "_load", None)
        if provider is None or not callable(load):
            raise RuntimeError(
                "TTT-Discover requires StrategyRuntime.provider using local-transformers"
            )
        load()
        return provider

    def _ensure_lora(self, provider: Any) -> Any:
        try:
            from peft import LoraConfig, PeftModel, get_peft_model
        except ImportError as exc:
            raise RuntimeError("TTT-Discover requires peft") from exc
        model = provider._model
        if not isinstance(model, PeftModel):
            model = get_peft_model(
                model,
                LoraConfig(
                    r=self.lora_rank,
                    lora_alpha=self.lora_rank,
                    lora_dropout=0.0,
                    bias="none",
                    task_type="CAUSAL_LM",
                ),
            )
            provider._model = model
        return model

    def _importance_sampling_update(
        self, attempts: Sequence[AttemptRecord], advantages: Sequence[float]
    ) -> float:
        import torch

        provider = self._provider()
        model = self._ensure_lora(provider)
        tokenizer = provider._tokenizer
        samples = []
        for attempt, advantage in zip(attempts, advantages, strict=True):
            if attempt.request is None or attempt.generation is None:
                continue
            response = attempt.generation.text or attempt.code
            samples.append(
                self._encode(
                    tokenizer, attempt.request.prompt, response, advantage, model
                )
            )
        if not samples:
            return 0.0
        model.train()
        model.config.use_cache = False
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=self.learning_rate,
            betas=(0.9, 0.95),
        )
        losses = []
        for _ in range(self.training_epochs):
            for sample in samples:
                new_log_probs = self._token_log_probs(
                    model, sample["input_ids"], sample["attention_mask"]
                )
                ratio = torch.exp(new_log_probs - sample["old_log_probs"])
                mask = sample["response_mask"]
                loss = -(ratio * sample["advantage"] * mask).sum() / mask.sum()
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [
                        parameter
                        for parameter in model.parameters()
                        if parameter.requires_grad
                    ],
                    1.0,
                )
                optimizer.step()
                losses.append(float(loss.detach().cpu()))
        model.eval()
        model.config.use_cache = True
        return sum(losses) / len(losses)

    def _encode(
        self, tokenizer: Any, prompt: str, response: str, advantage: float, model: Any
    ) -> dict[str, Any]:
        import torch

        prefix = (
            tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
            if hasattr(tokenizer, "apply_chat_template")
            else prompt + "\n"
        )
        prefix_length = len(tokenizer(prefix, add_special_tokens=True)["input_ids"])
        encoded = tokenizer(
            prefix + response + (tokenizer.eos_token or ""),
            add_special_tokens=True,
            truncation=True,
            max_length=self.max_sequence_length,
            return_tensors="pt",
        )
        device = next(model.parameters()).device
        input_ids = encoded["input_ids"].to(device)
        attention_mask = encoded.get("attention_mask", torch.ones_like(input_ids)).to(
            device
        )
        response_mask = torch.zeros(input_ids.shape[1] - 1, device=device)
        response_mask[max(0, prefix_length - 1) :] = 1.0
        if response_mask.sum() == 0:
            raise RuntimeError(
                "TTT-Discover response was truncated before trainable tokens"
            )
        model.eval()
        with torch.no_grad():
            old_log_probs = self._token_log_probs(
                model, input_ids, attention_mask
            ).detach()
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "response_mask": response_mask,
            "old_log_probs": old_log_probs,
            "advantage": advantage,
        }

    @staticmethod
    def _token_log_probs(model: Any, input_ids: Any, attention_mask: Any) -> Any:
        import torch

        logits = model(input_ids=input_ids, attention_mask=attention_mask).logits[
            :, :-1
        ]
        targets = input_ids[:, 1:]
        return (
            torch.log_softmax(logits.float(), dim=-1)
            .gather(-1, targets.unsqueeze(-1))
            .squeeze(-1)[0]
        )

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("initialize() must be called before use")
        return self.context


Strategy = TTTDiscoverMethod
Method = TTTDiscoverMethod
