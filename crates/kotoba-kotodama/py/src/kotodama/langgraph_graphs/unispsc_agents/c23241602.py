from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MachineSpecs(TypedDict):
    model: str
    precision_grade: str
    export_license_required: bool

def validate_specs(state: MachineSpecs):
    if state.get('precision_grade') == 'ultra-fine':
        return {'export_license_required': True}
    return {'export_license_required': False}

def route_verification(state: MachineSpecs):
    return 'export_check' if state['export_license_required'] else END

graph = StateGraph(MachineSpecs)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', lambda s: {'status': 'manual_review_required'})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_verification)
graph.add_edge('export_check', END)
graph = graph.compile()
