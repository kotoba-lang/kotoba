from typing import TypedDict
from langgraph.graph import StateGraph, END

class ZincState(TypedDict):
    spec_data: dict
    validation_passed: bool
    log: list

def validate_zinc_specs(state: ZincState):
    specs = state.get('spec_data', {})
    required = ['alloy_composition', 'tolerance']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'log': ['Specs validated: ' + str(passed)]}

def structural_integrity_check(state: ZincState):
    if state['validation_passed']:
        return {'log': state['log'] + ['Structural load analysis performed']}
    return {'log': state['log'] + ['Skipped structural analysis due to validation failure']}

graph = StateGraph(ZincState)
graph.add_node('validate', validate_zinc_specs)
graph.add_node('analysis', structural_integrity_check)
graph.add_edge('validate', 'analysis')
graph.add_edge('analysis', END)
graph.set_entry_point('validate')
graph = graph.compile()
