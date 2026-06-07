from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material: str
    dimensions: dict
    is_compliant: bool
    validation_log: List[str]

def validate_materials(state: PackagingState):
    log = state.get('validation_log', [])
    valid = state.get('material') in ['Paperboard', 'PET', 'Recycled Card']
    log.append(f'Material validation: {valid}')
    return {'is_compliant': valid, 'validation_log': log}

def final_approval(state: PackagingState):
    return {'validation_log': state['validation_log'] + ['Approval process complete']}

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_materials)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
