from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpecState(TypedDict):
    material: str
    specifications: List[str]
    validation_passed: bool

def validate_mounting_specs(state: SpecState):
    required = ['material', 'dimensions']
    passed = all(field in state for field in required)
    return {**state, 'validation_passed': passed}

def route_by_validation(state: SpecState):
    return 'process' if state.get('validation_passed') else END

graph = StateGraph(SpecState)
graph.add_node('validate', validate_mounting_specs)
graph.add_node('process', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()
