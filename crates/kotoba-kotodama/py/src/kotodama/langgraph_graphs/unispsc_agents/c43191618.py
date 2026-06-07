from typing import TypedDict, Annotated, Sequence, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class PeripheralState(TypedDict):
    item_name: str
    model: str
    compatibility_check: bool
    validation_log: Annotated[Sequence[str], add_messages]

def validate_peripheral(state: PeripheralState):
    log = f'Validating compatibility for {state['item_name']}'
    return {'compatibility_check': True, 'validation_log': [log]}

def generate_procurement_spec(state: PeripheralState):
    return {'validation_log': ['Spec generated successfully']}

graph = StateGraph(PeripheralState)
graph.add_node('validate', validate_peripheral)
graph.add_node('spec_gen', generate_procurement_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', 'spec_gen')
graph.add_edge('spec_gen', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_name': "",
    'model': "",
    'compatibility_check': False,
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
