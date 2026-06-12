from typing import TypedDict, Annotated, List, Any
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_id: str
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: ProcurementState):
    log = state.get('validation_log', [])
    specs = state.get('specs', {})
    compliant = 'material_grade' in specs and 'dimensional_tolerance' in specs
    log.append(f'Validation complete: {compliant}')
    return {'is_compliant': compliant, 'validation_log': log}

def route_by_compliance(state: ProcurementState):
    return 'process' if state['is_compliant'] else 'reject'

def process_part(state: ProcurementState):
    return {'validation_log': state['validation_log'] + ['Part sent to manufacturing queue']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_part)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)

# Compile the graph
graph = graph.compile()
