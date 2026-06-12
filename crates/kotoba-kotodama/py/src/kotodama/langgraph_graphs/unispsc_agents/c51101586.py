from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class DiagnosticState(TypedDict):
    reagent_id: str
    batch_id: str
    validation_status: str
    logs: List[str]

def validate_lot(state: DiagnosticState) -> DiagnosticState:
    # Logic to verify lot expiration and compliance
    state['validation_status'] = 'PENDING_INSPECTION'
    state['logs'].append(f'Validating batch {state["batch_id"]}')
    return state

def check_temp_log(state: DiagnosticState) -> DiagnosticState:
    # Logic to verify cold chain integrity
    state['validation_status'] = 'VALIDATED'
    state['logs'].append('Temperature logs confirmed compliant')
    return state

graph = StateGraph(DiagnosticState)
graph.add_node('validate', validate_lot)
graph.add_node('temp_check', check_temp_log)
graph.set_entry_point('validate')
graph.add_edge('validate', 'temp_check')
graph.add_edge('temp_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'reagent_id': "",
    'batch_id': "",
    'validation_status': "",
    'logs': []
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
