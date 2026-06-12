from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_code: str
    spec_data: dict
    validation_logs: List[str]
    is_approved: bool

def validate_reagent_spec(state: ReagentState) -> ReagentState:
    logs = state.get('validation_logs', [])
    spec = state.get('spec_data', {})
    if 'expiration_date' in spec and 'lot_number' in spec:
        logs.append('Spec validated successfully.')
        state['is_approved'] = True
    else:
        logs.append('Validation failed: missing critical fields.')
        state['is_approved'] = False
    state['validation_logs'] = logs
    return state

graph = StateGraph(ReagentState)
graph.add_node('validator', validate_reagent_spec)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
