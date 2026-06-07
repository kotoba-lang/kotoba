from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_spec: dict
    validation_passed: bool
    error_logs: List[str]

def validate_carbon_steel(state: ProcurementState):
    spec = state.get('material_spec', {})
    required = ['tensile_strength', 'weld_certification']
    if all(k in spec for k in required):
        return {'validation_passed': True}
    return {'validation_passed': False, 'error_logs': ['Missing mandatory specifications']}

def process_assembly(state: ProcurementState):
    print('Processing sonic welded bar assembly logic...')
    return {'validation_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_carbon_steel)
graph.add_node('process', process_assembly)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
