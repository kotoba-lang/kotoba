from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeatherState(TypedDict):
    spec_data: dict
    validated: bool

def validate_materials(state: WeatherState):
    # Business logic for material compliance check
    material = state.get('spec_data', {}).get('material', 'unknown')
    state['validated'] = material in ['EPDM', 'Silicone', 'Thermoplastic']
    return state

def check_thermal(state: WeatherState):
    # Business logic for thermal property validation
    state['validated'] = state['validated'] and state.get('spec_data', {}).get('r_value', 0) > 0
    return state

graph = StateGraph(WeatherState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_thermal', check_thermal)
graph.add_edge('validate_materials', 'check_thermal')
graph.add_edge('check_thermal', END)
graph.set_entry_point('validate_materials')
graph = graph.compile()
