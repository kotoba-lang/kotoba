from typing import TypedDict
from langgraph.graph import StateGraph, END

class LampHousingState(TypedDict):
    spec_sheet: dict
    validation_report: dict
    is_compliant: bool

def validate_thermal_specs(state: LampHousingState):
    """Validates thermal resistance and IP rating for lamp housings."""
    specs = state.get('spec_sheet', {})
    compliant = specs.get('thermal_limit', 0) > 200 and 'IP' in specs
    return {'is_compliant': compliant}

graph = StateGraph(LampHousingState)
graph.add_node('validate_thermal', validate_thermal_specs)
graph.set_entry_point('validate_thermal')
graph.add_edge('validate_thermal', END)
graph = graph.compile()
