from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class ArtMaterialState(TypedDict):
    material_type: str
    spec_compliance: bool
    validation_log: List[str]
def validate_material(state: ArtMaterialState):
    log = state.get('validation_log', [])
    if not state.get('material_type'):
        log.append('Error: Material type missing')
        return {'spec_compliance': False, 'validation_log': log}
    log.append(f'Validated {state[material_type]} for archival standards')
    return {'spec_compliance': True, 'validation_log': log}
graph = StateGraph(ArtMaterialState)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
