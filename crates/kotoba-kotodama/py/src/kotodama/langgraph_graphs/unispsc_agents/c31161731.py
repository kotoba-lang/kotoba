from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class WeldNutState(TypedDict):
    part_number: str
    material_spec: str
    weld_integrity_passed: bool
    validation_log: List[str]

def validate_weld_spec(state: WeldNutState):
    log = state.get('validation_log', [])
    # Specialized logic for weld nut tolerance and material vetting
    if state['material_spec'] == 'low_carbon_steel':
        log.append('Material validated for projection welding.')
    else:
        log.append('Warning: Material may inhibit optimal weld nugget formation.')
    return {'validation_log': log, 'weld_integrity_passed': True}

graph = StateGraph(WeldNutState)
graph.add_node('validate', validate_weld_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material_spec': "",
    'weld_integrity_passed': False,
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
