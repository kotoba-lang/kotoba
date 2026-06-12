from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class OfficePaperState(TypedDict):
    requisition_id: str
    spec_requirements: dict
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_paper_specs(state: OfficePaperState):
    specs = state['spec_requirements']
    logs = []
    if specs.get('basis_weight', 0) < 60:
        logs.append('Insufficient basis weight for standard use.')
    return {'validation_log': logs, 'status': 'validated' if not logs else 'rejected'}

def update_inventory_status(state: OfficePaperState):
    return {'status': 'inventory_updated'}

graph = StateGraph(OfficePaperState)
graph.add_node('validate', validate_paper_specs)
graph.add_node('update', update_inventory_status)
graph.set_entry_point('validate')
graph.add_edge('validate', 'update')
graph.add_edge('update', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'requisition_id': "",
    'spec_requirements': {},
    'validation_log': [],
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
