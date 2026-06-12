from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TshirtState(TypedDict):
    material_specs: dict
    compliance_docs: List[str]
    approved: bool

def validate_material(state: TshirtState):
    composition = state.get('material_specs', {}).get('fabric', '')
    return {'approved': 'cotton' in composition.lower() or 'polyester' in composition.lower()}

def check_compliance(state: TshirtState):
    has_certs = len(state.get('compliance_docs', [])) >= 2
    return {'approved': state['approved'] and has_certs}

graph = StateGraph(TshirtState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
