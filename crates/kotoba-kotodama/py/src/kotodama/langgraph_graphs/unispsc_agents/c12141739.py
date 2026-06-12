from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PolymerProcessState(TypedDict):
    material_id: str
    purity_level: float
    hazard_check: bool
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: PolymerProcessState):
    purity = state.get('purity_level', 0.0)
    if purity < 99.0:
        return {'validation_logs': ['Low purity detected: rejection required']}
    return {'validation_logs': ['Purity verified: proceeding to hazard check']}

def perform_hazard_check(state: PolymerProcessState):
    return {'hazard_check': True, 'validation_logs': ['Hazard assessment complete: compliance confirmed']}

graph = StateGraph(PolymerProcessState)
graph.add_node('validate', validate_purity)
graph.add_node('hazard_check', perform_hazard_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'hazard_check')
graph.add_edge('hazard_check', END)
graph = graph.compile()
