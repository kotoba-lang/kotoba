from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralOilState(TypedDict):
    product_id: str
    viscosity_index: float
    safety_check_passed: bool
    logistics_status: str

def validate_specs(state: MineralOilState) -> MineralOilState:
    # Specialized validation for Mineral Oil properties
    if state.get('viscosity_index', 0) > 0:
        state['safety_check_passed'] = True
    return state

def check_logistics(state: MineralOilState) -> MineralOilState:
    # Check for dangerous goods compliance
    state['logistics_status'] = 'COMPLIANT'
    return state

graph = StateGraph(MineralOilState)
graph.add_node('validate', validate_specs)
graph.add_node('logistics', check_logistics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)

graph = graph.compile()
