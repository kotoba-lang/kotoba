from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    raw_input: dict
    validated: bool
    sanitation_check: str
    final_decision: str

def validate_perishable_data(state: ProcessingState):
    # Logic to ensure moisture and temp specs are within valid range
    is_valid = 'moisture' in state['raw_input'] and 'temp' in state['raw_input']
    return {'validated': is_valid}

def perform_sanitation_check(state: ProcessingState):
    # Logic for checking sanitary certificate compliance
    return {'sanitation_check': 'PASS' if state['validated'] else 'FAIL'}

def finalize_procurement(state: ProcessingState):
    return {'final_decision': 'APPROVED' if state['sanitation_check'] == 'PASS' else 'REJECTED'}

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_perishable_data)
graph.add_node('sanitize', perform_sanitation_check)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sanitize')
graph.add_edge('sanitize', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_input': {},
    'validated': False,
    'sanitation_check': "",
    'final_decision': ""
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
