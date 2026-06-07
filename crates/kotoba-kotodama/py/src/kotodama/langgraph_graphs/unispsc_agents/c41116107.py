from typing import TypedDict
from langgraph.graph import StateGraph, END

class QualityControlState(TypedDict):
    lot_number: str
    stability_data: dict
    approved: bool

def validate_coa(state: QualityControlState):
    print('Validating Certificate of Analysis...')
    state['approved'] = True
    return {'approved': True}

def check_expiry(state: QualityControlState):
    print('Checking expiration protocol...')
    return {'approved': True}

graph = StateGraph(QualityControlState)
graph.add_node('validate', validate_coa)
graph.add_node('expiry', check_expiry)
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph.set_entry_point('validate')
graph = graph.compile()
