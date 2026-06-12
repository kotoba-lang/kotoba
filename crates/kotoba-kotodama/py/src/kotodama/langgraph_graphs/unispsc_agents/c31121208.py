from typing import TypedDict
from langgraph.graph import StateGraph, END

class TitaniumState(TypedDict):
    part_id: str
    specs: dict
    is_compliant: bool

def validate_material_specs(state: TitaniumState):
    # Simulate material compliance check for aerospace grade Titanium
    specs = state.get('specs', {})
    state['is_compliant'] = specs.get('grade') == 'Grade 5'
    return state

def run_ndt_check(state: TitaniumState):
    # Simulate Non-Destructive Testing simulation
    state['ndt_passed'] = True
    return state

workflow = StateGraph(TitaniumState)
workflow.add_node('validation', validate_material_specs)
workflow.add_node('ndt', run_ndt_check)
workflow.add_edge('validation', 'ndt')
workflow.add_edge('ndt', END)
workflow.set_entry_point('validation')
graph = workflow.compile()
