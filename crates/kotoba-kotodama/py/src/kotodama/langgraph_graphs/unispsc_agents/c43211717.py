from typing import TypedDict
from langgraph.graph import StateGraph, END

class OCRProcessState(TypedDict):
    input_path: str
    config: dict
    validation_result: bool
    engine_output: str

def validate_format(state: OCRProcessState):
    path = state['input_path']
    return {'validation_result': path.lower().endswith(('.pdf', '.tiff', '.png'))}

def run_ocr(state: OCRProcessState):
    # Simulate high-precision OCR extraction workflow
    return {'engine_output': 'Processed text data extraction complete.'}

graph = StateGraph(OCRProcessState)
graph.add_node('validate', validate_format)
graph.add_node('execute', run_ocr)
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'input_path': "",
    'config': {},
    'validation_result': False,
    'engine_output': ""
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
