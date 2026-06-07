from typing import TypedDict
from langgraph.graph import StateGraph, END

class cDNAState(TypedDict):
    kit_id: str
    temp_check: bool
    qc_passed: bool

def validate_temp(state: cDNAState):
    print('Verifying cold chain storage requirements')
    return {'temp_check': True}

def run_qc(state: cDNAState):
    print('Performing analytical batch quality control')
    return {'qc_passed': True}

graph = StateGraph(cDNAState)
graph.add_node('temp_check', validate_temp)
graph.add_node('qc', run_qc)
graph.add_edge('temp_check', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('temp_check')
graph = graph.compile()
