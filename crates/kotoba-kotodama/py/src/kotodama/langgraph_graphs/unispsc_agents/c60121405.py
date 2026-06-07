from typing import TypedDict
from langgraph.graph import StateGraph, END

class FrameState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_dimensions(state: FrameState):
    specs = state.get('specs', {})
    min_size = specs.get('min_size')
    max_size = specs.get('max_size')
    state['validation_passed'] = bool(min_size and max_size and min_size < max_size)
    return state

def finalize(state: FrameState):
    return {"status": "READY_FOR_PROCUREMENT" if state['validation_passed'] else "REJECTED"}

graph = StateGraph(FrameState)
graph.add_node("validate", validate_dimensions)
graph.add_node("finalize", finalize)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
