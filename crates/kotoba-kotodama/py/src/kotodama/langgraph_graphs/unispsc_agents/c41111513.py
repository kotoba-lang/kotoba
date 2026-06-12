from typing import TypedDict
from langgraph.graph import StateGraph, END

class MoistureBalanceState(TypedDict):
    equipment_id: str
    calibration_status: bool
    precision_check: float
    status: str

def validate_specs(state: MoistureBalanceState):
    is_calibrated = state.get('calibration_status', False)
    return {'status': 'READY' if is_calibrated else 'PENDING_CALIBRATION'}

workflow = StateGraph(MoistureBalanceState)
workflow.add_node('validation', validate_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
