from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GearProcurementState(TypedDict):
    part_id: str
    spec_compliance: bool
    validation_logs: List[str]
    export_control_check: bool

def validate_specs(state: GearProcurementState):
    # Simulate CAD/Spec validation for gears
    is_compliant = True # Placeholder logic
    return {'spec_compliance': is_compliant, 'validation_logs': ['Spec verified against ISO standards']}

def check_dual_use(state: GearProcurementState):
    # Simulate export control check
    is_regulated = True
    return {'export_control_check': is_regulated}

builder = StateGraph(GearProcurementState)
builder.add_node('validate', validate_specs)
builder.add_node('export_check', check_dual_use)
builder.set_entry_point('validate')
builder.add_edge('validate', 'export_check')
builder.add_edge('export_check', END)
graph = builder.compile()
