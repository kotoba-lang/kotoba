from typing import TypedDict
from langgraph.graph import StateGraph, END

class HematologyState(TypedDict):
    device_id: str
    calibration_status: bool
    validation_score: float

def validate_specs(state: HematologyState):
    state['validation_score'] = 1.0 if state.get('calibration_status') else 0.0
    return state

workflow = StateGraph(HematologyState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
