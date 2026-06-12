from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CompilerState(TypedDict):
    source_code_path: str
    build_config: dict
    compilation_log: List[str]
    is_valid: bool

def validate_environment(state: CompilerState) -> CompilerState:
    # Logic to check system dependencies
    state['is_valid'] = True
    state['compilation_log'].append('Environment validated.')
    return state

def compile_source(state: CompilerState) -> CompilerState:
    # Logic for invoking build tools
    state['compilation_log'].append('Compilation started.')
    return state

def run_tests(state: CompilerState) -> CompilerState:
    # Logic for post-compilation verification
    state['compilation_log'].append('Tests completed successfully.')
    return state

workflow = StateGraph(CompilerState)
workflow.add_node('validate', validate_environment)
workflow.add_node('compile', compile_source)
workflow.add_node('test', run_tests)

workflow.set_entry_point('validate')
workflow.add_edge('validate', 'compile')
workflow.add_edge('compile', 'test')
workflow.add_edge('test', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'source_code_path': "",
    'build_config': {},
    'compilation_log': [],
    'is_valid': False
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
