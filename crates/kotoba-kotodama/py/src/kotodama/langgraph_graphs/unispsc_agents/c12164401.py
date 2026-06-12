from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class MaterialState(TypedDict):
    material_code: str
    purity_level: float
    inspection_passed: bool
    logs: Annotated[List[str], operator.add]

def validate_material(state: MaterialState):
    if state['purity_level'] >= 99.9:
        return {'inspection_passed': True, 'logs': ['Purity validation passed']}
    else:
        return {'inspection_passed': False, 'logs': ['Purity below threshold']}

def process_procurement(state: MaterialState):
    if state['inspection_passed']:
        return {'logs': ['Proceeding with procurement order']}
    return {'logs': ['Procurement halted due to quality failure']}

graph = StateGraph(MaterialState)
graph.add_node('validate', validate_material)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'purity_level': 0.0,
    'inspection_passed': False,
    'logs': []
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
