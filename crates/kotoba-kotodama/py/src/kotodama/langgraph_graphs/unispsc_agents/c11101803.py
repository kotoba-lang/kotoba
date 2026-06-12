from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MineralProcessState(TypedDict):
    raw_material_id: str
    purity_check_passed: bool
    safety_validation_logs: Annotated[List[str], operator.add]
    final_classification: str

def validate_material_specs(state: MineralProcessState):
    # Simulated complex validation logic
    return {'purity_check_passed': True, 'safety_validation_logs': ['Material purity verified against industrial standards.']}

def perform_hazardous_assessment(state: MineralProcessState):
    return {'safety_validation_logs': ['Assessment for dangerous goods handling complete.']}

def finalize_procurement_state(state: MineralProcessState):
    return {'final_classification': 'READY_FOR_REFINING'}

graph = StateGraph(MineralProcessState)
graph.add_node('validate', validate_material_specs)
graph.add_node('assess', perform_hazardous_assessment)
graph.add_node('finalize', finalize_procurement_state)

graph.set_entry_point('validate')
graph.add_edge('validate', 'assess')
graph.add_edge('assess', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()
