from typing import TypedDict
from langgraph.graph import StateGraph, END
class FootRestState(TypedDict):
    spec_data: dict
    is_compliant: bool
def validate_specs(state: FootRestState):
    required = ['load_capacity', 'adjustment_mechanism']
    state['is_compliant'] = all(k in state.get('spec_data', {}) for k in required)
    return state
def procurement_workflow(state: FootRestState):
    print(f'Processing procurement with compliance: {state['is_compliant']}')
    return {'is_compliant': state['is_compliant']}
graph = StateGraph(FootRestState)
graph.add_node('validate', validate_specs)
graph.add_node('workflow', procurement_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'workflow')
graph.add_edge('workflow', END)
graph = graph.compile()
