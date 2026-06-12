from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SpectrumState(TypedDict):
    chart_id: str
    validation_passed: bool
    specs: dict

def validate_spectral_data(state: SpectrumState):
    print('Validating spectrum chart data parameters...')
    state['validation_passed'] = True
    return state

def generate_compliance_report(state: SpectrumState):
    print('Generating compliance report for spectrum charts...')
    return {'validation_passed': True}

graph = StateGraph(SpectrumState)
graph.add_node('validate', validate_spectral_data)
graph.add_node('report', generate_compliance_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
