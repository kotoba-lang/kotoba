from typing import TypedDict
from langgraph.graph import StateGraph, END

class DuctCleanState(TypedDict):
    spec_sheet: dict
    validation_results: list

def validate_airflow(state: DuctCleanState):
    cfm = state['spec_sheet'].get('cfm', 0)
    if cfm < 500: return {'validation_results': ['Airflow insufficient']}
    return {'validation_results': ['Airflow validated']}

def inspect_filters(state: DuctCleanState):
    if state['spec_sheet'].get('hepa_grade') != 'H13':
        return {'validation_results': state['validation_results'] + ['Filter insufficient']}
    return {'validation_results': state['validation_results'] + ['Filter compliant']}

graph = StateGraph(DuctCleanState)
graph.add_node('validate_airflow', validate_airflow)
graph.add_node('inspect_filters', inspect_filters)
graph.set_entry_point('validate_airflow')
graph.add_edge('validate_airflow', 'inspect_filters')
graph.add_edge('inspect_filters', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_sheet': {},
    'validation_results': []
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
