from __future__ import annotations

import re

from typing import Any, Dict, List

_DEFAULT_IMPULSE_MAGNITUDE = 1.5

_DEFAULT_IMPULSE2_MAGNITUDE = 0.55

_DEFAULT_DECEL_DAMPING = 3.2

_DEFAULT_MUD_DAMPING = 4.2

_DEFAULT_GRAVITY = (0, -10.0)

def update_task_description_for_visible_changes(
    base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,
    **kwargs,

) -> str:
    if "(originally " in base_description and " in the source environment)" in base_description:
        raise ValueError("Description already appears to contain source-environment annotations. Refusing to double-mutate.")
    description = base_description
    target = target_terrain_config or {}
    base = base_terrain_config or {}
    target_imp = target.get("impulse_magnitude", _DEFAULT_IMPULSE_MAGNITUDE)
    base_imp = base.get("impulse_magnitude", _DEFAULT_IMPULSE_MAGNITUDE)
    if target_imp != _DEFAULT_IMPULSE_MAGNITUDE:
        pattern = r"(- \*\*First impulse zone\*\*: x=\[8\.0, 9\.0\] m; a one-time backward impulse of magnitude )(\d+\.?\d*)( N·s is applied when the cart first enters\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_imp:.2g} (originally {base_imp:.2g} in the source environment){m.group(3)}",
                description,
            )
    target_imp2 = target.get("impulse2_magnitude", _DEFAULT_IMPULSE2_MAGNITUDE)
    base_imp2 = base.get("impulse2_magnitude", _DEFAULT_IMPULSE2_MAGNITUDE)
    if target_imp2 != _DEFAULT_IMPULSE2_MAGNITUDE:
        pattern = r"(- \*\*Second impulse zone\*\*: x=\[10\.5, 11\.0\] m; a one-time backward impulse of magnitude )(\d+\.?\d*)( N·s is applied when the cart first enters\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_imp2:.2g} (originally {base_imp2:.2g} in the source environment){m.group(3)}",
                description,
            )
    target_mud = target.get("mud_damping", _DEFAULT_MUD_DAMPING)
    base_mud = base.get("mud_damping", _DEFAULT_MUD_DAMPING)
    if target_mud != _DEFAULT_MUD_DAMPING:
        pattern = r"(- \*\*Mud zone\*\*: x=\[5\.5, 7\.5\] m; linear velocity damping coefficient )(\d+\.?\d*)( N·s/m applied while the cart is in this zone\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_mud:.2g} (originally {base_mud:.2g} in the source environment){m.group(3)}",
                description,
            )
    target_dec = target.get("decel_damping", _DEFAULT_DECEL_DAMPING)
    base_dec = base.get("decel_damping", _DEFAULT_DECEL_DAMPING)
    if target_dec != _DEFAULT_DECEL_DAMPING:
        pattern = r"(- \*\*Decel zone\*\*: x=\[9\.5, 11\.0\] m; linear velocity damping coefficient )(\d+\.?\d*)( N·s/m applied while the cart is in this zone\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_dec:.2g} (originally {base_dec:.2g} in the source environment){m.group(3)}",
                description,
            )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    **kwargs,

) -> str:
    return base_success_criteria

_D03_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **First impulse zone**: The magnitude of the backward impulse applied in the first track zone may vary.
- **Second impulse zone**: The magnitude of the backward impulse applied in the second track zone may vary.
- **Ambient Resistance**: Linear or angular damping across the environment may be altered, causing the cart to shed speed differently.
- **Deceleration Zone Damping**: The resistance within specific slowing zones may have been adjusted, altering how effectively the cart is braked.
- **Mud Zone Damping**: The linear velocity damping applied within the mud zone may have been adjusted, altering how much speed the cart loses in the early phase.
- **Gravity**: Changes in the gravitational field may affect the effective weight and friction of the cart as it moves.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""

def get_d03_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Massive first impulse",
            "mutation_description": "First impulse magnitude massively increased; requires forward thrust to survive speed trap v(9)>=2.8.",
            "task_description_suffix": _D03_SUFFIX,
            "terrain_config": {
                "impulse_magnitude": 40.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Extreme ambient linear drag",
            "mutation_description": "Global linear damping set to a catastrophic level where the cart loses 95% of its speed per second of travel. Even with maximum beam mass the cart cannot coast through to the speed trap (v >= 2.8 at x=9) without sustained forward propulsion. Every meter of unpowered travel halves the remaining speed.",
            "task_description_suffix": _D03_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "linear_damping": 5.0,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Extreme resistance cascade",
            "mutation_description": "Massively amplified impulses, severe mud and decel zone damping, plus aggressive global linear drag. Initial reference speeds plummet below threshold; requires dense heavy build plus constant forward propulsion with careful phase-dependent speed modulation.",
            "task_description_suffix": _D03_SUFFIX,
            "terrain_config": {
                "impulse_magnitude": 30.0,
                "impulse2_magnitude": 4.0,
                "decel_damping": 12.0,
                "mud_damping": 10.0,
            },
            "physics_config": {
                "linear_damping": 2.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Heavy world and strong impulses",
            "mutation_description": "Gravity increased, both impulses and decel damping stronger, plus ambient damping; full profile and phase must be re-tuned.",
            "task_description_suffix": _D03_SUFFIX,
            "terrain_config": {
                "impulse_magnitude": 2.6,
                "impulse2_magnitude": 0.95,
                "decel_damping": 4.5,
            },
            "physics_config": {
                "gravity": (0, -12),
                "linear_damping": 0.4,
                "angular_damping": 0.4,
            },
        },
    ]
