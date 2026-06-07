from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
import operator

class ReagentState(TypedDict):
    cas_number: str
    purity_required: float
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_purity(state: ReagentState):
    log = f'Validating purity for CAS: {state[cas_number]}'
    return {'validation_logs': [log], 'is_compliant': True}

def check_hazard(state: ReagentState):
    log = f'Checking hazardous shipping protocols for {state[cas_number]}'
    return {'validation_logs': [log]}

graph = StateGraph(ReagentState)
graph.add_node('purity_check', validate_purity)
graph.add_node('hazard_check', check_hazard)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'hazard_check')
graph.add_edge('hazard_check', END)
graph = graph.compile()
