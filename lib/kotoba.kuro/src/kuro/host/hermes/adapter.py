"""Explicit serial browser profile. No emulation of OS threads or subprocesses."""
import os, sys, io, tarfile, json, traceback
from concurrent.futures import Executor, Future
from contextvars import copy_context
os.environ['HERMES_HOME'] = '/workspace/hermes-home'
os.makedirs(os.environ['HERMES_HOME'], exist_ok=True)
with open(os.environ['HERMES_HOME'] + '/config.yaml', 'w') as config:
    json.dump({'model': {'default': _kuro_inputs['model'], 'provider': 'custom',
        'base_url': 'http://browser.invalid/v1', 'context_length': _kuro_inputs['contextLength'], 'streaming': _kuro_inputs.get('streaming', True)},
        'tools': {'tool_search': {'enabled': 'off'}},
        'agent': {'environment_probe': False}, 'compression': {'enabled': False}}, config)
source_root = '/workspace/hermes-source'
os.makedirs(source_root, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(bytes(_kuro_archive)), mode='r:gz') as archive:
    archive.extractall(source_root, filter='data')
# Native remote-backend synchronization is outside the browser profile. Defer its
# optional process inspection import; any attempted use fails explicitly.
from pathlib import Path
sync_path = Path(source_root) / 'tools/environments/file_sync.py'
sync_source = sync_path.read_text()
if sync_source.count('import psutil\n') != 1:
    raise RuntimeError('Hermes source changed: browser profile must be requalified')
process_check = 'return psutil.pid_exists(int(pid_part))'
if sync_source.count(process_check) != 1:
    raise RuntimeError('Hermes process-sync code changed: requalification required')
sync_path.write_text(sync_source.replace('import psutil\n', '').replace(process_check,
    "raise RuntimeError('native process inspection unavailable in browser profile')"))
sys.path.insert(0, source_root)
os.chdir(source_root)

class SerialExecutor(Executor):
    """Foreground Futures with context propagation; concurrency is deliberately one."""
    def __init__(self, *args, **kwargs):
        self.closed = False
    def submit(self, fn, /, *args, **kwargs):
        if self.closed:
            raise RuntimeError('executor is shut down')
        future = Future()
        future.set_running_or_notify_cancel()
        try:
            future.set_result(copy_context().run(fn, *args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future
    def shutdown(self, wait=True, *, cancel_futures=False):
        self.closed = True

# Replace the actual Hermes tool executor seam before its consumers import it.
import tools.daemon_pool
tools.daemon_pool.DaemonThreadPoolExecutor = SerialExecutor

def bridge(operation, value):
    return json.loads(_kuro_rpc(operation, json.dumps(value)))

def run_browser_agent(prompt):
    import logging, hermes_logging
    hermes_logging._register_queued_handler = lambda handler: logging.getLogger().addHandler(handler)
    from run_agent import AIAgent
    import httpx
    from agent import model_metadata_http
    def unsupported_metadata(*args, **kwargs):
        raise RuntimeError('browser profile requires configured model metadata')
    model_metadata_http.get = unsupported_metadata
    model_metadata_http.stream = unsupported_metadata
    from openai import OpenAI
    import base64
    class BrowserByteStream(httpx.SyncByteStream):
        def __init__(self, stream_id):
            self.stream_id = stream_id
            self.closed = False
        def __iter__(self):
            while not self.closed:
                chunk = bridge('stream-read', {'id': self.stream_id})
                if chunk['done']:
                    self.closed = True
                    return
                yield base64.b64decode(chunk['bytes'])
        def close(self):
            if not self.closed:
                self.closed = True
                bridge('stream-close', {'id': self.stream_id})
    class BrowserTransport(httpx.BaseTransport):
        def handle_request(self, request):
            if request.method != 'POST' or not request.url.path.endswith('/chat/completions'):
                raise RuntimeError('browser profile only supports chat completions')
            payload = json.loads(request.content)
            response = bridge('stream-open' if payload.get('stream') else 'model', payload)
            if response.get('streamId'):
                return httpx.Response(response['status'], headers={'Content-Type':'text/event-stream'},
                    stream=BrowserByteStream(response['streamId']), request=request)
            return httpx.Response(response['status'], json=response['body'], request=request)
    class BrowserAgent(AIAgent):
        def _create_openai_client(self, client_kwargs, **kwargs):
            return OpenAI(api_key='browser-transport-placeholder', base_url='http://browser.invalid/v1',
                          http_client=httpx.Client(transport=BrowserTransport()), max_retries=0)
        def _interruptible_api_call(self, api_kwargs):
            kwargs = dict(api_kwargs)
            kwargs.pop('stream_options', None)
            kwargs['stream'] = False
            return self.client.chat.completions.create(**kwargs)
        def _interruptible_streaming_api_call(self, api_kwargs, *, on_first_delta=None):
            from agent.chat_completion_helpers import _StreamingCall, _reset_stale_streak
            import threading
            call = _StreamingCall(self, api_kwargs, on_first_delta)
            call._resolve_stale_timeout()
            call._call_done = threading.Event()
            call._monitor_interrupted = {'yes': False}
            # Reuse Hermes's actual SSE accumulator and callbacks, without OS monitor threads.
            call._run_call()
            if self._interrupt_requested:
                raise InterruptedError('browser stream interrupted')
            if call.result['error'] is not None:
                raise call.result['error']
            if call.result['response'] is not None:
                _reset_stale_streak(self)
            if isinstance(call.clients.diag, dict) and call.clients.diag.get('first_chunk_at'):
                self._last_api_first_chunk_at = float(call.clients.diag['first_chunk_at'])
            return call.result['response']
    import agent.tool_executor as tool_executor
    def browser_tool_activity(agent, name, fn):
        agent._touch_activity('browser tool started: ' + name)
        try:
            return fn()
        finally:
            agent._touch_activity('browser tool finished: ' + name)
    tool_executor._run_with_activity_heartbeat = browser_tool_activity
    from tools.registry import registry
    for definition in _kuro_inputs['tools']:
        schema = definition['function']
        name = schema['name']
        def handler(args, name=name, **kwargs):
            from tools.approval_context import _approval_tool_call_id
            context = {'tool_call_id': _approval_tool_call_id.get()}
            return json.dumps(bridge('tool', {'id': context.get('tool_call_id') or name,
                'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}))
        registry.register(name=name, toolset='kuro_browser', schema=schema, handler=handler)
    agent = BrowserAgent(model=_kuro_inputs['model'], provider='custom', api_mode='chat_completions',
        base_url='http://browser.invalid/v1', api_key='browser-placeholder',
        enabled_toolsets=['kuro_browser'], max_iterations=5, quiet_mode=True,
        skip_context_files=True, load_soul_identity=False, skip_memory=True,
        skip_background_review=True, save_trajectories=False, checkpoints_enabled=False,
        session_id=_kuro_inputs.get('sessionId'),
        stream_delta_callback=lambda text: _kuro_emit('delta', text),
        reasoning_callback=lambda text: _kuro_emit('reasoning', text))
    agent._disable_streaming = not _kuro_inputs.get('streaming', True)
    snapshot = _kuro_inputs.get('snapshot')
    if snapshot:
        agent._cached_system_prompt = snapshot['systemPrompt']
    result = agent.run_conversation(prompt, conversation_history=snapshot['messages'] if snapshot else None)
    result['browserSystemPrompt'] = agent._cached_system_prompt
    return result
