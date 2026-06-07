from typing import TypedDict
from langgraph.graph import StateGraph, END

class CartState(TypedDict):
    engine_check: bool
    safety_check: bool
    approved: bool

def validate_engine(state: CartState):
    print('Validating engine specifications...')
    return {'engine_check': True}

def validate_safety(state: CartState):
    print('Checking safety equipment standards...')
    return {'safety_check': True}

def finalize_procurement(state: CartState):
    return {'approved': state['engine_check'] and state['safety_check']}

graph = StateGraph(CartState)
graph.add_node('engine', validate_engine)
graph.add_node('safety', validate_safety)
graph.add_node('approve', finalize_procurement)
graph.set_entry_point('engine')
graph.add_edge('engine', 'safety')
graph.add_edge('safety', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
