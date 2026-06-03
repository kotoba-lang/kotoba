import { run } from './out/bsp.js';
import { pregelRun } from './pregel-driver.js';
import { calls } from './host.js';

const r = pregelRun(run, { n: 3, acc: '' });
console.log('supersteps:', r.supersteps, '| trace:', r.trace.join(','));
console.log('final:', JSON.stringify(r.final));
console.log('host-log calls per superstep:', calls.length, '→', JSON.stringify(calls));

const ok = r.supersteps === 4
  && r.trace.join(',') === 'continue,continue,continue,ok'
  && r.final.status === 'ok' && r.final.acc === '...'
  && calls.length === 4;
console.log(ok ? '\nP3 BSP MULTI-SUPERSTEP DRIVER: PASS ✅ (guest looped 4 supersteps via the JS driver, host called each step)' : '\nFAIL ❌');
process.exit(ok ? 0 : 1);
