from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PaperProcurementState(TypedDict):
    requirements: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_paper_spec(state: PaperProcurementState) -> PaperProcurementState:
    reqs = state.get('requirements', {})
    gsm = reqs.get('basis_weight_gsm', 0)
    results = []
    if gsm < 60 or gsm > 120:
        results.append('Invalid basis weight for standard office use')
    return {**state, 'validation_results': results, 'is_approved': len(results) == 0}

workflow = StateGraph(PaperProcurementState)
workflow.add_node('validate', validate_paper_spec)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
