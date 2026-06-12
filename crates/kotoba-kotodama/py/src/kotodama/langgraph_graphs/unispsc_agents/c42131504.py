from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PatientGownState(TypedDict):
    gown_specs: dict
    compliance_passed: bool
    validation_log: List[str]

def validate_materials(state: PatientGownState):
    specs = state.get('gown_specs', {})
    valid = specs.get('flammability_test') == 'passed' and specs.get('material') != 'non-compliant'
    return {'compliance_passed': valid, 'validation_log': ['Material validation complete']}

def quality_check(state: PatientGownState):
    return {'validation_log': state['validation_log'] + ['Quality standards verified']}

graph = StateGraph(PatientGownState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('quality_check', quality_check)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'quality_check')
graph.add_edge('quality_check', END)
graph = graph.compile()
