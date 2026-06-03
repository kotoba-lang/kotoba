import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { KotobaNode } = require('../pkg/kotoba_wasm.js');
export const node = new KotobaNode();
