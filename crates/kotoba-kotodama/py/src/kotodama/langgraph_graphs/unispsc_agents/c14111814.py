from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from operator import add

class FileProcState(TypedDict):
    doc_count: int
    validation_errors: Annotated[Sequence[str], add]
    is_archivable: bool

def validate_filing_compliance(state: FileProcState):
    # Simple business logic: check if doc_count allows for standard filing
    is_valid = state['doc_count'] > 0
    return {'is_archivable': is_valid}

def categorize_document(state: FileProcState):
    # Simulate classification logic
    if state['doc_count'] > 1000:
        return {'validation_errors': ['Bulk storage handling required']}
    return {'validation_errors': []}

graph = StateGraph(FileProcState)
graph.add_node('validate', validate_filing_compliance)
graph.add_node('categorize', categorize_document)
graph.set_entry_point('validate')
graph.add_edge('validate', 'categorize')
graph.add_edge('categorize', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'doc_count': 0,
    'validation_errors': [],
    'is_archivable': False
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
