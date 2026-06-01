import { run } from './out/bsp.js';
import { pregelRun } from './pregel-driver.js';
const r = pregelRun(run, { n: 3, acc: '' });
globalThis.__bspResult = r;
globalThis.__bspDone = true;
