from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class GeneticsBookState(TypedDict):
    isbn: str
    title: str
    is_verified: bool
    validation_log: Annotated[list, operator.add]

def validate_isbn(state: GeneticsBookState):
    # Simple validation logic placeholder
    valid = len(state['isbn']) >= 10
    return {"is_verified": valid, "validation_log": [f"ISBN validation: {valid}"]}

def catalog_book(state: GeneticsBookState):
    return {"validation_log": [f"Book {state.get('title')} added to catalog"]}

builder = StateGraph(GeneticsBookState)
builder.add_node("validate", validate_isbn)
builder.add_node("catalog", catalog_book)
builder.set_entry_point("validate")
builder.add_edge("validate", "catalog")
builder.add_edge("catalog", END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'isbn': "",
    'title': "",
    'is_verified': False,
    'validation_log': []
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
