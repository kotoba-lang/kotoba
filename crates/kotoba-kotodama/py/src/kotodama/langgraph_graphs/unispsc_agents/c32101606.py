from typing import TypedDict
from langgraph.graph import StateGraph, END

class EEPROMProcurementState(TypedDict):
    part_number: str
    spec_sheet: dict
    compliance_check: bool

def validate_eeprom_specs(state: EEPROMProcurementState):
    # Simulate logic checking for dual-use sensitivity and spec validity
    print(f'Validating EEPROM: {state.get('part_number')}')
    return {'compliance_check': True}

def approval_workflow(state: EEPROMProcurementState):
    return {'compliance_check': True}

graph = StateGraph(EEPROMProcurementState)
graph.add_node('validate', validate_eeprom_specs)
graph.add_node('approval', approval_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
