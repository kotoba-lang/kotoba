from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AutopsyScaleState(TypedDict):
    serial_number: str
    calibration_date: str
    material_spec: str
    is_compliant: bool

def validate_certification(state: AutopsyScaleState) -> AutopsyScaleState:
    state['is_compliant'] = bool(state.get('calibration_date') and 'SUS316' in state.get('material_spec', ''))
    return state

def log_inspection(state: AutopsyScaleState) -> AutopsyScaleState:
    print(f'Inspecting scale: {state["serial_number"]}, Status: {state["is_compliant"]}')
    return state

graph = StateGraph(AutopsyScaleState)
graph.add_node('validate', validate_certification)
graph.add_node('log', log_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'log')
graph.add_edge('log', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'serial_number': "",
    'calibration_date': "",
    'material_spec': "",
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
