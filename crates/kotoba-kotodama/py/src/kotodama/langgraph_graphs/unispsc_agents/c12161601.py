from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalState(TypedDict):
    commodity_id: str
    sds_verified: bool
    compliance_score: float
    messages: Annotated[Sequence[str], add_messages]

def validate_sds(state: ChemicalState) -> ChemicalState:
    # Mock validation logic for chemical substance
    state['sds_verified'] = True
    return state

def run_compliance_check(state: ChemicalState) -> ChemicalState:
    # Mock compliance scoring
    state['compliance_score'] = 0.95
    return state

graph = StateGraph(ChemicalState)
graph.add_node('validate_sds', validate_sds)
graph.add_node('run_compliance_check', run_compliance_check)
graph.add_edge('validate_sds', 'run_compliance_check')
graph.add_edge('run_compliance_check', END)
graph.set_entry_point('validate_sds')
graph = graph.compile()
