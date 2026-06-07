from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CoalSupplyState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    validation_passed: bool
    logistics_route: List[str]

def validate_quality(state: CoalSupplyState) -> CoalSupplyState:
    metrics = state.get('quality_metrics', {})
    # Logic: Validate calorific value and ash content against industry standards
    state['validation_passed'] = metrics.get('calorific_value', 0) > 6000
    return state

def route_logistics(state: CoalSupplyState) -> CoalSupplyState:
    if state['validation_passed']:
        state['logistics_route'] = ['Port_A', 'Rail_B', 'Factory_C']
    else:
        state['logistics_route'] = ['Quarantine_Zone']
    return state

graph = StateGraph(CoalSupplyState)
graph.add_node('validate', validate_quality)
graph.add_node('logistics', route_logistics)
graph.set_entry_point('validate')
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
