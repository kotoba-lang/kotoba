from typing import TypedDict
from langgraph.graph import StateGraph, END

class OrganizerState(TypedDict):
    material: str
    max_load: float
    is_waterproof: bool

async def validate_spec(state: OrganizerState) -> OrganizerState:
    if not state.get('material'): raise ValueError('Missing material')
    return state

async def check_compatibility(state: OrganizerState) -> OrganizerState:
    print(f'Validating load capacity for {state.get("max_load")}kg')
    return state

graph = StateGraph(OrganizerState)
graph.add_node('validate_spec', validate_spec)
graph.add_node('compatibility_check', check_compatibility)
graph.set_entry_point('validate_spec')
graph.add_edge('validate_spec', 'compatibility_check')
graph.add_edge('compatibility_check', END)
graph = graph.compile()
