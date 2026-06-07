from typing import TypedDict
from langgraph.graph import StateGraph, END

class CircuitBreakerState(TypedDict):
    specs: dict
    validated: bool
    error_log: list

def validate_specs(state: CircuitBreakerState):
    required = ['Rated Current', 'Rated Voltage', 'Interrupting Capacity']
    errors = [f'Missing {f}' for f in required if f not in state['specs']]
    return {'validated': len(errors) == 0, 'error_log': errors}

def route_by_validation(state: CircuitBreakerState):
    return 'process' if state['validated'] else END

def process_breaker(state: CircuitBreakerState):
    print('Processing validated magnetic circuit breaker specs.')
    return state

builder = StateGraph(CircuitBreakerState)
builder.add_node('validate', validate_specs)
builder.add_node('process', process_breaker)
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_by_validation)
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validated': False,
    'error_log': []
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
