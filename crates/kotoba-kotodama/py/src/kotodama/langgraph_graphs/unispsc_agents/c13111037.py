from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CrudeOilState(TypedDict):
    commodity_code: str
    batch_id: str
    purity_level: float
    safety_clearance: bool
    validation_logs: List[str]

def validate_cargo_safety(state: CrudeOilState) -> CrudeOilState:
    if state['purity_level'] < 0.95:
        state['validation_logs'].append('Purity check failed: Below industrial grade.')
        state['safety_clearance'] = False
    else:
        state['validation_logs'].append('Purity validated.')
    return state

def route_processing(state: CrudeOilState):
    return 'process' if state['safety_clearance'] else END

def process_crude_refinement(state: CrudeOilState) -> CrudeOilState:
    state['validation_logs'].append('Refinement parameters optimized for crude grade.')
    return state

builder = StateGraph(CrudeOilState)
builder.add_node('validate', validate_cargo_safety)
builder.add_node('process', process_crude_refinement)
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_processing)
builder.add_edge('process', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'batch_id': "",
    'purity_level': 0.0,
    'safety_clearance': False,
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
