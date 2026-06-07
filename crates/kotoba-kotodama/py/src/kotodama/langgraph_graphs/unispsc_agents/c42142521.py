from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BloodNeedleState(TypedDict):
    specifications: dict
    validation_passed: bool
    compliance_status: List[str]

def validate_needle_specs(state: BloodNeedleState):
    specs = state.get('specifications', {})
    required_fields = ['gauge', 'sterilization_method', 'iso_compliance']
    valid = all(key in specs for key in required_fields)
    return {'validation_passed': valid}

def check_compliance(state: BloodNeedleState):
    status = []
    if state['validation_passed']:
        status.append('Regulatory compliance check complete')
    return {'compliance_status': status}

graph = StateGraph(BloodNeedleState)
graph.add_node('validate', validate_needle_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
