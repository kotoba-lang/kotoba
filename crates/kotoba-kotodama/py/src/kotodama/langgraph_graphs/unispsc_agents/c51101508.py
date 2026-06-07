from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SyringeState(TypedDict):
    sku: str
    volume_ml: float
    is_sterile: bool
    validation_logs: List[str]

def validate_syringe_spec(state: SyringeState):
    logs = state.get('validation_logs', [])
    if not state.get('is_sterile'):
        logs.append('ERROR: Sterility requirement not met')
    if state.get('volume_ml', 0) <= 0:
        logs.append('ERROR: Invalid volume specification')
    return {'validation_logs': logs}

def prepare_logistics(state: SyringeState):
    return {'validation_logs': state['validation_logs'] + ['Logistics: Cold chain not required']}

graph = StateGraph(SyringeState)
graph.add_node('validate', validate_syringe_spec)
graph.add_node('logistics', prepare_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
