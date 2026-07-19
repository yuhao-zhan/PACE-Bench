import os

import json

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pace_bench.tasks.primitives_api import API_INTRO

with open(os.path.join(os.path.dirname(__file__), '..', '..', 'primitives_api.json'), 'r') as f:
    _api_data = json.load(f)

if 'E_03' in _api_data and 'API_INTRO' in _api_data['E_03']:
    del _api_data['E_03']['API_INTRO']

TASK_PROMPT = {
    "task_description": """
Design a controller for a sled to navigate through a low-friction environment and pass through checkpoints.

- **Sled**: A sliding body subject to thrust and minimal friction. It starts at position (x=8.0 m, y=2.0 m).
- **Checkpoints** (must be passed in order):
  - **First checkpoint (Alpha)**: Sled center must enter the zone x in [17.5, 19.0] m, y in [3.8, 4.5] m.
  - **Second checkpoint (Beta)**: Sled center must enter the zone x in [23.0, 24.5] m, y in [2.5, 3.2] m.
- **Reverse-Thrust Zone**: In the region x in [20.0, 25.0] m, horizontal thrust applied to the sled is reversed (sign-flipped) — a rightward force becomes leftward and vice versa.
- **Vertical-Reverse Zone**: In the region x in [26.5, 28.5] m, vertical thrust effect is negated — upward thrust becomes downward and vice versa.
- **Speed-Limit Zone**: In the region x in [22.0, 26.0] m, if the sled's speed exceeds 4.0 m/s (originally 4.0 m/s), severe velocity damping is applied, reducing speed dramatically.
- **Final target**: Sled center must enter the zone x in [28, 32] m, y in [2.2, 2.8] m.
- **Time limit**: The task must be completed within 10,000 simulation steps; the run terminates after this limit and failure is declared if the objective is not met by then.

Design a control loop that:
1. Directs the sled toward the next checkpoint.
2. Manages speed and orientation to successfully pass through checkpoints.
3. Adapts to the low-friction dynamics of the environment.
""",
    "success_criteria": """

1. **Checkpoint Completion**: Sled passes through both required checkpoints in order (Alpha, then Beta).
2. **Target Reach**: Sled center enters the final target zone (x in [28, 32], y in [2.2, 2.8]).
3. **Efficiency**: Reaches the final target within 10,000 simulation steps.

- **APIs**: Use only the primitives documented below.
""",
    'primitives_api': API_INTRO + '\n' + '\n\n'.join(_api_data['E_03'].values()),

}
