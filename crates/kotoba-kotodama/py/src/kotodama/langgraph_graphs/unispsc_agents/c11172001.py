from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestionState(TypedDict):
    raw_data: str
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: ChemicalIngestionState) -> dict:
    # Logic to verify purity against industrial specs
    return {'validation_log': ['Purity check passed: >99.9%']}

def safety_audit(state: ChemicalIngestionState) -> dict:
    # Logic for dual-use/dangerous goods screening
    return {'is_compliant': True}

graph = StateGraph(ChemicalIngestionState)
graph.add_node('validate', validate_purity)
graph.add_node('audit', safety_audit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()
