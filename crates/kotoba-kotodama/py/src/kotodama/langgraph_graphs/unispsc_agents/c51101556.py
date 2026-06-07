from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    temperature_logs: Annotated[Sequence[float], operator.add]
    is_compliant: bool

def validate_cold_chain(state: PharmState):
    avg_temp = sum(state['temperature_logs']) / len(state['temperature_logs']) if state['temperature_logs'] else 25.0
    return {'is_compliant': 2.0 <= avg_temp <= 8.0}

def process_batch(state: PharmState):
    print(f'Processing batch {state['batch_id']}: Compliance={state['is_compliant']}')
    return state

builder = StateGraph(PharmState)
builder.add_node('validate', validate_cold_chain)
builder.add_node('process', process_batch)
builder.set_entry_point('validate')
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'temperature_logs': [],
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
