from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MotorProcurementState(TypedDict):
    part_number: str
    spec_compliance: bool
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_specs(state: MotorProcurementState):
    # Simulate spec validation logic
    return {'validation_logs': ['Validated torque specifications'], 'spec_compliance': True}

def check_export_compliance(state: MotorProcurementState):
    # Simulate dual-use export control check
    return {'validation_logs': ['Export compliance check passed']}

graph = StateGraph(MotorProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)

graph = graph.compile()
