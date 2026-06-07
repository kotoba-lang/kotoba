from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class HayState(TypedDict):
    hay_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_moisture(state: HayState) -> HayState:
    moisture = state['hay_data'].get('moisture_percentage', 0)
    if moisture > 15:
        return {'validation_logs': ['Moisture level too high for storage'], 'is_approved': False}
    return {'validation_logs': ['Moisture level compliant'], 'is_approved': True}

def check_phytosanitary(state: HayState) -> HayState:
    if not state['hay_data'].get('phytosanitary_certificate'):
        return {'validation_logs': ['Missing phytosanitary certificate'], 'is_approved': False}
    return {'validation_logs': ['Certificate verified'], 'is_approved': True}

graph = StateGraph(HayState)
graph.add_node('check_moisture', validate_moisture)
graph.add_node('check_cert', check_phytosanitary)
graph.set_entry_point('check_moisture')
graph.add_edge('check_moisture', 'check_cert')
graph.add_edge('check_cert', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'hay_data': {},
    'validation_logs': [],
    'is_approved': False
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
