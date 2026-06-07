from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoatingWorkflowState(TypedDict):
    part_type: str
    viscosity_check: bool
    is_hazardous: bool

def validate_viscosity(state: CoatingWorkflowState):
    state['viscosity_check'] = True
    return state

def safety_protocol(state: CoatingWorkflowState):
    state['is_hazardous'] = True
    return state

graph = StateGraph(CoatingWorkflowState)
graph.add_node('validate', validate_viscosity)
graph.add_node('safety', safety_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
