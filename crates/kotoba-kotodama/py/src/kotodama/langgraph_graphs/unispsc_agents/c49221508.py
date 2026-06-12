from typing import TypedDict
from langgraph.graph import StateGraph, END

class BasketballHoopState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: BasketballHoopState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if specs.get('rim_diameter_mm') != 450:
        log.append('Invalid rim diameter')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

graph_builder = StateGraph(BasketballHoopState)
graph_builder.add_node('validate', validate_specs)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', END)
graph = graph_builder.compile()
