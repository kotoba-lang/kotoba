from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    order_id: str
    is_sterile: bool
    compliance_cleared: bool

async def check_sterilization(state: State) -> State:
    state['is_sterile'] = True
    return state

async def validate_regulations(state: State) -> State:
    state['compliance_cleared'] = True
    return state

builder = StateGraph(State)
builder.add_node('sterilization_check', check_sterilization)
builder.add_node('regulatory_compliance', validate_regulations)
builder.set_entry_point('sterilization_check')
builder.add_edge('sterilization_check', 'regulatory_compliance')
builder.add_edge('regulatory_compliance', END)
graph = builder.compile()
