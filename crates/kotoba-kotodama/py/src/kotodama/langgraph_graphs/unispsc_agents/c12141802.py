from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    catalyst_id: str
    purity: float
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_purity(state: CatalystState):
    is_valid = state['purity'] >= 99.5
    return {'validation_log': [f'Purity check: {is_valid}'], 'status': 'valid' if is_valid else 'rejected'}

def check_hazard(state: CatalystState):
    return {'validation_log': ['Hazard assessment: Reviewing MSDS for reactivity limits']}

def process_deployment(state: CatalystState):
    return {'validation_log': ['Deployment: Ready for industrial reactor integration']}

graph = StateGraph(CatalystState)
graph.add_node('validate', validate_purity)
graph.add_node('hazard', check_hazard)
graph.add_node('deploy', process_deployment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'hazard')
graph.add_edge('hazard', 'deploy')
graph.add_edge('deploy', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'catalyst_id': "",
    'purity': 0.0,
    'validation_log': [],
    'status': ""
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
