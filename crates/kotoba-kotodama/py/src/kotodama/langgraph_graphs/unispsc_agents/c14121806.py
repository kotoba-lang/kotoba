from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material_type: str
    spec_requirements: dict
    validation_log: List[str]
    approved: bool

def validate_material_specs(state: PackagingState):
    log = state.get('validation_log', [])
    specs = state.get('spec_requirements', {})
    is_valid = specs.get('basis_weight_gsm', 0) > 0
    status = 'Pass' if is_valid else 'Fail'
    log.append(f'Spec validation: {status}')
    return {'validation_log': log, 'approved': is_valid}

def route_by_material(state: PackagingState):
    return 'process_paper' if state['approved'] else END

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_material_specs)
graph.add_node('process_paper', lambda x: {'validation_log': x['validation_log'] + ['Processing physical paper inventory']})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_material)
graph.add_edge('process_paper', END)
graph = graph.compile()
