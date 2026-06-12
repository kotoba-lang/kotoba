from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class FuelProcurementState(TypedDict):
    commodity_code: str
    spec_requirements: dict
    inspection_results: Annotated[Sequence[str], operator.add]
    status: str

def validate_specs(state: FuelProcurementState) -> FuelProcurementState:
    # Logic to validate chemical properties for solid fuel
    return {'inspection_results': ['Specs validated against safety limits']}

def check_logistics(state: FuelProcurementState) -> FuelProcurementState:
    # Logic to assess transport risk for dangerous goods
    return {'inspection_results': ['Logistics risk assessment complete']}

builder = StateGraph(FuelProcurementState)
builder.add_node('validate_specs', validate_specs)
builder.add_node('check_logistics', check_logistics)
builder.add_edge('validate_specs', 'check_logistics')
builder.set_entry_point('validate_specs')
builder.add_edge('check_logistics', END)
graph = builder.compile()
