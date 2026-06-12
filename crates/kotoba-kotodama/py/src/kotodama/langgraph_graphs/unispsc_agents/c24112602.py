from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class JarProcurementState(TypedDict):
    jar_specs: dict
    validation_passed: bool
    compliance_report: List[str]

def validate_jar_specs(state: JarProcurementState):
    specs = state.get('jar_specs', {})
    errors = []
    if not specs.get('food_safe', False):
        errors.append('Missing food safety certification')
    return {'validation_passed': len(errors) == 0, 'compliance_report': errors}

def route_by_validation(state: JarProcurementState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(JarProcurementState)
graph.add_node('validate', validate_jar_specs)
graph.add_node('process', lambda s: s)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation)
graph.add_edge('process', END)
graph = graph.compile()
