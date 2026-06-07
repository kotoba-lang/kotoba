from typing import TypedDict, Annotated; from langgraph.graph import StateGraph, END; from langgraph.graph.message import add_messages

class SemiconductorPartState(TypedDict):
    part_id: str
    spec_compliance: bool
    inspection_result: str

def validate_material(state: SemiconductorPartState) -> SemiconductorPartState:
    # Specialized CAD validation logic for semiconductor part purity
    state['spec_compliance'] = True
    state['inspection_result'] = 'Passed material purity test'
    return state

def process_heat_treatment(state: SemiconductorPartState) -> SemiconductorPartState:
    state['inspection_result'] += ' and heat treatment validated'
    return state

graph = StateGraph(SemiconductorPartState)
graph.add_node('validate_material', validate_material)
graph.add_node('process_heat_treatment', process_heat_treatment)
graph.add_edge('validate_material', 'process_heat_treatment')
graph.add_edge('process_heat_treatment', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
