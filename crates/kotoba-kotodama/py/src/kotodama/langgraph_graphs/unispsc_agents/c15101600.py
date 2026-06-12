from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class IndustrialMaterialState(TypedDict):
    material_id: str
    specs: dict
    is_validated: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_material_specs(state: IndustrialMaterialState):
    specs = state.get('specs', {})
    log = []
    if 'tensile_strength' in specs and specs['tensile_strength'] > 0:
        log.append('Tensile strength check passed.')
    else:
        log.append('Tensile strength check failed.')
    return {'is_validated': True, 'validation_log': log}

def process_procurement_workflow(state: IndustrialMaterialState):
    return {'validation_log': ['Procurement workflow initiated for industrial material.']}

graph = StateGraph(IndustrialMaterialState)
graph.add_node('validate', validate_material_specs)
graph.add_node('procure', process_procurement_workflow)
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph.set_entry_point('validate')
graph = graph.compile()
