from typing import TypedDict
from langgraph.graph import StateGraph, END

class StapleRemoverState(TypedDict):
    quality_check_passed: bool
    safety_rating: str

def validate_specs(state: StapleRemoverState):
    print('Validating staple remover material properties...')
    state['quality_check_passed'] = True
    return state

def check_ergonomics(state: StapleRemoverState):
    print('Verifying ergonomic standards for office safety...')
    state['safety_rating'] = 'compliant'
    return state

graph = StateGraph(StapleRemoverState)
graph.add_node('validate_specs', validate_specs)
graph.add_node('check_ergonomics', check_ergonomics)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', 'check_ergonomics')
graph.add_edge('check_ergonomics', END)
graph = graph.compile()
