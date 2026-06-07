from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CatalystState(TypedDict):
    material_id: str
    purity_cert: str
    safety_check: bool
    dispatch_plan: list

def validate_chemical_compliance(state: CatalystState) -> CatalystState:
    # Logic for checking CAS and purity requirements
    state['safety_check'] = True if state.get('purity_cert') else False
    return state

def plan_secure_delivery(state: CatalystState) -> CatalystState:
    if state.get('safety_check'):
        state['dispatch_plan'] = ['Hazmat-Transit-Approval', 'Logistics-Cold-Chain']
    return state

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_chemical_compliance)
graph.add_node('plan', plan_secure_delivery)
graph.set_entry_point('validate')
graph.add_edge('validate', 'plan')
graph.add_edge('plan', END)

graph = graph.compile()
