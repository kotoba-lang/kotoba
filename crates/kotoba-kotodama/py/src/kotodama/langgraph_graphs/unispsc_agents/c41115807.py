from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnalyzerState(TypedDict):
    device_id: str
    calibration_status: bool
    reagent_batch: str
    validation_score: float

def validate_chemistry_analyzer(state: AnalyzerState):
    print(f'Validating analyzer {state["device_id"]}')
    return {'validation_score': 0.95 if state['calibration_status'] else 0.0}

def process_reagents(state: AnalyzerState):
    print(f'Checking reagent batch: {state["reagent_batch"]}')
    return state

graph = StateGraph(AnalyzerState)
graph.add_node("validate", validate_chemistry_analyzer)
graph.add_node("process", process_reagents)
graph.set_entry_point("validate")
graph.add_edge("validate", "process")
graph.add_edge("process", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'calibration_status': False,
    'reagent_batch': "",
    'validation_score': 0.0
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
