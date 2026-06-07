from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AnimalFeedState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliance_cleared: bool
    inspection_log: List[str]

def validate_purity(state: AnimalFeedState):
    print(f'Validating purity for {state["batch_id"]}')
    return {'purity_validated': True, 'inspection_log': ['Purity test passed']}

def check_regulations(state: AnimalFeedState):
    print(f'Checking regulatory compliance for {state["batch_id"]}')
    return {'compliance_cleared': True, 'inspection_log': state['inspection_log'] + ['Compliance verified']}

graph = StateGraph(AnimalFeedState)
graph.add_node('purity_check', validate_purity)
graph.add_node('regulatory_check', check_regulations)
graph.add_edge('purity_check', 'regulatory_check')
graph.add_edge('regulatory_check', END)
graph.set_entry_point('purity_check')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_validated': False,
    'compliance_cleared': False,
    'inspection_log': []
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
