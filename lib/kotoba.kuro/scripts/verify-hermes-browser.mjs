// Compatibility probe: real local Hermes source inside Kuro's real browser Python tool.
// No credentials, installed environment, profiles, or runtime state are copied.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdir, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright';
import {serve} from './serve-browser-tools.mjs';

const source = process.argv[2];
if (!source) throw new Error('Usage: node scripts/verify-hermes-browser.mjs /path/to/hermes-agent');
const revision = execFileSync('git', ['-C', source, 'rev-parse', `${process.argv[3] || 'HEAD'}^{commit}`], {encoding: 'utf8'}).trim();
const paths = execFileSync('git', ['-C', source, 'ls-tree', '-r', '--name-only', revision], {encoding: 'utf8'})
  .trim().split('\n').filter(path => !/^(tests|evals|website|scripts|assets)\//.test(path) &&
    (path.endsWith('.py') || ['pyproject.toml', 'uv.lock', 'compat_manifest.json', 'LICENSE'].includes(path)));
assert(paths.includes('run_agent.py'));
const archive = execFileSync('git', ['-C', source, 'archive', '--format=tar.gz', revision, ...paths], {maxBuffer: 128 * 1024 * 1024});
const root = resolve('target/browser-tools');
await mkdir(root, {recursive: true});
await writeFile(`${root}/hermes-probe-source.tar.gz`, archive);
await writeFile(`${root}/hermes-probe-model.json`, JSON.stringify({id: 'local-transport-fixture',
  choices: [{message: {role: 'assistant', content: 'transport fixture only'}}]}));
const kuroRevision = execFileSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'}).trim();
const provenance = {revision, kuroRevision, files: paths.length, archiveSha256: createHash('sha256').update(archive).digest('hex')};
const {server, url} = await serve(root);
let browser;
const external = [];
try {
  browser = await chromium.launch({headless: true, ...(process.env.KURO_CHROMIUM_PATH ? {executablePath: process.env.KURO_CHROMIUM_PATH} : {})});
  const page = await browser.newPage();
  page.on('request', request => {if (!request.url().startsWith(url)) external.push(request.url());});
  await page.goto(url);
  await page.waitForFunction(() => window.browserTools);
  const runtime = await page.evaluate(async ({revision}) => {
    const {createToolHost} = await import('./client.js');
    const host = createToolHost({capabilities: ['tool/python', 'tool/python-js-bridge'], timeoutMs: 60000});
    const code = `
import sys, os, json, traceback, importlib, io, tarfile
from js import fetch
os.environ['HERMES_HOME'] = '/workspace/hermes-home'
os.makedirs('/workspace/hermes-home', exist_ok=True)
response = await fetch(inputs['sourceUrl'])
if not response.ok:
    raise RuntimeError('source snapshot could not be fetched')
buffer = await response.arrayBuffer()
from js import Uint8Array
archive_bytes = bytes(Uint8Array.new(buffer).to_py())
source_root = '/workspace/hermes-source'
os.makedirs(source_root, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
    archive.extractall(source_root, filter='data')
sys.path.insert(0, source_root)
os.chdir(source_root)
report = {'platform': sys.platform, 'python': sys.version, 'source_revision': inputs['revision'], 'checks': {}}
def check(name, fn):
    try:
        report['checks'][name] = {'ok': True, 'value': fn()}
    except BaseException as exc:
        report['checks'][name] = {'ok': False, 'exception': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc(limit=12)}
def budget():
    from agent.iteration_budget import IterationBudget
    counter = IterationBudget(2)
    values = [counter.consume(), counter.consume(), counter.consume()]
    counter.refund()
    return {'consume': values, 'remaining_after_refund': counter.remaining}
def thread():
    import threading
    seen = []
    t = threading.Thread(target=lambda: seen.append('ran'))
    t.start()
    t.join()
    return seen
def hermes_tool_pool():
    from tools.daemon_pool import DaemonThreadPoolExecutor
    pool = DaemonThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(lambda: {'tool_result': 42}).result(timeout=1)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
def process():
    import subprocess
    return subprocess.run(['echo', 'hermes-probe'], capture_output=True, text=True, check=True).stdout
def socket_probe():
    import socket
    sock = socket.socket()
    sock.close()
    return 'socket created'
def tls():
    import ssl
    return ssl.create_default_context().protocol
def tcp_http():
    import urllib.request
    with urllib.request.urlopen(inputs['modelFixtureUrl'], timeout=1) as response:
        return json.loads(response.read())['choices'][0]['message']['content']
def agent_import():
    from run_agent import AIAgent
    return {'class': AIAgent.__name__, 'module': AIAgent.__module__}
check('hermes_iteration_budget', budget)
check('thread_start', thread)
check('hermes_tool_executor_pool', hermes_tool_pool)
check('subprocess', process)
check('socket', socket_probe)
check('ssl_context', tls)
check('stdlib_http_to_model_fixture', tcp_http)
check('run_agent_import', agent_import)
for name in ['openai', 'pydantic', 'httpx', 'truststore', 'dotenv', 'rich', 'requests', 'jinja2', 'ruamel.yaml']:
    check('dependency:' + name, lambda name=name: {'module': importlib.import_module(name).__name__})
try:
    fixture_response = await fetch(inputs['modelFixtureUrl'])
    fixture = (await fixture_response.json()).to_py()
    report['checks']['browser_fetch_model_fixture'] = {'ok': True, 'value': fixture['choices'][0]['message']['content']}
except BaseException as exc:
    report['checks']['browser_fetch_model_fixture'] = {'ok': False, 'exception': type(exc).__name__, 'message': str(exc)}
report
`;
    return await host.call({id: 'hermes-browser-probe', type: 'function', function: {
      name: 'python', arguments: JSON.stringify({code, inputs: {sourceUrl: location.origin + '/hermes-probe-source.tar.gz',
        modelFixtureUrl: location.origin + '/hermes-probe-model.json', revision}})
    }});
  }, {revision});
  assert.equal(runtime.receipt['kuro/exit-code'], 0, JSON.stringify(runtime.receipt));
  assert.equal(runtime.result.source_revision, revision);
  assert.deepEqual(runtime.result.checks.hermes_iteration_budget.value, {consume: [true, true, false], remaining_after_refund: 1});
  assert.equal(runtime.result.checks.browser_fetch_model_fixture.ok, true);
  assert.deepEqual(external, [], 'compatibility test must not call external services');
  const agentImported = runtime.result.checks.run_agent_import.ok;
  const report = {provenance, runtime, externalRequests: external,
    verdict: {unmodifiedAgentImported: agentImported, conversationExecuted: false,
      liveModelUsed: false, browserLocalToolRoundTripExecuted: false,
      status: agentImported ? 'imported-conversation-unverified' : 'blocked-at-agent-import'}};
  await mkdir('docs/verification', {recursive: true});
  await writeFile('docs/verification/hermes-browser-probe.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
} finally {
  await browser?.close();
  await new Promise(resolveClose => server.close(resolveClose));
}
