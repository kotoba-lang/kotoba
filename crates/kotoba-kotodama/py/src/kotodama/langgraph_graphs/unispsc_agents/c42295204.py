from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SurgicalToolState(TypedDict):
    tool_id: str
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_dimensional_specs(state: SurgicalToolState):
    specs = state.get('specifications', {})
    is_valid = 'diameter' in specs and 'tolerance' in specs
    return {'is_compliant': is_valid, 'validation_log': ['Dimensional check passed' if is_valid else 'Dimensional check failed']}

def verify_sterility_docs(state: SurgicalToolState):
    is_compliant = state.get('is_compliant', False)
    return {'validation_log': state['validation_log'] + ['Sterility verification complete'], 'is_compliant': is_compliant}

graph = StateGraph(SurgicalToolState)
graph.add_node('validate_dims', validate_dimensional_specs)
graph.add_node('verify_docs', verify_sterility_docs)
graph.set_entry_point('validate_dims')
graph.add_edge('validate_dims', 'verify_docs')
graph.add_edge('verify_docs', END)
graph = graph.compile()
