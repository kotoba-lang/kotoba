from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    quality_passed: bool
    compliance_checks: List[str]

def validate_compliance(state: PharmState):
    checks = state.get('compliance_checks', [])
    passed = 'gmp' in checks and 'temp_stable' in checks
    return {'quality_passed': passed}

def process_shipment(state: PharmState):
    if state['quality_passed']:
        print(f'Shipment {state["batch_id"]} cleared for release.')
    return {}

graph = StateGraph(PharmState)
graph.add_node('validate', validate_compliance)
graph.add_node('ship', process_shipment)
graph.add_edge('validate', 'ship')
graph.add_edge('ship', END)
graph.set_entry_point('validate')
graph = graph.compile()
