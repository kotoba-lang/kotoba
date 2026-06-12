from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SilicaState(TypedDict):
    batch_id: str
    purity_level: float
    particle_distribution: List[float]
    passed_qa: bool

def validate_silica_purity(state: SilicaState) -> dict:
    passed = state['purity_level'] >= 99.9
    return {'passed_qa': passed}

def process_silica_batch(state: SilicaState) -> dict:
    # Simulation of robotics handling and sorting workflow
    return {'batch_id': f'PROC-{state['batch_id']}'}

graph = StateGraph(SilicaState)
graph.add_node('validate', validate_silica_purity)
graph.add_node('process', process_silica_batch)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'particle_distribution': [],
    'passed_qa': False
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
