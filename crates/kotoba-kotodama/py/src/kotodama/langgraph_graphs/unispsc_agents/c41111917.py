from typing import TypedDict
from langgraph.graph import StateGraph, END
class TesterState(TypedDict):
    device_id: str
    calibration_valid: bool
    compliance_checked: bool
def validate_calibration(state: TesterState):
    return {'calibration_valid': True}
def check_compliance(state: TesterState):
    return {'compliance_checked': True}
graph = StateGraph(TesterState)
graph.add_node('calibrate', validate_calibration)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('calibrate')
graph.add_edge('calibrate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
