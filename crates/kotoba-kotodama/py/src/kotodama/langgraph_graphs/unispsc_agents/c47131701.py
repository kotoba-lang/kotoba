from typing import TypedDict
from langgraph.graph import StateGraph, END

class DispenserState(TypedDict):
    material: str
    mounting_type: str
    is_compliant_ada: bool

def validate_specs(state: DispenserState):
    if state.get('material') not in ['Stainless Steel', 'ABS Plastic']:
        raise ValueError('Invalid material specification')
    return {'is_compliant_ada': True}

def deploy_workflow(state: DispenserState):
    print('Workflow: Initializing procurement for dispenser...')
    return {'status': 'validated'}

graph = StateGraph(DispenserState)
graph.add_node('validate', validate_specs)
graph.add_node('deploy', deploy_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
