from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    input_data: dict
    is_compliant: bool
    validation_log: list

def validate_ink_remover(state: State):
    data = state.get('input_data', {})
    logs = []
    compliant = True
    if 'ph' not in data or not (5.0 <= data['ph'] <= 8.0):
        logs.append('pH level outside safe dermatological range')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': logs}

workflow = StateGraph(State)
workflow.add_node('validate', validate_ink_remover)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
