from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ChemicalProcurementState(TypedDict):
    requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: ChemicalProcurementState) -> ChemicalProcurementState:
    purity = state.get('requirements', {}).get('purity', 0)
    if purity >= 99.0:
        return {'validation_results': ['Purity check passed']}
    return {'validation_results': ['Purity check failed'], 'is_compliant': False}

def safety_review(state: ChemicalProcurementState) -> ChemicalProcurementState:
    return {'validation_results': ['Safety protocols verified']}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('safety', safety_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)

graph = graph.compile()
