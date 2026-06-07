from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    instrument_id: str
    is_sterile: bool
    passed_qa: bool

def validate_instrument(state: ProcessingState): return {"passed_qa": True}
def log_sterilization(state: ProcessingState): return {"is_sterile": True}

graph = StateGraph(ProcessingState)
graph.add_node("validate", validate_instrument)
graph.add_node("sterilize", log_sterilization)
graph.add_edge("validate", "sterilize")
graph.add_edge("sterilize", END)
graph.set_entry_point("validate")

graph = graph.compile()
