from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class StainerState(TypedDict):
    specifications: dict
    validation_passed: bool
    error_log: List[str]

def validate_tech_specs(state: StainerState):
    specs = state.get('specifications', {})
    required = ['iso_13485_certification', 'reagent_compatibility']
    missing = [req for req in required if req not in specs]
    return {'validation_passed': len(missing) == 0, 'error_log': missing}

def check_compliance(state: StainerState):
    # Regulatory logic for microbiology hardware
    if state['validation_passed']:
        return 'compliant'
    return 'non_compliant'

graph = StateGraph(StainerState)
graph.add_node('validate', validate_tech_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
