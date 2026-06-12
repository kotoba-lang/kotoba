from typing import TypedDict
from langgraph.graph import StateGraph, END

class LoomState(TypedDict):
    loom_model: str
    shaft_count: int
    is_configured: bool

async def validate_specs(state: LoomState):
    print(f'Validating specs for {state.get("loom_model")}...')
    return {'is_configured': state.get('shaft_count', 0) > 0}

async def check_readiness(state: LoomState):
    print('Checking weaving readiness...')
    return {'is_configured': True}

graph = StateGraph(LoomState)
graph.add_node('validate', validate_specs)
graph.add_node('setup', check_readiness)
graph.add_edge('validate', 'setup')
graph.add_edge('setup', END)
graph.set_entry_point('validate')
graph = graph.compile()
