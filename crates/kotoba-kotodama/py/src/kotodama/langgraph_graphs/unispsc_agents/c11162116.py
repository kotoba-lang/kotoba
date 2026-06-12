from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SiliconState(TypedDict):
    material_id: str
    spec_requirements: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_crystal_purity(state: SiliconState) -> SiliconState:
    # Logic to check purity against specs
    state['validation_log'] = ['Purity check passed']
    return state

def check_export_control(state: SiliconState) -> SiliconState:
    # Dual-use export control logic
    state['validation_log'] = state['validation_log'] + ['Export control verified']
    state['is_compliant'] = True
    return state

graph = StateGraph(SiliconState)
graph.add_node('validate_purity', validate_crystal_purity)
graph.add_node('export_control', check_export_control)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'export_control')
graph.add_edge('export_control', END)
graph = graph.compile()
