from typing import TypedDict
from langgraph.graph import StateGraph, END

class InkState(TypedDict):
    chemical_data: dict
    compliance_ok: bool
    final_report: str

def validate_chemistry(state: InkState):
    # Simulate SDS validation logic
    sds = state.get('chemical_data', {})
    is_valid = 'hazard_class' in sds and sds['hazard_class'] < 5
    return {'compliance_ok': is_valid}

def generate_spec(state: InkState):
    return {'final_report': 'Technical spec verified and approved.' if state['compliance_ok'] else 'Validation rejected.'}

graph = StateGraph(InkState)
graph.add_node('validate', validate_chemistry)
graph.add_node('approve', generate_spec)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
