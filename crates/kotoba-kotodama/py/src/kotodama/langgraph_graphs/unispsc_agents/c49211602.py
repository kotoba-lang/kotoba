from typing import TypedDict
from langgraph.graph import StateGraph, END

class GolfBallState(TypedDict):
    ball_model: str
    usga_compliant: bool
    test_results: dict

def validate_usga_specs(state: GolfBallState):
    # Simulate regulatory compliance check for golf balls
    compliant = state.get('test_results', {}).get('restitution', 0) < 0.83
    return {'usga_compliant': compliant}

def route_by_spec(state: GolfBallState):
    return 'validate' if state.get('ball_model') else END

graph = StateGraph(GolfBallState)
graph.add_node('validate', validate_usga_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
