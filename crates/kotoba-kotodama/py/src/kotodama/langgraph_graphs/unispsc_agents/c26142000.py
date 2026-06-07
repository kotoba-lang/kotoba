from typing import TypedDict
from langgraph.graph import StateGraph, END

class IrradiationState(TypedDict):
    spec_data: dict
    validation_results: list
    compliance_ok: bool

def validate_shielding(state: IrradiationState):
    print('Validating radiation shielding...')
    return {'validation_results': ['shielding_checked']}

def check_compliance(state: IrradiationState):
    print('Checking regulatory certifications...')
    return {'compliance_ok': True}

graph = StateGraph(IrradiationState)
graph.add_node('validate_shielding', validate_shielding)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_shielding')
graph.add_edge('validate_shielding', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
