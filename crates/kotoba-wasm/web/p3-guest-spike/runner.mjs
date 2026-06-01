import { run } from './out/pregel.js';
const r = run('vertex-42');
console.log('guest run() returned:', JSON.stringify(r));
const ok = typeof r === 'string' && r.includes('pregel-superstep(input=vertex-42)') && r.includes('kotoba-host[vertex-42]');
console.log(ok ? '\nP3 jco SPIKE: PASS ✅ (Component Model guest ran on the JS WebAssembly engine + called back into the JS host)' : '\nP3 jco SPIKE: FAIL ❌');
process.exit(ok ? 0 : 1);
