from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EnergyKitState(TypedDict):
    kit_id: str
    compliance_docs: List[str]
    spec_verified: bool

def validate_kit_specs(state: EnergyKitState):
    print(f'Validating specs for kit: {state[kit_id]}')
    return {'spec_verified': len(state['compliance_docs']) > 0}

graph = StateGraph(EnergyKitState)
graph.add_node('validate', validate_kit_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
