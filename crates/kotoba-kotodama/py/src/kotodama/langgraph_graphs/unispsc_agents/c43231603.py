from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class TaxSoftwareState(TypedDict):
    compliance_checks: Annotated[list, operator.add]
    validation_status: str

def validate_compliance(state: TaxSoftwareState):
    return {"compliance_checks": ["Tax Law v2024 Check"], "validation_status": "Validated"}

def generate_report(state: TaxSoftwareState):
    return {"validation_status": "Finalized"}

graph = StateGraph(TaxSoftwareState)
graph.add_node("compliance", validate_compliance)
graph.add_node("reporting", generate_report)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "reporting")
graph.add_edge("reporting", END)
graph = graph.compile()
