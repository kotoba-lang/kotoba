from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    mold_id: str
    material_type: str
    specs_verified: bool
    compliance_risk: List[str]

def validate_mold_specs(state: MoldState):
    # Simulate CAD/spec validation logic
    is_valid = state.get('material_type') in ['silicone', 'steel', 'aluminum']
    if not is_valid:
        return {'specs_verified': False}
    return {'specs_verified': True}

def check_compliance(state: MoldState):
    compliance = ['standard'] if state.get('specs_verified') else ['flagged_for_review']
    return {'compliance_risk': compliance}

graph = StateGraph(MoldState)
graph.add_node('validate', validate_mold_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
