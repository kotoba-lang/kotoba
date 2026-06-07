from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeatherproofBoxState(TypedDict):
    ip_rating: str
    nema_rating: str
    validation_result: bool

def validate_specs(state: WeatherproofBoxState):
    # Business logic for verifying if IP and NEMA ratings meet outdoor usage requirements
    valid = "6" in state.get('ip_rating', '') and "3R" in state.get('nema_rating', '')
    return {"validation_result": valid}

graph = StateGraph(WeatherproofBoxState)
graph.add_node("validate_specs", validate_specs)
graph.set_entry_point("validate_specs")
graph.add_edge("validate_specs", END)
graph = graph.compile()
