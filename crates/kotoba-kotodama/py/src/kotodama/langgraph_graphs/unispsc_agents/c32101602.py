from typing import TypedDict
from langgraph.graph import StateGraph, END

class DRAMState(TypedDict):
    spec_data: dict
    validation_errors: list
    is_compliant: bool

def validate_dram_tech(state: DRAMState):
    spec = state.get('spec_data', {})
    errors = []
    if spec.get('clock_speed_mhz', 0) < 2133: errors.append('Insufficient clock speed')
    return {'validation_errors': errors, 'is_compliant': len(errors) == 0}

def check_export_compliance(state: DRAMState):
    if state.get('is_compliant'):
        print('Checking dual-use export regulations...')
    return {}

graph = StateGraph(DRAMState)
graph.add_node('validate', validate_dram_tech)
graph.add_node('export_check', check_export_compliance)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
