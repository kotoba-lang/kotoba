from typing import TypedDict
from langgraph.graph import StateGraph, END

class MagnesiumState(TypedDict):
    part_specs: dict
    validation_passed: bool
    compliance_risk: str

def validate_magnesium_specs(state: MagnesiumState):
    # Simulate material compliance check for metallurgical standards
    if 'alloy_grade' in state.get('part_specs', {}):
        return {'validation_passed': True, 'compliance_risk': 'low'}
    return {'validation_passed': False, 'compliance_risk': 'high'}

def routing_logic(state: MagnesiumState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(MagnesiumState)
graph.add_node('validate', validate_magnesium_specs)
graph.add_node('process', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', routing_logic)
graph.add_edge('process', END)
graph = graph.compile()
