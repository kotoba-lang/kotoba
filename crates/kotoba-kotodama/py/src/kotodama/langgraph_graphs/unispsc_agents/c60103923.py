from typing import TypedDict
from langgraph.graph import StateGraph, END

class SpecimenState(TypedDict):
    specimen_id: str
    cites_compliant: bool
    is_preserved: bool
    approved: bool

def validate_cites(state: SpecimenState):
    return {'cites_compliant': True} if state.get('cites_compliant') else {'approved': False}

def check_preservation(state: SpecimenState):
    return {'is_preserved': True} if state.get('is_preserved') else {'approved': False}

workflow = StateGraph(SpecimenState)
workflow.add_node('cites_check', validate_cites)
workflow.add_node('preservation_check', check_preservation)
workflow.set_entry_point('cites_check')
workflow.add_edge('cites_check', 'preservation_check')
workflow.add_edge('preservation_check', END)
graph = workflow.compile()
