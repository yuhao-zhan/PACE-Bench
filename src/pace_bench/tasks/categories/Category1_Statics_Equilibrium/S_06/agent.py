def build_agent(sandbox):
    sandbox.add_block(-0.5, 0.11, 1.0, 0.2)
    sandbox.add_block(-0.4, 0.31, 1.0, 0.2)
    return None

def agent_action(sandbox, agent_body, step_count):
    pass

def build_agent_stage_1(sandbox):
    sandbox.add_block(-0.45, 0.11, 1.0, 0.2, density=120.0)
    sandbox.add_block(0.0, 0.31, 1.0, 0.2, density=50.0)
    return None

def agent_action_stage_1(sandbox, agent_body, step_count):
    pass

def build_agent_stage_2(sandbox):
    sandbox.add_block(-0.30, 0.11, 1.0, 0.2, density=167.5)
    sandbox.add_block(0.07, 0.31, 1.0, 0.2, density=167.5)
    return None

def agent_action_stage_2(sandbox, agent_body, step_count):
    pass

def build_agent_stage_3(sandbox):
    sandbox.add_block(-0.35, 0.11, 1.0, 0.2, density=32.5)
    sandbox.add_block(0.03, 0.31, 1.0, 0.2, density=32.5)
    return None

def agent_action_stage_3(sandbox, agent_body, step_count):
    pass

def build_agent_stage_4(sandbox):
    sandbox.add_block(-0.35, 0.11, 1.0, 0.2, density=80.0)
    sandbox.add_block(0.05, 0.31, 1.0, 0.2, density=80.0)
    return None

def agent_action_stage_4(sandbox, agent_body, step_count):
    pass
