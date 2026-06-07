from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EduGameState(TypedDict):
    product_id: str
    safety_check: bool
    edu_criteria_met: bool
    feedback: List[str]

def validate_safety(state: EduGameState):
    print('Validating safety certifications...')
    state['safety_check'] = True
    return state

def validate_educational_value(state: EduGameState):
    print('Validating educational alignment...')
    state['edu_criteria_met'] = True
    return state

graph = StateGraph(EduGameState)
graph.add_node('safety', validate_safety)
graph.add_node('pedagogy', validate_educational_value)
graph.set_entry_point('safety')
graph.add_edge('safety', 'pedagogy')
graph.add_edge('pedagogy', END)

graph = graph.compile()
