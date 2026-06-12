from typing import TypedDict
from langgraph.graph import StateGraph, END

class SimulatorState(TypedDict):
    spec_completed: bool
    compliance_validated: bool
    integration_finalized: bool

def validate_specs(state: SimulatorState):
    return {'spec_completed': True}

def check_compliance(state: SimulatorState):
    return {'compliance_validated': True}

def finalize(state: SimulatorState):
    return {'integration_finalized': True}

graph = StateGraph(SimulatorState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_node('finalize', finalize)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
