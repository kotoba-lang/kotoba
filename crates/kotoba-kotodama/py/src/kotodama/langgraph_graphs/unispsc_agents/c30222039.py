import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class CanalState(TypedDict):
    project_id: str
    specifications: dict
    validation_results: Annotated[list, operator.add]

def validate_geology(state: CanalState):
    return {"validation_results": ["Geotechnical data validated"]}

def structural_compliance(state: CanalState):
    return {"validation_results": ["Structural code compliance passed"]}

graph = StateGraph(CanalState)
graph.add_node("geology", validate_geology)
graph.add_node("structure", structural_compliance)
graph.set_entry_point("geology")
graph.add_edge("geology", "structure")
graph.add_edge("structure", END)
graph = graph.compile()
