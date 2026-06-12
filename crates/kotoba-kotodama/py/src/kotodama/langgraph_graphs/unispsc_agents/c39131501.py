from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MarkerState(TypedDict):
    part_number: str
    material: str
    is_compliant: bool
    validation_log: List[str]

def validate_marker_spec(state: MarkerState):
    log = []
    compliant = True
    if not state.get('material'):
        log.append('Material specification missing')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def process_order(state: MarkerState):
    print(f'Processing wire marker: {state.get('part_number')}')
    return {'validation_log': state['validation_log'] + ['Order ready for procurement']}

workflow = StateGraph(MarkerState)
workflow.add_node('validate', validate_marker_spec)
workflow.add_node('process', process_order)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'process')
workflow.add_edge('process', END)
graph = workflow.compile()
