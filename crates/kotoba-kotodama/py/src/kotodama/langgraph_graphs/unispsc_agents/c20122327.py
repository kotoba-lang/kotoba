from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MoldState(TypedDict):
    part_id: str
    specs: dict
    validation_passed: bool
    log: Annotated[Sequence[str], operator.add]

def validate_geometry(state: MoldState):
    # Simulate CAD geometry validation
    passed = True
    return {"validation_passed": passed, "log": ["Geometry validated against CAD"]}

def check_material_cert(state: MoldState):
    # Simulate material compliance check
    return {"log": ["Material cert verified"]}

def finalize_process(state: MoldState):
    return {"log": ["Mold component processing complete"]}

graph = StateGraph(MoldState)
graph.add_node("geometry", validate_geometry)
graph.add_node("material", check_material_cert)
graph.add_node("finalize", finalize_process)
graph.set_entry_point("geometry")
graph.add_edge("geometry", "material")
graph.add_edge("material", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
