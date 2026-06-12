from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralProcessState(TypedDict):
    material_id: str
    purity: float
    safety_clearance: bool
    process_steps: List[str]

def validate_material(state: MineralProcessState) -> MineralProcessState:
    if state['purity'] < 0.99:
        state['process_steps'].append('reject_low_purity')
    else:
        state['process_steps'].append('validate_purity_passed')
    return state

def check_hazards(state: MineralProcessState) -> MineralProcessState:
    state['process_steps'].append('hazard_screening_complete')
    state['safety_clearance'] = True
    return state

builder = StateGraph(MineralProcessState)
builder.add_node('validate', validate_material)
builder.add_node('safety', check_hazards)
builder.set_entry_point('validate')
builder.add_edge('validate', 'safety')
builder.add_edge('safety', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'safety_clearance': False,
    'process_steps': []
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
