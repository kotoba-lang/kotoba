from typing import TypedDict
from langgraph.graph import StateGraph, END

class AllergyEquipmentState(TypedDict):
    device_id: str
    compliance_docs: list
    is_validated: bool

def validate_compliance(state: AllergyEquipmentState):
    # Logic to verify ISO 13485 and regulatory docs
    docs = state.get('compliance_docs', [])
    is_valid = len(docs) >= 2
    return {'is_validated': is_valid}

def process_equipment(state: AllergyEquipmentState):
    if state['is_validated']:
        print(f'Processing device {state['device_id']} for shipment')
    return state

graph = StateGraph(AllergyEquipmentState)
graph.add_node('validate', validate_compliance)
graph.add_node('process', process_equipment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
