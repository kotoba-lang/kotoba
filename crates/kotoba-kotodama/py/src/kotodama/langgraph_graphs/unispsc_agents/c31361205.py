from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_spec: str
    torque_requirements: float
    validation_passed: bool

async def validate_specs(state: AssemblyState):
    state['validation_passed'] = bool(state.get('material_spec') and state.get('torque_requirements', 0) > 0)
    return state

async def route_inspection(state: AssemblyState):
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
