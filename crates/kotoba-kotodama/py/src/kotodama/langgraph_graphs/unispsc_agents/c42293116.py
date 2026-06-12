from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalInstrumentState(TypedDict):
    instrument_code: str
    compliance_cleared: bool
    sterilization_check: bool

def validate_instrument_specs(state: SurgicalInstrumentState):
    # Simulate CAD document or medical cert validation
    state['compliance_cleared'] = True
    return state

def check_sterilization_compliance(state: SurgicalInstrumentState):
    state['sterilization_check'] = True
    return state

graph = StateGraph(SurgicalInstrumentState)
graph.add_node("validate", validate_instrument_specs)
graph.add_node("sterilization", check_sterilization_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterilization")
graph.add_edge("sterilization", END)
graph = graph.compile()
