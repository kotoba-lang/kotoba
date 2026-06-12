from typing import TypedDict
from langgraph.graph import StateGraph, END

class TractorState(TypedDict):
    spec_data: dict
    validation_passed: bool
    log: list

def validate_specs(state: TractorState):
    specs = state.get('spec_data', {})
    passed = specs.get('tractive_effort', 0) > 200
    return {'validation_passed': passed, 'log': ['Specs validated for heavy aircraft']}

def safety_check(state: TractorState):
    return {'log': state['log'] + ['Safety compliance check complete']}

graph = StateGraph(TractorState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
