from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingProcurementState(TypedDict):
    part_number: str
    spec_compliance: bool
    validation_logs: List[str]
    approval_status: str

def validate_specs(state: BearingProcurementState):
    # Simulate high-precision CAD validation
    compliance = True if state.get('part_number') else False
    return {'spec_compliance': compliance, 'validation_logs': ['CAD model verified']}

def check_export_controls(state: BearingProcurementState):
    # Dual-use check logic
    return {'approval_status': 'CLEARED'}

graph = StateGraph(BearingProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_controls)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
