from typing import TypedDict
from langgraph.graph import StateGraph, END

class SquashBallState(TypedDict):
    ball_type: str
    is_wsf_certified: bool
    approved: bool

def validate_ball(state: SquashBallState) -> SquashBallState:
    if state.get('is_wsf_certified'):
        state['approved'] = True
    else:
        state['approved'] = False
    return state

workflow = StateGraph(SquashBallState)
workflow.add_node('validation', validate_ball)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
