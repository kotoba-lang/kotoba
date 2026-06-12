from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PumpProcurementState(TypedDict):
    requirements: dict
    validation_steps: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: PumpProcurementState):
    # Simulate technical validation logic
    specs = state.get('requirements', {})
    status = specs.get('pressure_rating', 0) > 0
    return {'validation_steps': ['Validation: Pressure Rating Checked'], 'is_compliant': status}

def check_compliance(state: PumpProcurementState):
    # Simulate regulatory/standard check
    return {'validation_steps': ['Compliance: ISO/Industry Standards Verified']}

graph = StateGraph(PumpProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
