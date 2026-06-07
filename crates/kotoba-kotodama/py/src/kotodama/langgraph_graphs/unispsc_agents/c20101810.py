from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningPartsState(TypedDict):
    part_id: str
    spec_compliance: bool
    inspection_result: str
    workflow_log: List[str]

def validate_specs(state: MiningPartsState) -> MiningPartsState:
    # Logic to verify material grade and abrasion resistance
    state['spec_compliance'] = True
    state['workflow_log'].append('Specs validated')
    return state

def run_inspection(state: MiningPartsState) -> MiningPartsState:
    # Simulation of physical inspection process
    state['inspection_result'] = 'PASSED'
    state['workflow_log'].append('Physical inspection complete')
    return state

graph = StateGraph(MiningPartsState)
graph.add_node('validate', validate_specs)
graph.add_node('inspect', run_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'spec_compliance': False,
    'inspection_result': "",
    'workflow_log': []
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
