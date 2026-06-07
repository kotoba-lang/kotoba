from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SulfateState(TypedDict):
    commodity_code: str
    purity_level: float
    safety_clearance: bool
    log_messages: Annotated[Sequence[str], operator.add]

def validate_purity(state: SulfateState) -> SulfateState:
    min_purity = 98.5
    if state.get('purity_level', 0) < min_purity:
        state['log_messages'] = ['Purity below threshold']
    else:
        state['log_messages'] = ['Purity validated']
    return state

def check_safety_compliance(state: SulfateState) -> SulfateState:
    state['safety_clearance'] = True
    state['log_messages'] = ['Safety protocols cleared']
    return state

graph = StateGraph(SulfateState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_check', check_safety_compliance)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
