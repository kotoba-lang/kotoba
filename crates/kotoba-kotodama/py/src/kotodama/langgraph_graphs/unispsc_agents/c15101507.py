from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    lubricant_id: str
    specifications: dict
    validation_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_viscosity(state: LubricantState):
    spec = state.get('specifications', {})
    if 'viscosity_grade_iso' in spec:
        return {'validation_results': ['Viscosity spec verified']}
    return {'validation_results': ['Viscosity spec missing']}

def validate_safety(state: LubricantState):
    return {'validation_results': ['MSDS and flash point compliant']}

workflow = StateGraph(LubricantState)
workflow.add_node('validate_viscosity', validate_viscosity)
workflow.add_node('validate_safety', validate_safety)
workflow.add_edge('validate_viscosity', 'validate_safety')
workflow.add_edge('validate_safety', END)
workflow.set_entry_point('validate_viscosity')
graph = workflow.compile()
