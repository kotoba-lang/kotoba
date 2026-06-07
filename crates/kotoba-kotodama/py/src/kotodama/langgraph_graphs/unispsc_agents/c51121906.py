from typing import TypedDict
from langgraph.graph import StateGraph, END

class BetaineState(TypedDict):
    purity: float
    safety_clearance: bool

def validate_purity(state: BetaineState) -> BetaineState:
    if state.get('purity', 0) < 99.0:
        state['safety_clearance'] = False
    else:
        state['safety_clearance'] = True
    return state

def process_compliance(state: BetaineState) -> BetaineState:
    print(f'Compliance check status: {state.get("safety_clearance")}')
    return state

graph = StateGraph(BetaineState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', process_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
