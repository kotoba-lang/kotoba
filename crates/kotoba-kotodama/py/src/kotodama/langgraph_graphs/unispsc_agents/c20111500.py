from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ToolProcessState(TypedDict):
    raw_spec: dict
    validated_metrics: dict
    risk_assessment: list
    is_approved: bool

def validate_specs(state: ToolProcessState) -> ToolProcessState:
    spec = state.get('raw_spec', {})
    accuracy = spec.get('accuracy', 0.0)
    state['validated_metrics'] = {'valid': accuracy < 0.005}
    return state

def risk_screening(state: ToolProcessState) -> ToolProcessState:
    if state['validated_metrics'].get('valid'):
        state['risk_assessment'] = ['standard']
        state['is_approved'] = True
    else:
        state['risk_assessment'] = ['service-delivery-risk']
        state['is_approved'] = False
    return state

builder = StateGraph(ToolProcessState)
builder.add_node('validate', validate_specs)
builder.add_node('screen', risk_screening)
builder.add_edge('validate', 'screen')
builder.add_edge('screen', END)
builder.set_entry_point('validate')
graph = builder.compile()
