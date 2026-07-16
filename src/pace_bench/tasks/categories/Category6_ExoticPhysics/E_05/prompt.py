import os

import json

import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pace_bench.tasks.primitives_api import API_INTRO

with open(os.path.join(os.path.dirname(__file__), '..', '..', 'primitives_api.json'), 'r') as f:
    _api_data = json.load(f)

if 'E_05' in _api_data and 'API_INTRO' in _api_data['E_05']:
    del _api_data['E_05']['API_INTRO']

TASK_PROMPT = {
    "task_description": """
Design a controller to navigate a body through a complex, invisible magnetic force field to a target zone.

- **Body**: A dynamic object starting at x=8.0m, y=5.0m.
- **Force Fields**: Numerous invisible repulsive and attractive points are scattered throughout the environment.
- **Gates**: Some force fields oscillate in intensity, creating "gates" that are only passable at certain times.
- **Target Zone**: Reach the area x in [28.0, 32.0] m and y in [6.0, 9.0] m.
- **Forbidden Region (pit)**: If the body enters the region x in [16.0, 24.0] m with y < 5.5 m before reaching the target, the run fails immediately.
- **Maximum Thrust**: The thrust vector magnitude must not exceed 165.0 (engine limit).
- **Goal**: Navigate the body to the target zone by applying thrust to overcome repulsive forces and time the passage through gates.

Design a control loop that:
1. Applies thrust to move the body toward the target.
2. Uses position and velocity feedback to identify and overcome repulsive "peaks" or local minima.
3. Times the approach to pass through oscillating gates when their repulsive force is weak.
4. Successfully reaches the target zone within the simulation time limit.
""",
    "success_criteria": """

1. **Target Reach**: Body reaches the target zone (x in [28.0, 32.0] m, y in [6.0, 9.0] m).
2. **Efficiency**: Task completed within 10,000 simulation steps.

- **Starting Position**: Body starts at x = 8.0 m, y = 5.0 m.
- **Maximum Thrust**: The thrust vector magnitude must not exceed 165.0 (engine limit).
- **Simulation Time Budget**: The task must be completed within 10,000 simulation steps (timeout failure otherwise).
- **Forbidden Region (pit)**: If the body enters the region x in [16.0, 24.0] m with y < 5.5 m before reaching the target, the run fails immediately.
- **Ceiling**: There is a ceiling at y = 9.7 m (maximum y-bound) — the body must stay below it to remain in navigable space.
- **APIs**: Use only the primitives documented below.
""",
    'primitives_api': API_INTRO + '\n' + '\n\n'.join(_api_data['E_05'].values()),

}
