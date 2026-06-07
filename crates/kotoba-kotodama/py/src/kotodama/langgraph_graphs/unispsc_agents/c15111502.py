from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class FiberState(TypedDict):
    batch_id: str
    specifications: dict
    validation_passed: bool
    log: List[str]

def validate_fiber_specs(state: FiberState) -> FiberState:
    specs = state.get('specifications', {})
    # Logic: Validate structural integrity requirements
    if specs.get('tensile_strength', 0) > 3000:
        state['validation_passed'] = True
        state['log'].append('Quality check passed.')
    else:
        state['validation_passed'] = False
        state['log'].append('Quality check failed: insufficient tensile strength.')
    return state

def route_procurement(state: FiberState) -> str:
    return 'VALIDATE' if state['validation_passed'] else 'REJECT'

def finalize_order(state: FiberState) -> FiberState:
    state['log'].append('Procurement order finalized.')
    return state

graph = StateGraph(FiberState)
graph.add_node('VALIDATE', validate_fiber_specs)
graph.add_node('FINALIZE', finalize_order)
graph.set_entry_point('VALIDATE')
graph.add_conditional_edges('VALIDATE', route_procurement, {'VALIDATE': 'FINALIZE', 'REJECT': END})
graph.add_edge('FINALIZE', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'specifications': {},
    'validation_passed': False,
    'log': []
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
