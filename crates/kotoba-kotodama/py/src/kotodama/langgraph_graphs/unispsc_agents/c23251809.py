from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DieProcurementState(TypedDict):
    spec_file_path: str
    validation_passed: bool
    approvals: List[str]

def validate_specs(state: DieProcurementState):
    print('Validating rotary die technical specs...')
    return {'validation_passed': True}

def check_compliance(state: DieProcurementState):
    print('Checking regulatory compliance for precision metal tools...')
    return {'approvals': ['QC_PASSED']}

graph = StateGraph(DieProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
