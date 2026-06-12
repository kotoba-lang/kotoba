from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    chemical_id: str
    compliance_docs: Annotated[Sequence[str], operator.add]
    is_cleared: bool

def validate_safety_data(state: ChemicalIngestState) -> ChemicalIngestState:
    # Simulate safety protocol validation logic
    state['is_cleared'] = True
    state['compliance_docs'] = ['MSDS_VERIFIED']
    return state

def check_dual_use(state: ChemicalIngestState) -> ChemicalIngestState:
    # Dual-use control check logic
    return state

graph = StateGraph(ChemicalIngestState)
graph.add_node('validate', validate_safety_data)
graph.add_node('export_check', check_dual_use)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
