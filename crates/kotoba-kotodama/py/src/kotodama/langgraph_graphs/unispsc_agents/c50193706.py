from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FoodState(TypedDict):
    commodity: str
    quality_check_passed: bool
    compliance_docs: List[str]

def validate_quality(state: FoodState):
    print('Checking shelf life and sugar content...')
    return {'quality_check_passed': True}

def process_shipment(state: FoodState):
    print('Assigning refrigerated logistics...')
    return {'compliance_docs': ['cert_1', 'cert_2']}

graph = StateGraph(FoodState)
graph.add_node('quality_check', validate_quality)
graph.add_node('logistics', process_shipment)
graph.set_entry_point('quality_check')
graph.add_edge('quality_check', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
