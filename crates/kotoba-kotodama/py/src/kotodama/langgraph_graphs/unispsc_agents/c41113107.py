from typing import TypedDict
from langgraph.graph import StateGraph, END

class GasAnalyzerState(TypedDict):
    model_number: str
    calibration_date: str
    is_compliant: bool

def validate_specs(state: GasAnalyzerState):
    # Simulate validation logic for spec compliance
    return {'is_compliant': bool(state.get('model_number'))}

graph = StateGraph(GasAnalyzerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
