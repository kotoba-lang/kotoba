from typing import TypedDict
from langgraph.graph import StateGraph, END

class HeaterProcurementState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: HeaterProcurementState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if specs.get('voltage', 0) <= 0:
        log.append('Invalid voltage detected')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def assemble_procurement(state: HeaterProcurementState):
    return {'validation_log': state['validation_log'] + ['Procurement initiated']}

graph = StateGraph(HeaterProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('assemble', assemble_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'assemble')
graph.add_edge('assemble', END)
graph = graph.compile()
