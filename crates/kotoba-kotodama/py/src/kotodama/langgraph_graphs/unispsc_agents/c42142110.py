from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProductState(TypedDict):
    product_id: str
    thermal_rating: float
    safety_check: bool

async def check_leakage(state: ProductState):
    return {'safety_check': state['thermal_rating'] > 0}

async def approve_procurement(state: ProductState):
    print(f'Processing procurement for {state.product_id}')
    return {'safety_check': True}

graph = StateGraph(ProductState)
graph.add_node('leakage_test', check_leakage)
graph.add_node('approval', approve_procurement)
graph.add_edge('leakage_test', 'approval')
graph.add_edge('approval', END)
graph.set_entry_point('leakage_test')
graph = graph.compile()
