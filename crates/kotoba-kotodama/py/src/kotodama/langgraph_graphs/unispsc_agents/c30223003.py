from typing import TypedDict
from langgraph.graph import StateGraph, END

class MosqueProjectState(TypedDict):
    project_id: str
    compliance_status: bool
    steps_completed: list

def validate_zoning(state: MosqueProjectState):
    print(f'Validating zoning for {state[project_id]}...')
    return {'compliance_status': True, 'steps_completed': ['zoning']}

def finalize_construction(state: MosqueProjectState):
    return {'steps_completed': state['steps_completed'] + ['finalized']}

graph = StateGraph(MosqueProjectState)
graph.add_node('zoning', validate_zoning)
graph.add_node('construction', finalize_construction)
graph.set_entry_point('zoning')
graph.add_edge('zoning', 'construction')
graph.add_edge('construction', END)
graph = graph.compile()
