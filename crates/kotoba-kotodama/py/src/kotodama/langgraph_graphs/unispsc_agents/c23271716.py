from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingGraphState(TypedDict):
    spec_data: dict
    validation_report: dict

def validate_dresser_specs(state: WeldingGraphState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['tip_diameter', 'grit_type'])
    return {'validation_report': {'status': 'approved' if is_valid else 'rejected'}}

def finalize_order(state: WeldingGraphState):
    print('Procurement logic processed for dressing accessories.')
    return {'validation_report': {'finalized': True}}

graph = StateGraph(WeldingGraphState)
graph.add_node('validate', validate_dresser_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
