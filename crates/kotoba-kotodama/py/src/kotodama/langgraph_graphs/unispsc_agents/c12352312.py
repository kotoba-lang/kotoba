from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_id: str
    purity_level: float
    compliance_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_purity(state: ChemicalProcurementState) -> dict:
    if state['purity_level'] >= 99.9:
        return {'compliance_checks': ['purity_verified']}
    return {'compliance_checks': ['purity_failed']}

def safety_review(state: ChemicalProcurementState) -> dict:
    if 'purity_verified' in state['compliance_checks']:
        return {'is_approved': True}
    return {'is_approved': False}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_review', safety_review)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_review')
graph.add_edge('safety_review', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'compliance_checks': [],
    'is_approved': False
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
