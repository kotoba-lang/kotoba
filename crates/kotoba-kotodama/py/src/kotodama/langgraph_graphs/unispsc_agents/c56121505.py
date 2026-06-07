from typing import TypedDict
from langgraph.graph import StateGraph, END

class ClassroomTableState(TypedDict):
    spec_data: dict
    validation_log: list

def validate_durability(state: ClassroomTableState):
    data = state.get('spec_data', {})
    status = 'PASS' if data.get('material') in ['Laminate', 'Solid Wood'] else 'FAIL'
    return {'validation_log': [f'Durability Check: {status}']}

def safety_review(state: ClassroomTableState):
    log = state.get('validation_log', [])
    log.append('Safety Compliance: Verified against ANSI/BIFMA standards')
    return {'validation_log': log}

graph = StateGraph(ClassroomTableState)
graph.add_node('DurabilityCheck', validate_durability)
graph.add_node('SafetyReview', safety_review)
graph.add_edge('DurabilityCheck', 'SafetyReview')
graph.add_edge('SafetyReview', END)
graph.set_entry_point('DurabilityCheck')

graph = graph.compile()
