from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_drape_specs(state: ProcurementState):
    specs = state.get('specifications', {})
    # Check for mandatory sterility certification
    is_compliant = 'sterility_cert' in specs and specs['sterility_cert'] is True
    return {'validation_passed': is_compliant, 'compliance_report': 'Validated' if is_compliant else 'Failed'}

def generate_procurement_workflow():
    graph = StateGraph(ProcurementState)
    graph.add_node('validate', validate_drape_specs)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = generate_procurement_workflow()
