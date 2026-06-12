from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class PolymerState(TypedDict):
    material_id: str
    safety_clearance: bool
    purity_check: float
    processing_steps: Annotated[list[str], operator.add]

def validate_safety(state: PolymerState):
    # Simulate stringent chemical safety check
    return {'safety_clearance': True}

def perform_purity_test(state: PolymerState):
    # Simulate spectroscopic verification
    return {'purity_check': 99.98}

def record_processing(state: PolymerState):
    return {'processing_steps': ['Ingestion', 'SafetyValidation', 'PurityVerification', 'Archive']}

graph = StateGraph(PolymerState)
graph.add_node('safety', validate_safety)
graph.add_node('purity', perform_purity_test)
graph.add_node('record', record_processing)

graph.set_entry_point('safety')
graph.add_edge('safety', 'purity')
graph.add_edge('purity', 'record')
graph.add_edge('record', END)

graph = graph.compile()
