from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_id: str
    compliance_docs: List[str]
    validation_passed: bool

def validate_medical_device(state: ProcurementState):
    print('Validating ISO 13485 and sterilization records')
    return {'validation_passed': True}

def route_to_qa(state: ProcurementState):
    return 'qa_path' if state['validation_passed'] else END

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_device)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
