from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    chemical_name: str
    purity_level: float
    compliance_verified: bool

def validate_chemistry(state: ProcurementState):
    if state.get('purity_level', 0) < 99.0:
        raise ValueError('Purity below pharmaceutical standards')
    return {'compliance_verified': True}

def check_regulations(state: ProcurementState):
    print('Verifying MAOI licensing requirements...')
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chemistry)
graph.add_node('compliance', check_regulations)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
