from typing import TypedDict
from langgraph.graph import StateGraph, END

class OxycodoneState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    shipping_temp_verified: bool

async def verify_permits(state: OxycodoneState):
    return {'compliance_cleared': True}

async def log_environment(state: OxycodoneState):
    return {'shipping_temp_verified': True}

workflow = StateGraph(OxycodoneState)
workflow.add_node('verify', verify_permits)
workflow.add_node('log', log_environment)
workflow.set_entry_point('verify')
workflow.add_edge('verify', 'log')
workflow.add_edge('log', END)
graph = workflow.compile()
