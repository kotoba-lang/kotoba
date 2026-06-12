from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HearingAidCaseState(TypedDict):
    case_model: str
    specifications: dict
    validation_results: List[str]
    is_compliant: bool

def validate_specs(state: HearingAidCaseState):
    specs = state.get('specifications', {})
    results = []
    if specs.get('moisture_resistance', False):
        results.append('Validated moisture resistance')
    return {'validation_results': results, 'is_compliant': len(results) > 0}

graph = StateGraph(HearingAidCaseState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
