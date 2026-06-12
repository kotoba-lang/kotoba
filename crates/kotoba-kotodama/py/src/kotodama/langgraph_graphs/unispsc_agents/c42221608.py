from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TubingLabelState(TypedDict):
    label_type: str
    compliance_docs: List[str]
    validation_passed: bool

async def validate_biocompatibility(state: TubingLabelState):
    # Simulate ISO 10993 compliance check
    is_compliant = 'ISO_10993' in state.get('compliance_docs', [])
    return {'validation_passed': is_compliant}

async def approval_node(state: TubingLabelState):
    if state['validation_passed']:
        return 'approved'
    return 'rejected'

graph = StateGraph(TubingLabelState)
graph.add_node('validate', validate_biocompatibility)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
