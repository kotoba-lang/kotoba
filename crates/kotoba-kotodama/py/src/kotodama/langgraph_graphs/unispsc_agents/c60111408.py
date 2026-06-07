from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DecoTapeState(TypedDict):
    material_type: str
    spec_compliance: bool
    validation_report: List[str]

def validate_specs(state: DecoTapeState):
    report = []
    if not state.get('material_type'):
        report.append('Missing material specification')
    return {'validation_report': report, 'spec_compliance': len(report) == 0}

def finalize_procurement(state: DecoTapeState):
    return {'validation_report': state['validation_report'] + ['Finalized for procurement']}

graph = StateGraph(DecoTapeState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
