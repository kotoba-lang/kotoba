from typing import TypedDict
from langgraph.graph import StateGraph, END

class SedimentGraphState(TypedDict):
    spec_data: dict
    analysis_result: str
    is_compliant: bool

def validate_specs(state: SedimentGraphState):
    specs = state.get('spec_data', {})
    required = ['accuracy', 'calibration']
    is_compliant = all(k in specs for k in required)
    return {'is_compliant': is_compliant}

def process_analysis(state: SedimentGraphState):
    if state.get('is_compliant'):
        return {'analysis_result': 'Validated: Ready for field deployment'}
    return {'analysis_result': 'Invalid: Specs missing'}

graph = StateGraph(SedimentGraphState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_analysis)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
