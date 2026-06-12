from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class PlantProcurementState(TypedDict):
    seed_id: str
    phytosanitary_status: bool
    germination_test: float
    messages: Annotated[Sequence[str], add_messages]

def validate_phytosanitary(state: PlantProcurementState):
    return {'phytosanitary_status': True}

def check_germination(state: PlantProcurementState):
    return {'germination_test': 0.95}

graph = StateGraph(PlantProcurementState)
graph.add_node('validate_phytosanitary', validate_phytosanitary)
graph.add_node('check_germination', check_germination)
graph.add_edge('validate_phytosanitary', 'check_germination')
graph.add_edge('check_germination', END)
graph.set_entry_point('validate_phytosanitary')
graph = graph.compile()
