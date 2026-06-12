from typing import TypedDict
from langgraph.graph import StateGraph, END
class ProcureState(TypedDict):
    spec_data: dict
    validated: bool
    approved: bool
def validate_specs(state: ProcureState):
    s = state.get('spec_data', {})
    valid = 'power-rating-kw' in s and 'safety-standard-compliance' in s
    return {'validated': valid}
def route_step(state: ProcureState):
    return 'approved' if state['validated'] else END
graph = StateGraph(ProcureState)
graph.add_node('validator', validate_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
