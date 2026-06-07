from typing import TypedDict
from langgraph.graph import StateGraph, END

class BagProcurementState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_bag_specs(state: BagProcurementState):
    specs = state.get('spec_data', {})
    status = 'PASS' if specs.get('material_durability') == 'industrial' else 'FAIL'
    return {'validation_results': {'spec_check': status}}

def check_compliance(state: BagProcurementState):
    return {'validation_results': {'compliance_tag': 'ISO-13485-Standard-Compliance'}}

graph = StateGraph(BagProcurementState)
graph.add_node('validate', validate_bag_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
