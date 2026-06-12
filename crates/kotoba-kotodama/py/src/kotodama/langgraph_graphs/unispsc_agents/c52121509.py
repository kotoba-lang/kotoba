from typing import TypedDict
from langgraph.graph import StateGraph, END

class SheetProcurementState(TypedDict):
    material: str
    dimensions: str
    quality_score: float
    approved: bool

def validate_specs(state: SheetProcurementState):
    state['approved'] = state.get('quality_score', 0) > 0.8
    return state

def run_compliance(state: SheetProcurementState):
    print(f'Compliance check for {state.get("material")} material.')
    return state

graph = StateGraph(SheetProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', run_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
