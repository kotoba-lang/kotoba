from typing import TypedDict
from langgraph.graph import StateGraph, END

class TellTaleState(TypedDict):
    spec_data: dict
    validation_msg: str
    is_compliant: bool

def validate_specs(state: TellTaleState):
    specs = state.get('spec_data', {})
    compliant = 'tolerance' in specs and 'material' in specs
    return {'is_compliant': compliant, 'validation_msg': 'Success' if compliant else 'Missing fields'}

graph = StateGraph(TellTaleState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
