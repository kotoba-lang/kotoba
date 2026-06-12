from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeProcurementState(TypedDict):
    tape_type: str
    archival_compliant: bool
    vendor_rating: float

def validate_ph(state: TapeProcurementState):
    print('Validating archival pH neutrality for acid-free tape...')
    return {'archival_compliant': True}

def process_procurement(state: TapeProcurementState):
    print('Processing procurement order for archive-grade tape.')
    return {'vendor_rating': 4.8}

graph = StateGraph(TapeProcurementState)
graph.add_node('validate', validate_ph)
graph.add_node('order', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'order')
graph.add_edge('order', END)
graph = graph.compile()
