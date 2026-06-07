from typing import TypedDict
from langgraph.graph import StateGraph, END

class OphthalmicState(TypedDict):
    device_id: str
    is_sterile: bool
    compliance_docs: list
    status: str

def validate_sterility(state: OphthalmicState):
    state['is_sterile'] = True if state.get('compliance_docs') else False
    return {'status': 'Validated' if state['is_sterile'] else 'Rejected'}

workflow = StateGraph(OphthalmicState)
workflow.add_node('validate', validate_sterility)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
