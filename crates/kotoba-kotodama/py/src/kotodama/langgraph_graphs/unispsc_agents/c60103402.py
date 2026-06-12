from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class BookProcurementState(TypedDict):
    title: str
    age_range: str
    compliance_check: bool
    approved: bool

def validate_curriculum(state: BookProcurementState):
    print(f'Validating curriculum for: {state.get('title')}')
    return {'compliance_check': True}

def approval_step(state: BookProcurementState):
    return {'approved': state.get('compliance_check', False)}

graph = StateGraph(BookProcurementState)
graph.add_node('validate', validate_curriculum)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
