from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class TrainingState(TypedDict):
    materials: List[str]
    compliance_checked: bool
    approved: bool

def validate_content(state: TrainingState):
    print('Validating instructional alignment for etiquette accuracy')
    return {'compliance_checked': True}

def approval_check(state: TrainingState):
    print('Routing materials for HR manager approval')
    return {'approved': True}

graph = StateGraph(TrainingState)
graph.add_node('validate', validate_content)
graph.add_node('approve', approval_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
