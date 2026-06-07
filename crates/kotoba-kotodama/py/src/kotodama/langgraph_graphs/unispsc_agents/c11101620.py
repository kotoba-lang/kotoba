from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalIngestState(TypedDict):
    chemical_id: str
    purity_level: float
    hazard_codes: List[str]
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_purity(state: ChemicalIngestState):
    threshold = 99.9
    if state['purity_level'] < threshold:
        return {'validation_logs': ['Purity level below threshold'], 'is_compliant': False}
    return {'validation_logs': ['Purity verification passed'], 'is_compliant': True}

def check_hazards(state: ChemicalIngestState):
    if 'TOXIC' in state['hazard_codes']:
        return {'validation_logs': ['Toxic hazard detected, trigger special handling'], 'is_compliant': False}
    return {'validation_logs': ['Hazard screening completed'], 'is_compliant': True}

graph = StateGraph(ChemicalIngestState)
graph.add_node('validate', validate_purity)
graph.add_node('hazard_check', check_hazards)
graph.set_entry_point('validate')
graph.add_edge('validate', 'hazard_check')
graph.add_edge('hazard_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'chemical_id': "",
    'purity_level': 0.0,
    'hazard_codes': [],
    'validation_logs': [],
    'is_compliant': False
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
