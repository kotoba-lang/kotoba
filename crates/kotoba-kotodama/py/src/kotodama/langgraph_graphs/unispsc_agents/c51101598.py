from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SamplingState(TypedDict):
    batch_id: str
    is_sterile: bool
    validation_logs: List[str]
    approved: bool

def validate_sterility(state: SamplingState):
    is_sterile = state.get('is_sterile', False)
    log = 'Sterility check passed' if is_sterile else 'Sterility check failed'
    return {'validation_logs': [log], 'approved': is_sterile}

graph = StateGraph(SamplingState)
graph.add_node('validate', validate_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
