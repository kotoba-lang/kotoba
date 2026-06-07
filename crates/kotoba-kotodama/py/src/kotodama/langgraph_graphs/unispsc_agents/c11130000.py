from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_code: str
    purity_required: float
    compliance_checks: List[str]
    approved: bool
    error_log: List[str]

def validate_safety_compliance(state: ChemicalProcurementState) -> Dict[str, Any]:
    # Specialized validation logic for industrial chemicals
    if 'safety_data_sheet_id' not in state.get('compliance_checks', []):
        return {'approved': False, 'error_log': ['SDS Missing']}
    return {'approved': True}

def process_procurement(state: ChemicalProcurementState) -> Dict[str, Any]:
    # Simulate supply chain routing logic
    return {'status': 'processed'}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('safety_check', validate_safety_compliance)
graph.add_node('procure', process_procurement)
graph.add_edge('safety_check', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
