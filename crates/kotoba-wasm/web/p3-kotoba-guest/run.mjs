import { encode, decode } from 'cbor-x';
import { run } from './out/kguest.js';
import { node } from './hosts/node.js';

const ctx = { graph: 'yoro-social-v1', session_cid: null, args_cbor: new TextEncoder().encode('superstep-args') };
const outCbor = run(encode(ctx));
const out = decode(outCbor);
console.log('real kotoba-guest run() →', JSON.stringify(out));

const dump = JSON.parse(node.exportDatoms());
const task = dump.find(d => d.a === 'kotoba/task');
console.log('KotobaNode got quad via guest kqe.assert-quad →', task ? JSON.stringify(task) : 'NONE');

const ok = out && out.status === 'ok' && out.quads_asserted === 1
  && out.agent_did === 'did:web:etzhayyim.com:actor:tsumugi'
  && out.topic_cid && out.topic_cid.startsWith('bafy-kse-')
  && task && task.a === 'kotoba/task' && task.v_edn.includes('superstep-args');
console.log(ok ? '\nP3 REAL-GUEST VERIFY: PASS ✅ (production kotoba-guest ran via jco; auth+kqe+kse host wired; kqe.assert-quad landed in KotobaNode)' : '\nP3 REAL-GUEST: FAIL ❌');
process.exit(ok ? 0 : 1);
