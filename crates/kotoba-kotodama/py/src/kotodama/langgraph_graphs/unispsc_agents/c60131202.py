from typing import TypedDict
from langgraph.graph import StateGraph, END

class OboeState(TypedDict):
    instrument_id: str
    quality_check_passed: bool
    tuning_verified: bool

def validate_instrument(state: OboeState):
    return {'quality_check_passed': True}

def verify_tuning(state: OboeState):
    return {'tuning_verified': True}

graph = StateGraph(OboeState)
graph.add_node('validate_instrument', validate_instrument)
graph.add_node('verify_tuning', verify_tuning)
graph.set_entry_point('validate_instrument')
graph.add_edge('validate_instrument', 'verify_tuning')
graph.add_edge('verify_tuning', END)
graph = graph.compile()
