#!/usr/bin/env node
// Local files only: exercise the exact argv transport without B2 credentials.
import fs from 'node:fs';
import path from 'node:path';
const [op, ...args] = process.argv.slice(2);
const remote = s => s.startsWith('fake:')
  ? path.join(process.env.B2_TEST_REMOTE, s.slice(5)) : s;
const write = (p, bytes) => {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, bytes);
};
try {
  switch (op) {
    case 'lsjson': {
      const p = remote(args[0]);
      process.stdout.write(JSON.stringify(fs.existsSync(p)
        ? fs.readdirSync(p, { withFileTypes: true }).filter(e => e.isFile()).map(e => ({ Name: e.name })) : []));
      break;
    }
    case 'cat': process.stdout.write(fs.readFileSync(remote(args[0]))); break;
    case 'rcat': {
      const p = remote(args[0]);
      if (process.env.B2_TEST_REJECT_PUBLICATION === '1' && p.includes('/events/')) process.exit(42);
      write(p, fs.readFileSync(0));
      break;
    }
    case 'copy': {
      const src = remote(args[0]), dst = remote(args[1]), at = args.indexOf('--files-from');
      const names = at >= 0 ? fs.readFileSync(args[at + 1], 'utf8').trim().split('\n') : fs.readdirSync(src);
      for (const name of names.filter(Boolean)) {
        const bytes = fs.readFileSync(path.join(src, name)), p = path.join(dst, name);
        if (args.includes('--immutable') && fs.existsSync(p) && !fs.readFileSync(p).equals(bytes)) process.exit(43);
        write(p, bytes);
      }
      break;
    }
    default: throw new Error(`Unsupported stub operation: ${op}`);
  }
} catch (e) { process.stderr.write(`${e.message}\n`); process.exit(1); }
