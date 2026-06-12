from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class ValveState(TypedDict):
    valve_id: str
    material_certified: bool
    pressure_test_passed: bool
    final_compliance: bool

def validate_materials(state: ValveState):
    # Simulate material check
    return {'material_certified': True}

def perform_pressure_test(state: ValveState):
    # Simulate pressure testing logic
    return {'pressure_test_passed': True}

def finalize_compliance(state: ValveState):
    compliance = state.get('material_certified') and state.get('pressure_test_passed')
    return {'final_compliance': compliance}

graph = StateGraph(ValveState)
graph.add_node('check_material', validate_materials)
graph.add_node('pressure_test', perform_pressure_test)
graph.add_node('finalize', finalize_compliance)
graph.set_entry_point('check_material')
graph.add_edge('check_material', 'pressure_test')
graph.add_edge('pressure_test', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
