from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicalDeviceState(TypedDict):
    device_id: str
    specifications: dict
    validation_passed: bool

def validate_materials(state: MedicalDeviceState):
    # Simulate material check for biocompatibility
    state['validation_passed'] = 'material' in state['specifications']
    return state

def check_certification(state: MedicalDeviceState):
    # Simulate regulatory audit
    state['validation_passed'] = state.get('validation_passed', False) and 'iso13485' in state['specifications']
    return state

graph = StateGraph(MedicalDeviceState)
graph.add_node('material_check', validate_materials)
graph.add_node('cert_check', check_certification)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'cert_check')
graph.add_edge('cert_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'specifications': {},
    'validation_passed': False
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
