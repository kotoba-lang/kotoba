from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PatientJacketState(TypedDict):
    specifications: dict
    validation_errors: List[str]
    is_compliant: bool

def validate_materials(state: PatientJacketState):
    fab = state.get('specifications', {}).get('fabric', '')
    errors = []
    if 'flame_retardant' not in fab:
        errors.append('Missing flame retardant certification')
    return {'validation_errors': errors}

def determine_status(state: PatientJacketState):
    return {'is_compliant': len(state.get('validation_errors', [])) == 0}

graph = StateGraph(PatientJacketState)
graph.add_node('validate', validate_materials)
graph.add_node('status', determine_status)
graph.set_entry_point('validate')
graph.add_edge('validate', 'status')
graph.add_edge('status', END)
graph = graph.compile()
