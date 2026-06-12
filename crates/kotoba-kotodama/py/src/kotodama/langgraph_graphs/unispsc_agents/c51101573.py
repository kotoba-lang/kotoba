from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PreservationState(TypedDict):
    vial_id: str
    cryogenic_temp: float
    qc_passed: bool
    log_history: Annotated[Sequence[str], operator.add]

def validate_vial(state: PreservationState) -> PreservationState:
    # Simplified validation logic for cryogenic vials
    is_valid = state.get('cryogenic_temp', 0) <= -150.0
    return {**state, 'qc_passed': is_valid, 'log_history': [f'Vial {state["vial_id"]} QC: {is_valid}']}

def storage_step(state: PreservationState) -> PreservationState:
    return {**state, 'log_history': ['Allocated to cryogenic storage vault']}

graph = StateGraph(PreservationState)
graph.add_node('validate', validate_vial)
graph.add_node('storage', storage_step)
graph.add_edge('validate', 'storage')
graph.add_edge('storage', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'vial_id': "",
    'cryogenic_temp': 0.0,
    'qc_passed': False,
    'log_history': []
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
