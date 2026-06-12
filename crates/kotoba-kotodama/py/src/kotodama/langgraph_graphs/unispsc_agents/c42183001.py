from typing import TypedDict
from langgraph.graph import StateGraph, END

class VisionChartState(TypedDict):
    chart_id: str
    compliance_checked: bool
    is_calibrated: bool

def validate_chart_compliance(state: VisionChartState):
    state['compliance_checked'] = True
    return state

def check_calibration(state: VisionChartState):
    state['is_calibrated'] = True
    return state

graph = StateGraph(VisionChartState)
graph.add_node('validate', validate_chart_compliance)
graph.add_node('calibrate', check_calibration)
graph.add_edge('validate', 'calibrate')
graph.add_edge('calibrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
