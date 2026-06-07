from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OrienteeringGraphState(TypedDict):
    equipment_data: dict
    validation_passes: bool
    log: List[str]

def validate_specs(state: OrienteeringGraphState):
    """Validate compass accuracy and material durability requirements."""
    specs = state.get('equipment_data', {})
    valid = specs.get('accuracy', 0) > 0 and specs.get('weather_resistant', False)
    return {'validation_passes': valid, 'log': ['Specs validated']}

def process_deployment(state: OrienteeringGraphState):
    """Process hardware for competition readiness."""
    if state['validation_passes']:
        return {'log': ['Hardware configured and ready for event']}
    return {'log': ['Validation failed, staging incomplete']}

workflow = StateGraph(OrienteeringGraphState)
workflow.add_node('validate', validate_specs)
workflow.add_node('deploy', process_deployment)
workflow.add_edge('validate', 'deploy')
workflow.add_edge('deploy', END)
workflow.set_entry_point('validate')
graph = workflow.compile()
