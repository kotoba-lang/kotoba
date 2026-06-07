from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CleaningKitState(TypedDict):
    kit_id: str
    contents: List[str]
    compliance_passed: bool

def validate_contents(state: CleaningKitState) -> CleaningKitState:
    if not state.get('contents'):
        state['compliance_passed'] = False
    else:
        state['compliance_passed'] = True
    return state

def finalize_kit(state: CleaningKitState) -> str:
    return 'APPROVED' if state['compliance_passed'] else 'REJECTED'

graph = StateGraph(CleaningKitState)
graph.add_node('validate', validate_contents)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
