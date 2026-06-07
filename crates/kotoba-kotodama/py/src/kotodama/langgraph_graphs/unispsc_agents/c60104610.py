from typing import TypedDict
from langgraph.graph import StateGraph, END

class AirTableState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_specs(state: AirTableState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['load_capacity', 'flatness'])
    print(f'Validating specs: {specs}')
    return {'validation_result': is_valid}

def process_procurement(state: AirTableState):
    if state['validation_result']:
        print('Procurement request approved.')
    else:
        print('Procurement request rejected: missing specs.')
    return state

graph = StateGraph(AirTableState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
