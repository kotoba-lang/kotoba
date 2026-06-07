from typing import TypedDict
from langgraph.graph import StateGraph, END
class AnchorState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list
def validate_specs(state: AnchorState):
    specs = state.get('spec_data', {})
    critical_keys = ['breaking_load', 'material']
    valid = all(k in specs for k in critical_keys)
    return {'validated': valid, 'error_log': [] if valid else ['Missing technical specs']}
def finalize_procurement(state: AnchorState):
    return {'validated': True}
graph = StateGraph(AnchorState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
