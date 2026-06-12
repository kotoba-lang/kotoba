from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    compliance_checks: Annotated[Sequence[str], operator.add]
    validation_passed: bool

def validate_certification(state: ReagentState) -> ReagentState:
    print(f'Validating ISO 13485 for {state[reagent_id]}')
    return {compliance_checks: ['ISO_13485_CHECKED']}

def check_temp_logs(state: ReagentState) -> ReagentState:
    print(f'Verifying temperature storage logs for {state[reagent_id]}')
    return {compliance_checks: ['TEMP_LOG_VERIFIED'], validation_passed: True}

graph = StateGraph(ReagentState)
graph.add_node('cert_check', validate_certification)
graph.add_node('temp_check', check_temp_logs)
graph.add_edge('cert_check', 'temp_check')
graph.add_edge('temp_check', END)
graph.set_entry_point('cert_check')
graph = graph.compile()
