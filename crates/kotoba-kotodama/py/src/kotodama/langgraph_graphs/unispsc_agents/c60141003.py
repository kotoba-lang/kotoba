from typing import TypedDict
from langgraph.graph import StateGraph, END

class DollHouseState(TypedDict):
    product_id: str
    safety_certs: bool
    passed_qa: bool

def validate_safety(state: DollHouseState):
    return {'safety_certs': True}

def inspect_quality(state: DollHouseState):
    return {'passed_qa': True}

graph = StateGraph(DollHouseState)
graph.add_node('safety_check', validate_safety)
graph.add_node('quality_control', inspect_quality)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'quality_control')
graph.add_edge('quality_control', END)
graph = graph.compile()
