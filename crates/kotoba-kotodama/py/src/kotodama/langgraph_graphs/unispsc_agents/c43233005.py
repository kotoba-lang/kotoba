from typing import TypedDict
from langgraph.graph import StateGraph, END

class FirmwareState(TypedDict):
    firmware_blob: str
    version: str
    signature_valid: bool
    compatible: bool

def validate_signature(state: FirmwareState):
    # Simulate crypto validation
    return {'signature_valid': True}

def check_compatibility(state: FirmwareState):
    # Simulate hardware verification
    return {'compatible': True}

graph = StateGraph(FirmwareState)
graph.add_node('validate', validate_signature)
graph.add_node('compatibility', check_compatibility)
graph.add_edge('validate', 'compatibility')
graph.add_edge('compatibility', END)
graph.set_entry_point('validate')
graph = graph.compile()
