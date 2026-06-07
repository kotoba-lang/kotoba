from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class PaperProcurementState(TypedDict):
    paper_specs: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_specs(state: PaperProcurementState):
    specs = state['paper_specs']
    logs = []
    compliant = True
    if not specs.get('acid_free_certification'):
        logs.append('Warning: Missing acid-free certification')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def archival_check(state: PaperProcurementState):
    if state['paper_specs'].get('archival_longevity_rating', 0) < 100:
        return {'validation_logs': ['Insufficient archival rating for long-term storage']}
    return {'validation_logs': ['Archival standards met']}

workflow = StateGraph(PaperProcurementState)
workflow.add_node('validate', validate_specs)
workflow.add_node('archive', archival_check)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'archive')
workflow.add_edge('archive', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'paper_specs': {},
    'validation_logs': [],
    'is_compliant': False
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
