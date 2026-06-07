from typing import TypedDict
from langgraph.graph import StateGraph, END

class MilkingMachineState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    alert_required: bool

def validate_tech_specs(state: MilkingMachineState):
    specs = state.get('spec_sheet', {})
    # Logic to validate milking pressure and hygiene compliance
    is_valid = specs.get('suction_kpa', 0) > 30 and specs.get('food_grade') == True
    return {'validation_passed': is_valid}

def check_compliance_records(state: MilkingMachineState):
    return {'alert_required': not state['validation_passed']}

graph = StateGraph(MilkingMachineState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('compliance', check_compliance_records)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
