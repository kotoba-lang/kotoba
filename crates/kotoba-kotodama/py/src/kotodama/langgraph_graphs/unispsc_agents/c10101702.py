from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AnimalProcureState(TypedDict):
    status: str
    health_checks: Annotated[Sequence[str], operator.add]
    transport_log: Annotated[Sequence[str], operator.add]

def health_inspection(state: AnimalProcureState):
    return {"health_checks": ["Veterinary inspection completed", "Vaccination verified"]}

def transport_validation(state: AnimalProcureState):
    return {"transport_log": ["Climate-controlled transport assigned", "Route compliance checked"]}

workflow = StateGraph(AnimalProcureState)
workflow.add_node("health_inspection", health_inspection)
workflow.add_node("transport_validation", transport_validation)
workflow.add_edge("health_inspection", "transport_validation")
workflow.add_edge("transport_validation", END)
workflow.set_entry_point("health_inspection")
graph = workflow.compile()
