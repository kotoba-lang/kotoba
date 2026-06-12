from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForensicState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_airflow(state: ForensicState):
    airflow = state['spec_data'].get('airflow', 0)
    valid = 0.4 <= airflow <= 0.6
    return {'validation_results': [f'Airflow valid: {valid}'], 'is_compliant': valid}

def check_certifications(state: ForensicState):
    certs = state['spec_data'].get('certs', [])
    valid = 'HEPA_H14' in certs
    return {'validation_results': state['validation_results'] + [f'Certs valid: {valid}'], 'is_compliant': state['is_compliant'] and valid}

graph = StateGraph(ForensicState)
graph.add_node('airflow_check', validate_airflow)
graph.add_node('cert_check', check_certifications)
graph.set_entry_point('airflow_check')
graph.add_edge('airflow_check', 'cert_check')
graph.add_edge('cert_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_results': [],
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
