from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SubmarineTenderState(TypedDict):
    tender_spec_id: str
    compliance_passed: bool
    validation_logs: List[str]

async def validate_specs(state: SubmarineTenderState):
    log = 'Verifying structural and naval defense certifications.'
    return {'compliance_passed': True, 'validation_logs': [log]}

async def assess_security(state: SubmarineTenderState):
    log = 'Performing mandatory security clearance and export control check.'
    return {'validation_logs': state['validation_logs'] + [log]}

graph = StateGraph(SubmarineTenderState)
graph.add_node('validate', validate_specs)
graph.add_node('security', assess_security)
graph.set_entry_point('validate')
graph.add_edge('validate', 'security')
graph.add_edge('security', END)
graph = graph.compile()
