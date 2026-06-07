from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BathSeatState(TypedDict):
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_safety(state: BathSeatState):
    specs = state.get('specifications', {})
    logs = []
    compliant = True
    if specs.get('max_weight', 0) < 100:
        logs.append('Weight capacity below industry standard')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': logs}

workflow = StateGraph(BathSeatState)
workflow.add_node('safety_check', validate_safety)
workflow.set_entry_point('safety_check')
workflow.add_edge('safety_check', END)
graph = workflow.compile()
