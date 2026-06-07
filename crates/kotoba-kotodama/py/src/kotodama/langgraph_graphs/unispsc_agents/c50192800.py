from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FoodSupplyState(TypedDict):
    product_id: str
    quality_cert: bool
    temp_check: bool
    approved: bool

def validate_quality(state: FoodSupplyState):
    return {'quality_cert': True}

def validate_logistics(state: FoodSupplyState):
    return {'temp_check': True}

def approval_logic(state: FoodSupplyState):
    return {'approved': state['quality_cert'] and state['temp_check']}

graph = StateGraph(FoodSupplyState)
graph.add_node('quality', validate_quality)
graph.add_node('logistics', validate_logistics)
graph.add_node('approval', approval_logic)
graph.add_edge('quality', 'logistics')
graph.add_edge('logistics', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('quality')
graph = graph.compile()
