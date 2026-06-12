from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PipeState(TypedDict):
    specs: dict
    validation_passed: bool
    compliance_report: str

def validate_pressure(state: PipeState):
    pressure = state['specs'].get('pressure_rating', 0)
    state['validation_passed'] = pressure > 0
    state['compliance_report'] = 'Pressure check passed' if state['validation_passed'] else 'Pressure failure'
    return state

def check_standards(state: PipeState):
    has_asme = 'ASME' in state['specs'].get('certifications', [])
    state['validation_passed'] = state['validation_passed'] and has_asme
    return state

graph = StateGraph(PipeState)
graph.add_node('validate_pressure', validate_pressure)
graph.add_node('check_standards', check_standards)
graph.set_entry_point('validate_pressure')
graph.add_edge('validate_pressure', 'check_standards')
graph.add_edge('check_standards', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'specs': {},
    'validation_passed': False,
    'compliance_report': ""
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
