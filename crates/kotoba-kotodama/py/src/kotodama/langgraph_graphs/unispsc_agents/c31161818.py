from typing import TypedDict, Annotated, List
import operator
from langgraph.graph import StateGraph, END

class WasherState(TypedDict):
    specs: dict
    validation_log: List[str]
    is_compliant: bool

def validate_material(state: WasherState):
    log = state.get('validation_log', [])
    material = state['specs'].get('material')
    if not material:
        log.append('Material missing')
    return {'validation_log': log}

def structural_check(state: WasherState):
    log = state.get('validation_log', [])
    if state['specs'].get('pressure_mpa', 0) < 0:
        log.append('Invalid pressure rating')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

graph = StateGraph(WasherState)
graph.add_node('material_check', validate_material)
graph.add_node('structural_check', structural_check)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'structural_check')
graph.add_edge('structural_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_log': [],
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
