from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ForgingState(TypedDict):
    spec_data: dict
    validation_checks: List[str]
    approved: bool

def validate_materials(state: ForgingState):
    grade = state['spec_data'].get('grade')
    is_valid = grade in ['ASTM A576', 'AISI 1045']
    return {'validation_checks': ['Material Grade Verified'] if is_valid else ['Material Grade Invalid']}

def check_dimensions(state: ForgingState):
    tolerance = state['spec_data'].get('tolerance', 0.0)
    status = 'Dimensional Check Passed' if tolerance <= 0.05 else 'Manual Review Required'
    return {'validation_checks': state['validation_checks'] + [status]}

graph = StateGraph(ForgingState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_dimensions', check_dimensions)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_dimensions')
graph.add_edge('check_dimensions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_checks': [],
    'approved': False
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
