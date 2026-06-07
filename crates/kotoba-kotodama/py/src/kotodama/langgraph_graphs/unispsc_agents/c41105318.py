from typing import TypedDict
from langgraph.graph import StateGraph, END

class GelProcessingState(TypedDict):
    spec_data: dict
    validation_status: str

async def validate_specs(state: GelProcessingState):
    perc = state['spec_data'].get('gel_percentage', 0)
    if 0.5 <= perc <= 3.0:
        return {'validation_status': 'passed'}
    return {'validation_status': 'failed'}

async def check_storage(state: GelProcessingState):
    temp = state['spec_data'].get('storage_temp', '2-8C')
    return {'validation_status': 'ready_for_shipping' if temp == '2-8C' else 'cooling_error'}

graph = StateGraph(GelProcessingState)
graph.add_node('validate', validate_specs)
graph.add_node('storage_check', check_storage)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage_check')
graph.add_edge('storage_check', END)
graph = graph.compile()
