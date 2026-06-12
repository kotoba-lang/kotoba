from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    safety_check_passed: bool
    purity_level: float
    compliance_tags: List[str]

def validate_safety(state: ChemicalState):
    # Simulate regulatory validation logic
    return {'safety_check_passed': state.get('purity_level', 0) > 0.98}

def process_logistics(state: ChemicalState):
    # Simulate supply chain routing
    tags = state.get('compliance_tags', [])
    tags.append('cleared_for_transit')
    return {'compliance_tags': tags}

workflow = StateGraph(ChemicalState)
workflow.add_node('safety_check', validate_safety)
workflow.add_node('logistics', process_logistics)
workflow.add_edge('safety_check', 'logistics')
workflow.add_edge('logistics', END)
workflow.set_entry_point('safety_check')
graph = workflow.compile()
