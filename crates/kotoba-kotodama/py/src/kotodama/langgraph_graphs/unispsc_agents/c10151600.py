from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FarmingMaterialState(TypedDict):
    batch_id: str
    composition: dict
    validation_score: float
    status: str

def validate_material(state: FarmingMaterialState) -> FarmingMaterialState:
    comp = state.get('composition', {})
    score = 0.0
    if comp.get('nitrogen', 0) > 0:
        score += 0.5
    if comp.get('organic', False):
        score += 0.5
    return {**state, 'validation_score': score, 'status': 'VALIDATED' if score >= 0.5 else 'REJECTED'}

def process_procurement(state: FarmingMaterialState) -> FarmingMaterialState:
    return {**state, 'status': 'PROCESSED'}

builder = StateGraph(FarmingMaterialState)
builder.add_node('validate', validate_material)
builder.add_node('process', process_procurement)
builder.set_entry_point('validate')
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
graph = builder.compile()
