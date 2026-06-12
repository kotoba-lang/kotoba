import operator
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class AssessmentState(TypedDict):
    equipment_specs: dict
    validation_results: Annotated[list, operator.add]
    status: str

def validate_specs(state: AssessmentState):
    specs = state.get('equipment_specs', {})
    errors = []
    if 'accuracy' not in specs: errors.append('Missing accuracy field')
    return {'validation_results': errors, 'status': 'validated' if not errors else 'failed'}

def generate_report(state: AssessmentState):
    return {'status': 'report_generated'}

graph = StateGraph(AssessmentState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
