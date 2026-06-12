from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class DrillingFluidState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_results: Annotated[List[str], operator.add]
    approval_status: bool

def validate_viscosity(state: DrillingFluidState):
    print('Validating fluid viscosity profile...')
    state['validation_results'].append('viscosity_verified')
    return state

def check_environmental_compliance(state: DrillingFluidState):
    print('Checking environmental toxicity rating...')
    state['validation_results'].append('environmental_compliance_passed')
    return state

def finalize_approval(state: DrillingFluidState):
    state['approval_status'] = True
    return state

graph = StateGraph(DrillingFluidState)
graph.add_node('validate_viscosity', validate_viscosity)
graph.add_node('check_env', check_environmental_compliance)
graph.add_node('finalize', finalize_approval)

graph.add_edge('validate_viscosity', 'check_env')
graph.add_edge('check_env', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate_viscosity')
graph = graph.compile()
