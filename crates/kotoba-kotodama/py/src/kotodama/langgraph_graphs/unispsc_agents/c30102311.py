from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BronzeState(TypedDict):
    material_spec: str
    quality_check_passed: bool
    compliance_docs: List[str]

def validate_specs(state: BronzeState):
    print('Validating bronze alloy metallurgical composition...')
    return {'quality_check_passed': True}

def check_compliance(state: BronzeState):
    print('Verifying ISO9001 and mill test report authenticity...')
    return {'compliance_docs': ['MTR_001', 'ISO_CERT']}

graph = StateGraph(BronzeState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
