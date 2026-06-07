from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from operator import add

class ProcessingState(TypedDict):
    data_input: dict
    processing_steps: Annotated[Sequence[str], add]
    is_validated: bool

def validate_data_integrity(state: ProcessingState):
    print(f"Validating data: {state['data_input']}")
    return {"is_validated": True, "processing_steps": ["validation_pass"]}

def execute_algorithm(state: ProcessingState):
    if not state.get("is_validated", False):
        return {"processing_steps": ["execution_skipped"]}
    print("Executing specialized algorithms.")
    return {"processing_steps": ["algorithm_executed"]}

def finalize_report(state: ProcessingState):
    print("Finalizing processing report.")
    return {"processing_steps": ["report_generated"]}

graph = StateGraph(ProcessingState)
graph.add_node("validate", validate_data_integrity)
graph.add_node("execute", execute_algorithm)
graph.add_node("report", finalize_report)

graph.set_entry_point("validate")
graph.add_edge("validate", "execute")
graph.add_edge("execute", "report")
graph.add_edge("report", END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'data_input': {},
    'processing_steps': [],
    'is_validated': False
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
