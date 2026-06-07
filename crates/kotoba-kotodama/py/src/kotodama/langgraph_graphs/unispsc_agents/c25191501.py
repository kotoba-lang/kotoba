from typing import TypedDict
from langgraph.graph import StateGraph, END
class TrainingState(TypedDict):
    requirement_spec: dict
    compliance_check: bool
    export_approved: bool
def validate_specs(state: TrainingState):
    print('Validating ground support hardware specs...')
    state['compliance_check'] = True
    return state
def check_export_control(state: TrainingState):
    print('Verifying dual-use export regulations...')
    state['export_approved'] = True
    return state
graph = StateGraph(TrainingState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_control)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
