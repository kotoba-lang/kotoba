from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralProcState(TypedDict):
    material_type: str
    quality_metrics: dict
    approved: bool

def validate_abrasive_quality(state: MineralProcState):
    metrics = state.get('quality_metrics', {})
    # Simulated validation logic: check if hardness meets industrial threshold
    if metrics.get('hardness', 0) >= 9.0:
        return {'approved': True}
    return {'approved': False}

def process_procurement(state: MineralProcState):
    print(f'Processing procurement for {state.get('material_type')}')
    return {'approved': True}

graph = StateGraph(MineralProcState)
graph.add_node('validate', validate_abrasive_quality)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
