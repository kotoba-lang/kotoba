from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class RollerProcurementState(TypedDict):
    specifications: dict
    validation_results: Annotated[list, operator.add]

def validate_roller_specs(state: RollerProcurementState):
    specs = state.get('specifications', {})
    results = []
    if not specs.get('nap_length'): results.append('Missing nap length')
    if not specs.get('frame_material'): results.append('Missing frame material')
    return {'validation_results': results}

graph = StateGraph(RollerProcurementState)
graph.add_node('validate', validate_roller_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
