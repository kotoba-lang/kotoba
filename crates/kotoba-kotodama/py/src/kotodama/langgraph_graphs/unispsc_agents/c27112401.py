from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StapleGunState(TypedDict):
    model_number: str
    power_source: str
    is_compliant: bool
    validation_errors: List[str]

def validate_tool(state: StapleGunState):
    errors = []
    if not state.get('power_source') in ['manual', 'electric', 'pneumatic']:
        errors.append('Invalid power source')
    return {'is_compliant': len(errors) == 0, 'validation_errors': errors}

workflow = StateGraph(StapleGunState)
workflow.add_node('validate', validate_tool)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
