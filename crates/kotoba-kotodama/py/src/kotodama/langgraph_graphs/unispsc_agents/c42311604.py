from typing import TypedDict
from langgraph.graph import StateGraph, END

class HemostatState(TypedDict):
    product_id: str
    material_certified: bool
    sterility_verified: bool

def validate_compliance(state: HemostatState):
    # Simulate Biocompatibility and Sterility verification
    return {'material_certified': True, 'sterility_verified': True}

def process_procurement(state: HemostatState):
    print(f'Processing procurement for medical grade collagen: {state[product_id]}')
    return {'status': 'processed'}

graph = StateGraph(HemostatState)
graph.add_node('validate', validate_compliance)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
