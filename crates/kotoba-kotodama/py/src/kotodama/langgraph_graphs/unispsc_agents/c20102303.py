from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotEndEffectorState(TypedDict):
    part_id: str
    specifications: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: RobotEndEffectorState):
    specs = state.get('specifications', {})
    passed = 'payload_capacity_kg' in specs and 'repeatability_mm' in specs
    return {'validation_passed': passed, 'log': [f'Specs validation: {passed}']}

def assembly_workflow(state: RobotEndEffectorState):
    return {'log': state['log'] + ['Workflow: End-effector assembly simulation complete.']}

def build_graph():
    graph = StateGraph(RobotEndEffectorState)
    graph.add_node('validate', validate_specs)
    graph.add_node('assemble', assembly_workflow)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'assemble')
    graph.add_edge('assemble', END)
    return graph.compile()

graph = build_graph()
