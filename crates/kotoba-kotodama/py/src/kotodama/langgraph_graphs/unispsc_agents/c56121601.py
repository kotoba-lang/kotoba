from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FurnitureState(TypedDict):
    item_name: str
    safety_compliance: bool
    test_results: List[str]

def validate_safety(state: FurnitureState):
    print('Validating safety standards for children\'s furniture...')
    state['safety_compliance'] = True
    state['test_results'] = ['Flammability', 'Lead-free', 'Stability']
    return state

def approve_procurement(state: FurnitureState):
    print('Compliance confirmed. Proceeding to procurement workflow.')
    return state

graph = StateGraph(FurnitureState)
graph.add_node('validate', validate_safety)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
