from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoffeeState(TypedDict):
    product_name: str
    quality_status: str
    inspection_result: dict

def validate_coffee_quality(state: CoffeeState):
    # Simulate inspection logic for instant coffee
    result = {'is_grade_a': True, 'moisture_content': '<5%'}
    return {'inspection_result': result, 'quality_status': 'passed'}

def finalize_procurement(state: CoffeeState):
    return {'quality_status': 'finalized'}

graph = StateGraph(CoffeeState)
graph.add_node('validate', validate_coffee_quality)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
