from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    device_specs: dict
    validation_report: List[str]
    is_approved: bool

def validate_specs(state: SurgicalState):
    specs = state.get('device_specs', {})
    report = []
    if 'sterilization' not in specs:
        report.append('Missing sterilization data')
    return {'validation_report': report, 'is_approved': len(report) == 0}

def approval_step(state: SurgicalState):
    return {'is_approved': state['is_approved']}

graph = StateGraph(SurgicalState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
