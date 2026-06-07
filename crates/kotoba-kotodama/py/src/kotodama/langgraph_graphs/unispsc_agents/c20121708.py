from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ControlState(TypedDict):
    board_id: str
    inspection_passed: bool
    thermal_test_result: float
    status: str

def validate_pcb_spec(state: ControlState) -> ControlState:
    # Specialized validation logic for high-precision industrial PCB
    if state['thermal_test_result'] < 85.0:
        state['inspection_passed'] = True
        state['status'] = 'COMPLIANT'
    else:
        state['inspection_passed'] = False
        state['status'] = 'FAILED_THERMAL_THRESHOLD'
    return state

def assembly_workflow(state: ControlState) -> ControlState:
    state['status'] = 'READY_FOR_INTEGRATION'
    return state

builder = StateGraph(ControlState)
builder.add_node('validate', validate_pcb_spec)
builder.add_node('assemble', assembly_workflow)
builder.set_entry_point('validate')
builder.add_edge('validate', 'assemble')
builder.add_edge('assemble', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'board_id': "",
    'inspection_passed': False,
    'thermal_test_result': 0.0,
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
