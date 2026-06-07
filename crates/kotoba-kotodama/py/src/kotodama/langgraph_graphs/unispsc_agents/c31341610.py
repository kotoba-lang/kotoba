from typing import TypedDict
from langgraph.graph import StateGraph, END

class TitaniumState(TypedDict):
    spec_compliance: bool
    export_license_required: bool
    ndt_results: str

def validate_materials(state: TitaniumState):
    # Simulate material compliance check
    state['spec_compliance'] = True
    return state

def check_export_controls(state: TitaniumState):
    # Simulate ECCN check for dual-use
    state['export_license_required'] = True
    return state

workflow = StateGraph(TitaniumState)
workflow.add_node('validate', validate_materials)
workflow.add_node('export_check', check_export_controls)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'export_check')
workflow.add_edge('export_check', END)
graph = workflow.compile()
