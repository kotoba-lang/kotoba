from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodState(TypedDict):
    product_id: str
    safety_compliance: bool
    batch_tracked: bool

def validate_safety(state: FoodState) -> FoodState:
    print(f'Validating FSSAI/HACCP for {state[product_id]}')
    state['safety_compliance'] = True
    return state

def track_batch(state: FoodState) -> FoodState:
    print('Logging batch and shelf-life metadata')
    state['batch_tracked'] = True
    return state

graph = StateGraph(FoodState)
graph.add_node('safety', validate_safety)
graph.add_node('tracking', track_batch)
graph.set_entry_point('safety')
graph.add_edge('safety', 'tracking')
graph.add_edge('tracking', END)
graph = graph.compile()
