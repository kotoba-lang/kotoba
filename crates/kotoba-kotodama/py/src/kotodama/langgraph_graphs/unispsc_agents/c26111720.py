from typing import TypedDict
from langgraph.graph import StateGraph, END

class BatteryHolderState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    compliance_status: str

def validate_holder_specs(state: BatteryHolderState):
    specs = state.get('spec_sheet', {})
    required = ['material_composition', 'voltage_rating']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_status': 'COMPLIANT' if passed else 'INCOMPLETE'}

def router(state: BatteryHolderState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(BatteryHolderState)
graph.add_node('process', validate_holder_specs)
graph.set_entry_point('process')
graph.add_edge('process', END)

graph = graph.compile()
