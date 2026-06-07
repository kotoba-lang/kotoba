from typing import TypedDict
from langgraph.graph import StateGraph, END

class SteeringState(TypedDict):
    specs: dict
    validated: bool

def validate_specs(state: SteeringState):
    required = ['material', 'dimensions', 'compliance_cert']
    state['validated'] = all(k in state['specs'] for k in required)
    return state

def assembly_check(state: SteeringState):
    print('Checking steering component assembly parameters...')
    return state

graph = StateGraph(SteeringState)
graph.add_node('validation', validate_specs)
graph.add_node('assembly', assembly_check)
graph.set_entry_point('validation')
graph.add_edge('validation', 'assembly')
graph.add_edge('assembly', END)

if __name__ == '__main__':
    graph = graph.compile()
