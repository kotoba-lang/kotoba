from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class CounterState(TypedDict):
    spec_data: dict
    validation_logs: Annotated[list, operator.add]
    is_compliant: bool

def validate_counter_spec(state: CounterState):
    specs = state.get('spec_data', {})
    logs = []
    compliant = True
    if 'calibration' not in specs:
        logs.append('Missing Calibration Certificate')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

workflow = StateGraph(CounterState)
workflow.add_node('validate', validate_counter_spec)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
