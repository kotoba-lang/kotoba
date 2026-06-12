from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlywheelState(TypedDict):
    specs: dict
    validated: bool
    error: str

async def validate_specs(state: FlywheelState):
    required = ['Material Grade', 'Dynamic Balancing Report']
    if all(k in state['specs'] for k in required):
        return {'validated': True}
    return {'validated': False, 'error': 'Missing required specs'}

async def check_tolerance(state: FlywheelState):
    if state.get('validated'):
        return {'validated': True}
    return {'validated': False}

graph = StateGraph(FlywheelState)
graph.add_node('validate', validate_specs)
graph.add_node('tolerance', check_tolerance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'tolerance')
graph.add_edge('tolerance', END)
graph = graph.compile()
