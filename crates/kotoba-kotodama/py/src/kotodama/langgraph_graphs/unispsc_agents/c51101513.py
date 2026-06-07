from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class AntiepilepticState(TypedDict):
    lot_id: str
    temp_log: list[float]
    is_compliant: bool
    validation_steps: Annotated[Sequence[str], operator.add]

def validate_cold_chain(state: AntiepilepticState) -> AntiepilepticState:
    compliant = all(2.0 <= temp <= 8.0 for temp in state['temp_log'])
    return {'is_compliant': compliant, 'validation_steps': ['ColdChainValidation']}

def perform_quality_audit(state: AntiepilepticState) -> AntiepilepticState:
    if not state['is_compliant']:
        return {'validation_steps': ['AuditAborted-ColdChainFailure']}
    return {'validation_steps': ['QualityAuditPassed']}

graph = StateGraph(AntiepilepticState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('quality_audit', perform_quality_audit)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'quality_audit')
graph.add_edge('quality_audit', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'lot_id': "",
    'temp_log': [],
    'is_compliant': False,
    'validation_steps': []
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
