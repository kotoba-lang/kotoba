from typing import TypedDict
from langgraph.graph import StateGraph, END

class DressingState(TypedDict):
    product_id: str
    is_sterile: bool
    passes_adhesion_test: bool

def validate_sterility(state: DressingState):
    return {"is_sterile": True}

def validate_adhesion(state: DressingState):
    return {"passes_adhesion_test": True}

graph = StateGraph(DressingState)
graph.add_node("sterility", validate_sterility)
graph.add_node("adhesion", validate_adhesion)
graph.add_edge("sterility", "adhesion")
graph.add_edge("adhesion", END)
graph.set_entry_point("sterility")
graph = graph.compile()
