from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    input_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: ProcessingState) -> dict:
    data = state.get('input_data', {})
    logs = ['Validation initiated: checking precision tolerances.']
    compliant = data.get('tolerance', 0.01) <= 0.05
    if compliant:
        logs.append('Specs within tolerance.')
    else:
        logs.append('Error: Tolerance out of range.')
    return {'validation_logs': logs, 'is_compliant': compliant}

def final_report(state: ProcessingState) -> dict:
    return {'validation_logs': ['Report generated: Status ' + ('PASS' if state['is_compliant'] else 'FAIL')]}

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_specs)
graph.add_node('report', final_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
