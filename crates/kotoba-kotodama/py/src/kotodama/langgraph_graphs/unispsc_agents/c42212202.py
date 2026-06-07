from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PillOrganizerState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_accessibility(state: PillOrganizerState):
    log = state.get('validation_log', [])
    compliance = state['specs'].get('accessibility_certified', False)
    log.append('Checked ADA/Accessibility compliance')
    return {'is_compliant': compliance, 'validation_log': log}

def check_material_safety(state: PillOrganizerState):
    log = state.get('validation_log', [])
    is_safe = state['specs'].get('bpa_free', True)
    log.append('Validated chemical safety for medical use')
    return {'is_compliant': state['is_compliant'] and is_safe, 'validation_log': log}

graph = StateGraph(PillOrganizerState)
graph.add_node('accessibility', validate_accessibility)
graph.add_node('safety', check_material_safety)
graph.set_entry_point('accessibility')
graph.add_edge('accessibility', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'is_compliant': False,
    'validation_log': []
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
