from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalState(TypedDict):
    messages: Annotated[Sequence[str], add_messages]
    purity_check: bool
    regulatory_approved: bool

def check_purity(state: ChemicalState):
    # Simulate high-precision purity analysis
    return {'purity_check': True}

def verify_compliance(state: ChemicalState):
    # Simulate regulatory requirement check
    return {'regulatory_approved': True}

builder = StateGraph(ChemicalState)
builder.add_node('check_purity', check_purity)
builder.add_node('verify_compliance', verify_compliance)
builder.add_edge('check_purity', 'verify_compliance')
builder.add_edge('verify_compliance', END)
builder.set_entry_point('check_purity')
graph = builder.compile()
