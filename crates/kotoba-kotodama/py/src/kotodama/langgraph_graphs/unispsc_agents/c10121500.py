from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FertilizerState(TypedDict):
    composition_data: dict
    validation_results: List[str]
    is_compliant: bool

def analyze_composition(state: FertilizerState) -> FertilizerState:
    # Logic to validate NPK ratios and heavy metals
    composition = state.get('composition_data', {})
    results = []
    if composition.get('heavy_metals', 0) > 0.05:
        results.append('Heavy metal limit exceeded')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: FertilizerState) -> str:
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(FertilizerState)
graph.add_node('analyze', analyze_composition)
graph.set_entry_point('analyze')
graph.add_conditional_edges('analyze', route_by_compliance, {'compliant': END, 'flag_for_review': 'flag_for_review'})
graph.add_node('flag_for_review', lambda x: x)
graph.add_edge('flag_for_review', END)
graph = graph.compile()
