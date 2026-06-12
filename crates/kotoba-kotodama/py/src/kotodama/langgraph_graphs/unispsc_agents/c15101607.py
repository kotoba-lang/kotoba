from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    material_id: str
    purity_level: float
    hazard_data: dict
    workflow_status: Annotated[Sequence[str], operator.add]

def validate_material(state: ChemicalIngestState) -> dict:
    # Logic to verify purity and safety standards
    status = 'Validated' if state['purity_level'] > 0.99 else 'Flagged'
    return {'workflow_status': [f'Material {state["material_id"]} {status}']}

def route_for_hazard(state: ChemicalIngestState) -> str:
    return 'process_hazardous' if state['hazard_data'].get('is_dangerous') else END

def process_hazardous(state: ChemicalIngestState) -> dict:
    return {'workflow_status': ['High-risk handling protocols activated']}

graph = StateGraph(ChemicalIngestState)
graph.add_node('validate', validate_material)
graph.add_node('process_hazardous', process_hazardous)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_for_hazard)
graph.add_edge('process_hazardous', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'hazard_data': {},
    'workflow_status': []
}


class _DefaultsWrapper2605231330:
    """Pre-fills missing TypedDict fields before delegating to the compiled graph."""

    __slots__ = ("_inner", "_defaults")

    def __init__(self, inner, defaults):
        self._inner = inner
        self._defaults = defaults

    def _merge(self, input_state):
        if not isinstance(input_state, dict):
            return input_state
        merged = dict(self._defaults)
        merged.update(input_state)
        return merged

    def invoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.invoke(merged, **kwargs)
        return self._inner.invoke(merged, config=config, **kwargs)

    async def ainvoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return await self._inner.ainvoke(merged, **kwargs)
        return await self._inner.ainvoke(merged, config=config, **kwargs)

    def stream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.stream(merged, **kwargs)
        return self._inner.stream(merged, config=config, **kwargs)

    async def astream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            async for chunk in self._inner.astream(merged, **kwargs):
                yield chunk
            return
        async for chunk in self._inner.astream(merged, config=config, **kwargs):
            yield chunk

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)


graph = _DefaultsWrapper2605231330(graph, _DEFAULTS_2605231330)
