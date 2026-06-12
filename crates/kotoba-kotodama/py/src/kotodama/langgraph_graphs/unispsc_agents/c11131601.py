from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    commodity_code: str
    purity: float
    origin: str
    compliance_cleared: bool

def validate_origin(state: MineralState) -> MineralState:
    # Logic to verify origin against sanctions list
    state['compliance_cleared'] = state['origin'] not in ['restricted_region_a', 'restricted_region_b']
    return state

def check_purity(state: MineralState) -> MineralState:
    # Logic to validate industrial grade thresholds
    if state['purity'] < 0.95:
        print(f'Purity {state['purity']} below industrial standard.')
    return state

workflow = StateGraph(MineralState)
workflow.add_node('validate_origin', validate_origin)
workflow.add_node('check_purity', check_purity)
workflow.set_entry_point('validate_origin')
workflow.add_edge('validate_origin', 'check_purity')
workflow.add_edge('check_purity', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity': 0.0,
    'origin': "",
    'compliance_cleared': False
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
