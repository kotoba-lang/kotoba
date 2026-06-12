from typing import TypedDict
from langgraph.graph import StateGraph, END

class BondedAssemblyState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_risk: str

def validate_bonding_spec(state: BondedAssemblyState):
    specs = state.get('spec_data', {})
    required = ['tensile_strength', 'curing_temp']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'compliance_risk': 'high' if not passed else 'low'}

def process_assembly(state: BondedAssemblyState):
    return {'compliance_risk': 'cleared'}

graph = StateGraph(BondedAssemblyState)
graph.add_node('validate', validate_bonding_spec)
graph.add_node('process', process_assembly)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)

graph = graph.compile()
