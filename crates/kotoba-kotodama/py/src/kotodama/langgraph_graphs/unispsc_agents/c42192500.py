from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EquipmentProtectorState(TypedDict):
    specifications: dict
    validation_log: List[str]
    approved: bool

def validate_compliance(state: EquipmentProtectorState):
    specs = state.get('specifications', {})
    if 'ISO' in specs.get('certifications', []):
        return {'validation_log': ['ISO compliance verified'], 'approved': True}
    return {'validation_log': ['Compliance check failed'], 'approved': False}

def check_dimensions(state: EquipmentProtectorState):
    if state.get('approved'):
        return {'validation_log': state['validation_log'] + ['Dimensions matched']}
    return state

graph = StateGraph(EquipmentProtectorState)
graph.add_node('validate', validate_compliance)
graph.add_node('dimensions', check_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'dimensions')
graph.add_edge('dimensions', END)
graph = graph.compile()
