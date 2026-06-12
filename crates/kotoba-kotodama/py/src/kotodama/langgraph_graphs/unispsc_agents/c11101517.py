from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SiliconState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_silicon_specs(state: SiliconState):
    specs = state.get('spec_requirements', {})
    logs = []
    compliant = True
    if specs.get('purity_percentage', 0) < 99.9999999:
        logs.append('Insufficient purity for semiconductor grade.')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

workflow = StateGraph(SiliconState)
workflow.add_node('validate', validate_silicon_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
