from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SemiconductorState(TypedDict):
    material_id: str
    purity: float
    process_step: str
    validation_logs: List[str]

def validate_material(state: SemiconductorState) -> dict:
    purity = state.get('purity', 0.0)
    if purity < 99.99:
        return {'validation_logs': ['Purity level below threshold for organic electronics.']}
    return {'validation_logs': ['Material purity verified.']}

def process_deposition(state: SemiconductorState) -> dict:
    return {'process_step': 'READY_FOR_DEPOSITION'}

graph = StateGraph(SemiconductorState)
graph.add_node('validate', validate_material)
graph.add_node('process', process_deposition)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
