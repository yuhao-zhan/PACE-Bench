"""PACE-Bench multi-turn, trajectory-level GRPO/PPO adaptation of RAGEN.

Two rollout episodes are advanced for two code-revision turns.  Both turns in an
episode receive the same normalized *episode return* advantage, then LoRA is updated
with asymmetric PPO clipping.  Thus a 20-attempt budget permits five online updates.
This is a small single-task adaptation of StarPO, not the distributed veRL stack.
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


OFFICIAL_REPOSITORY = "https://github.com/mll-lab-nu/RAGEN"
OFFICIAL_AUDIT_COMMIT = "20daedc47558e000f7de912b060646bf2e8026bd"


def _new(record_type: type[Any], **values: Any) -> Any:
    parameters = inspect.signature(record_type).parameters
    return record_type(
        **{key: value for key, value in values.items() if key in parameters}
    )


def trajectory_grpo_advantages(
    returns: Sequence[float], epsilon: float = 1e-6
) -> list[float]:
    """Normalize complete episode returns; never group individual turns separately."""

    if not returns:
        return []
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    standard_deviation = math.sqrt(variance)
    if standard_deviation < epsilon:
        return [0.0 for _ in returns]
    return [(value - mean) / (standard_deviation + epsilon) for value in returns]


@dataclass
class Episode:
    episode_id: int
    turns: list[AttemptRecord]

    @property
    def total_return(self) -> float:
        reward = 0.0
        for turn in self.turns:
            if turn.verification.error and not turn.code:
                reward -= 0.1
            reward += max(-1.0, min(1.0, turn.score / 100.0))
        return reward


class RAGENMethod:
    name = "ragen"

    def __init__(
        self,
        *,
        episodes_per_update: int = 2,
        turns_per_episode: int = 2,
        lora_rank: int = 64,
        learning_rate: float = 1e-5,
        ppo_epochs: int = 2,
        clip_low: float = 0.2,
        clip_high: float = 0.28,
        max_sequence_length: int = 16_384,
    ) -> None:
        if episodes_per_update < 2 or turns_per_episode != 2:
            raise ValueError("PACE RAGEN requires >=2 episodes and exactly 2 turns")
        self.episodes_per_update = episodes_per_update
        self.turns_per_episode = turns_per_episode
        self.lora_rank = lora_rank
        self.learning_rate = learning_rate
        self.ppo_epochs = ppo_epochs
        self.clip_low = clip_low
        self.clip_high = clip_high
        self.max_sequence_length = max_sequence_length
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompt_builder = PromptBuilder()
        self.first_turns: list[AttemptRecord] = []
        self.phase = 0
        self.update_index = 0
        self.training_events: list[dict[str, Any]] = []

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.first_turns.clear()
        self.phase = 0
        self.update_index = 0
        self.training_events.clear()

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        count = min(
            self.episodes_per_update,
            remaining_attempts if self.phase == 1 else max(1, remaining_attempts // 2),
        )
        if count <= 0:
            raise ValueError("build_step requires a positive remaining_attempts budget")
        submissions: list[CandidateSubmission] = []
        if self.phase == 0:
            prompt = self._episode_start_prompt(history)
            for episode_id in range(count):
                submissions.append(
                    self._submission(prompt, episode_id=episode_id, turn=1)
                )
        else:
            for episode_id, parent in enumerate(self.first_turns[:count]):
                submissions.append(
                    self._submission(
                        self._turn_two_prompt(parent, history),
                        episode_id=episode_id,
                        turn=2,
                    )
                )
        return _new(
            StrategyStep,
            submissions=tuple(submissions),
            metadata={"update": self.update_index + 1, "turn": self.phase + 1},
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        batch = list(attempts)
        if self.phase == 0:
            self.first_turns = batch
            self.phase = 1
            return
        episodes = [
            Episode(index, [first, second])
            for index, (first, second) in enumerate(zip(self.first_turns, batch))
        ]
        final_attempt = max((item.attempt for item in batch), default=0)
        if final_attempt < self._require_context().config.attempts:
            self._trajectory_update(episodes)
        else:
            self.training_events.append(
                {"skipped": "no later candidate after final budget"}
            )
        self.first_turns = []
        self.phase = 0
        self.update_index += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "official_repository": OFFICIAL_REPOSITORY,
            "official_audit_commit": OFFICIAL_AUDIT_COMMIT,
            "algorithm": "two_episode_two_turn_trajectory_grpo_with_ppo_clip",
            "online_updates": self.update_index,
            "episodes_per_update": self.episodes_per_update,
            "turns_per_episode": self.turns_per_episode,
            "training_events": list(self.training_events),
            "lora_rank": self.lora_rank,
            "learning_rate": self.learning_rate,
            "ppo_epochs": self.ppo_epochs,
            "official_equivalence": False,
            "adaptation_note": (
                "Single-task LoRA replaces distributed veRL/full fine-tuning; episode-level "
                "returns and two-turn response credit preserve the StarPO trajectory unit."
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _submission(
        self, prompt: str, *, episode_id: int, turn: int
    ) -> CandidateSubmission:
        config = self._require_context().config
        seed = config.seed + (self.update_index + 1) * 10_000 + turn * 100 + episode_id
        request = GenerationRequest(
            prompt=prompt,
            seed=seed,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={
                "method": self.name,
                "update": self.update_index + 1,
                "episode_id": episode_id,
                "turn": turn,
            },
        )
        return _new(
            CandidateSubmission,
            request=request,
            metadata={"episode_id": episode_id, "turn": turn},
        )

    def _episode_start_prompt(self, history: Sequence[AttemptRecord]) -> str:
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

    def _turn_two_prompt(
        self, first_turn: AttemptRecord, history: Sequence[AttemptRecord]
    ) -> str:
        context = self._require_context()
        global_best = max([*history, *self.first_turns], key=lambda item: item.score)
        arguments = dict(
            best_code=global_best.code,
            best_feedback=global_best.verification.feedback,
            previous_code=first_turn.code,
            previous_feedback=first_turn.verification.feedback,
            best_attempt=global_best.attempt,
            previous_attempt=first_turn.attempt,
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

    def _trajectory_update(self, episodes: Sequence[Episode]) -> None:
        returns = [episode.total_return for episode in episodes]
        advantages = trajectory_grpo_advantages(returns)
        if not any(abs(value) > 1e-9 for value in advantages):
            self.training_events.append(
                {
                    "returns": returns,
                    "advantages": advantages,
                    "skipped": "constant_returns",
                }
            )
            return
        provider = self._provider()
        model = self._ensure_lora(provider)
        tokenizer = provider._tokenizer
        samples = []
        for episode, advantage in zip(episodes, advantages, strict=True):
            for turn in episode.turns:
                if turn.request is not None and turn.generation is not None:
                    response = turn.generation.text or turn.code
                    samples.append(
                        self._encode(
                            tokenizer, turn.request.prompt, response, advantage, model
                        )
                    )
        if not samples:
            self.training_events.append(
                {
                    "returns": returns,
                    "advantages": advantages,
                    "skipped": "no_generation_text",
                }
            )
            return
        mean_loss = self._ppo_update(model, samples)
        self.training_events.append(
            {
                "returns": returns,
                "advantages": advantages,
                "samples": len(samples),
                "ppo_epochs": self.ppo_epochs,
                "mean_loss": mean_loss,
            }
        )

    def _provider(self) -> Any:
        provider = self.runtime.provider if self.runtime is not None else None
        load = getattr(provider, "_load", None)
        if provider is None or not callable(load):
            raise RuntimeError(
                "RAGEN requires StrategyRuntime.provider using local-transformers"
            )
        load()
        return provider

    def _ensure_lora(self, provider: Any) -> Any:
        try:
            from peft import LoraConfig, PeftModel, get_peft_model
        except ImportError as exc:
            raise RuntimeError("RAGEN requires peft") from exc
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
                "RAGEN response was truncated before its trainable tokens"
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

    def _ppo_update(self, model: Any, samples: Sequence[dict[str, Any]]) -> float:
        import torch

        model.train()
        model.config.use_cache = False
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=self.learning_rate,
        )
        losses: list[float] = []
        for _ in range(self.ppo_epochs):
            for sample in samples:
                new_log_probs = self._token_log_probs(
                    model, sample["input_ids"], sample["attention_mask"]
                )
                ratio = torch.exp(new_log_probs - sample["old_log_probs"])
                advantage = torch.as_tensor(sample["advantage"], device=ratio.device)
                unclipped = ratio * advantage
                clipped = (
                    torch.clamp(ratio, 1.0 - self.clip_low, 1.0 + self.clip_high)
                    * advantage
                )
                mask = sample["response_mask"]
                loss = -(torch.minimum(unclipped, clipped) * mask).sum() / mask.sum()
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

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("initialize() must be called before use")
        return self.context


Strategy = RAGENMethod
Method = RAGENMethod
