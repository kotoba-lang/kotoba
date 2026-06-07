from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PowderProcessingState(TypedDict):
    batch_id: str
    purity_check: bool
    particle_analysis: dict
    is_compliant: bool

def validate_powder_specs(state: PowderProcessingState):
    purity = state.get('particle_analysis', {}).get('purity', 0)
    return {'is_compliant': purity >= 99.9}

def route_by_compliance(state: PowderProcessingState):
    return 'process' if state['is_compliant'] else 'quarantine'

def process_powder_workflow(state: PowderProcessingState):
    return {'batch_id': state['batch_id'] + '_processed'}

graph = StateGraph(PowderProcessingState)
graph.add_node('validate', validate_powder_specs)
graph.add_node('process', process_powder_workflow)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'process': 'process', 'quarantine': END})
graph.add_edge('process', END)
graph = graph.compile()
