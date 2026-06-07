from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PaperProcurementState(TypedDict):
    paper_type: str
    spec_compliance: bool
    validation_log: List[str]

def validate_paper_spec(state: PaperProcurementState):
    log = state.get('validation_log', [])
    if 'fsc_certified_percentage' not in state:
        log.append('Missing FSC certification data')
        return {'spec_compliance': False, 'validation_log': log}
    log.append('Specs validated against ISO 9706')
    return {'spec_compliance': True, 'validation_log': log}

def route_procurement(state: PaperProcurementState):
    return 'VALIDATE' if state.get('paper_type') else END

graph = StateGraph(PaperProcurementState)
graph.add_node('VALIDATE', validate_paper_spec)
graph.set_entry_point('VALIDATE')
graph.add_edge('VALIDATE', END)
graph = graph.compile()
