from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if specs.get('tensile_strength', 0) < 500:
        log.append('Tensile strength below safety threshold')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def process_procurement(state: ProcurementState):
    print('Processing baseball backstop order...')
    return {'validation_log': state['validation_log'] + ['Order processed']}

builder = StateGraph(ProcurementState)
builder.add_node('validator', validate_specs)
builder.add_node('procure', process_procurement)
builder.set_entry_point('validator')
builder.add_edge('validator', 'procure')
builder.add_edge('procure', END)
graph = builder.compile()
