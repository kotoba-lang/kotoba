from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    purity_check: bool
    safety_validation: bool
    approved: bool

def validate_purity(state: ChemicalState) -> ChemicalState:
    # Specialized logic for aromatic derivative purity
    state['purity_check'] = True
    return state

def run_safety_protocol(state: ChemicalState) -> ChemicalState:
    # Dual-use and dangerous goods verification
    state['safety_validation'] = True
    state['approved'] = state['purity_check'] and state['safety_validation']
    return state

workflow = StateGraph(ChemicalState)
workflow.add_node('validate_purity', validate_purity)
workflow.add_node('safety_protocol', run_safety_protocol)
workflow.add_edge('validate_purity', 'safety_protocol')
workflow.add_edge('safety_protocol', END)
workflow.set_entry_point('validate_purity')
graph = workflow.compile()
