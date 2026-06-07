from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    cas_number: str
    purity: float
    safety_check: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_cas(state: ChemicalIngestState) -> ChemicalIngestState:
    # Specialized logic for chemical registry validation
    if not state.get('cas_number'):
        return {**state, 'safety_check': False, 'validation_log': ['Invalid CAS format']}
    return {**state, 'safety_check': True}

def process_purity(state: ChemicalIngestState) -> ChemicalIngestState:
    if state.get('purity', 0) < 99.0:
        return {**state, 'validation_log': ['Purity below industrial threshold']}
    return {**state, 'validation_log': ['Purity verified']}

graph = StateGraph(ChemicalIngestState)
graph.add_node('validate_cas', validate_cas)
graph.add_node('process_purity', process_purity)
graph.add_edge('validate_cas', 'process_purity')
graph.add_edge('process_purity', END)
graph.set_entry_point('validate_cas')
graph = graph.compile()
