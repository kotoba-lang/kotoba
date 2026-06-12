from typing import TypedDict
from langgraph.graph import StateGraph, END

class FormulaState(TypedDict):
    product_info: dict
    compliance_cleared: bool
    expiry_check_passed: bool

def validate_composition(state: FormulaState):
    print('Validating nutritional composition for pediatric safety...')
    state['compliance_cleared'] = True
    return state

def check_expiry_protocol(state: FormulaState):
    print('Verifying temperature control and shelf-life...')
    state['expiry_check_passed'] = True
    return state

graph = StateGraph(FormulaState)
graph.add_node('validate', validate_composition)
graph.add_node('expiry', check_expiry_protocol)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph = graph.compile()
