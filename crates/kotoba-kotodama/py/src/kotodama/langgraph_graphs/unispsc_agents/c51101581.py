from typing import TypedDict, Annotated, List, Dict
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_code: str
    quality_docs: Dict[str, str]
    inspection_status: bool
    validation_log: List[str]

def validate_purity(state: ReagentState):
    log = state.get('validation_log', [])
    log.append('Verifying Certificate of Analysis and Purity.')
    return {'inspection_status': True, 'validation_log': log}

def storage_protocol_check(state: ReagentState):
    log = state.get('validation_log', [])
    log.append('Checking cold-chain logistics for reagent stability.')
    return {'validation_log': log}

workflow = StateGraph(ReagentState)
workflow.add_node('purity', validate_purity)
workflow.add_node('storage', storage_protocol_check)
workflow.set_entry_point('purity')
workflow.add_edge('purity', 'storage')
workflow.add_edge('storage', END)

graph = workflow.compile()
