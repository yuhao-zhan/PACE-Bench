import os

import json

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pace_bench.tasks.primitives_api import API_INTRO

with open(os.path.join(os.path.dirname(__file__), '..', '..', 'primitives_api.json'), 'r') as f:
    _api_data = json.load(f)

if 'E_01' in _api_data and 'API_INTRO' in _api_data['E_01']:
    del _api_data['E_01']['API_INTRO']

TASK_PROMPT = {
    "task_description": """
Design a stable structure that stays within the boundaries of a bounded arena under time-varying gravity.

- **Arena**: A bounded region with x in [0, 40] m and y in [0, 20] m.
- **Gravity**: The gravity vector oscillates periodically between downward and upward directions; the magnitude varies over time. Discover the stage-specific oscillation parameters through environmental feedback.
- **Obstacles**: Three fixed obstacle strips are embedded in the arena. No beam center may lie inside any obstacle zone (structure overlapping any zone causes failure). Obstacle 1: x ∈ [18.0, 22.0], y ∈ [9.75, 10.25] m. Obstacle 2: x ∈ [14.0, 26.0], y ∈ [12.75, 13.25] m. Obstacle 3: x ∈ [18.5, 19.5], y ∈ [13.75, 14.25] m.
- **Build Zone**: Structure must be built within x=[12.0, 28.0], y=[6.0, 18.0].
- **Beam dimensions**: Each beam's width and height must be between 0.1 m and 5.0 m (enforced by the simulator).
- **Forbidden zones**: Two forbidden regions disallow beam centers — placement there causes immediate failure. Forbidden Zone 1: x ∈ [19.0, 20.0], y ∈ [14.5, 15.5] m. Forbidden Zone 2: x ∈ [18.0, 21.0], y ∈ [15.9, 16.1] m.
- **Anchors**: You can anchor your structure to the floor, ceiling, or walls by adding joints with `body_b=None` at appropriate coordinates.
- **Joint strength**: Joints have no force limit in the default configuration (they do not break from overload); some environment stages may introduce a finite joint breaking threshold — discover the actual limit from feedback if joints fail unexpectedly.
- **Surface Traction**: Arena surfaces and obstacles have a friction coefficient (discover the actual value from feedback). Zero friction eliminates surface grip entirely.
- **Motion Damping**: Linear and angular damping may differ from standard values (discover the actual value from feedback); negative values inject energy into the system and cause vibrations to grow.
- **Simulation**: The simulation runs for 2500 steps. Success is evaluated at the end; the structure must remain in bounds and intact for the full run.

Design a structure that:
1. Remains entirely within the arena boundaries throughout the simulation despite gravity inversions.
2. Avoids overlapping with the fixed obstacles.
3. Maintains structural integrity (joints must not break under the alternating loads).
""",
    "success_criteria": """

1. **Containment**: No part of the structure (or any dynamic bodies) leaves the arena bounds.
2. **Integrity**: The structure remains intact; no joints are broken.

- **Simulation length**: In the base environment the simulation runs for 2500 steps; you must maintain containment and integrity for the full run.
- **Mass Budget**: Total structure mass must not exceed 200.0 kg.
- **Beam Limit**: Maximum 12 beams (discover the limit from feedback).
- **Joint strength**: Joints have no force limit in the default configuration (they do not break from overload); some environment stages may introduce a finite joint breaking threshold — discover the actual limit from feedback if joints fail unexpectedly.
- **Beam size**: Width and height per beam in [0.1, 5.0] m.
- **Surface Traction**: Arena surfaces and obstacles have a friction coefficient (discover the actual value from feedback). Zero friction eliminates surface grip entirely.
- **Motion Damping**: Linear and angular damping may differ from standard values (discover the actual value from feedback); negative values inject energy into the system and cause vibrations to grow.
- **APIs**: Use only the primitives documented below.
""",
    'primitives_api': API_INTRO + '\n' + '\n\n'.join(_api_data['E_01'].values()),

}
