from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InstallKitState(TypedDict):
    kit_id: str
    components: List[str]
    compliance_ok: bool
    validation_log: List[str]

def validate_components(state: InstallKitState):
    if not state.get('components'):
        return {'validation_log': ['Error: Missing component list'], 'compliance_ok': False}
    return {'validation_log': ['Components validated'], 'compliance_ok': True}

def generate_install_plan(state: InstallKitState):
    state['validation_log'].append('Installation plan generated')
    return state

graph = StateGraph(InstallKitState)
graph.add_node('validate', validate_components)
graph.add_node('plan', generate_install_plan)
graph.add_edge('validate', 'plan')
graph.add_edge('plan', END)
graph.set_entry_point('validate')
graph = graph.compile()
