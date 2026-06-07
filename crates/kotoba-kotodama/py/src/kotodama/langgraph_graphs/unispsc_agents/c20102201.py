from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CylinderSpec(TypedDict):
    pressure_mpa: float
    bore_mm: float
    status: str
    validation_logs: List[str]

def validate_pressure(state: CylinderSpec) -> CylinderSpec:
    if state['pressure_mpa'] > 70.0:
        state['status'] = 'HIGH_PRESSURE_REVIEW'
        state['validation_logs'].append('High pressure alert: Safety validation required')
    else:
        state['status'] = 'APPROVED'
    return state

def check_dimensions(state: CylinderSpec) -> CylinderSpec:
    if state['bore_mm'] <= 0:
        state['status'] = 'REJECTED'
        state['validation_logs'].append('Invalid bore diameter')
    return state

builder = StateGraph(CylinderSpec)
builder.add_node('validate_pressure', validate_pressure)
builder.add_node('check_dimensions', check_dimensions)
builder.add_edge('validate_pressure', 'check_dimensions')
builder.add_edge('check_dimensions', END)
builder.set_entry_point('validate_pressure')
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'pressure_mpa': 0.0,
    'bore_mm': 0.0,
    'status': "",
    'validation_logs': []
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
