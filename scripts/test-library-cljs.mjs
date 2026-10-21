import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const repo=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const workspace=path.resolve(process.argv[2]??'');
assert(process.argv.length===3&&workspace.includes('/github/workspaces/'),
  'usage: node scripts/test-library-cljs.mjs /absolute/github/workspaces/compiled-test');
fs.mkdirSync(workspace,{recursive:true});
const output=fs.mkdtempSync(path.join(workspace,'compiled-test-'));
const sources=path.join(output,'src'),build=path.join(output,'build');
fs.mkdirSync(sources);fs.mkdirSync(build);
fs.writeFileSync(path.join(build,'package.json'),'{"type":"commonjs"}\n');
const mappings=[];
function stage(source,destination){
  fs.mkdirSync(path.dirname(destination),{recursive:true});
  const bytes=fs.readFileSync(source);
  fs.writeFileSync(destination,bytes);
  mappings.push({source:path.relative(repo,source),destination:path.relative(output,destination),
    sha256:createHash('sha256').update(bytes).digest('hex')});
}
stage(path.join(repo,'lib/kotoba.test/src/kotoba/test/cljs.cljk'),
  path.join(sources,'kotoba/test/cljs.cljc'));
stage(path.join(repo,'test/fixtures/library-import/compiled-test.cljk'),
  path.join(sources,'kotoba/fixture/compiled_test.cljc'));
fs.writeFileSync(path.join(output,'source-mapping.json'),JSON.stringify(mappings,null,2)+'\n');
const env={...process.env};delete env.KOTOBA_TEST_PLANTED_FAILURE;
function run(command,args,label,expected=0){
  const result=spawnSync(command,args,{cwd:output,env,encoding:'utf8',timeout:240000,maxBuffer:8*1024*1024});
  fs.writeFileSync(path.join(output,label+'.log'),(result.stdout??'')+(result.stderr??''));
  assert.equal(result.status,expected,`${label}: ${result.error??result.stderr}`);
  return result;
}
const compiledProject=path.join(repo,'lib/kotoba.test/compiled');
const deps='{:deps {org.clojure/clojurescript {:mvn/version "1.11.132"} '+
  'kotoba.test/compiled {:local/root '+JSON.stringify(compiledProject)+'}}}';
fs.writeFileSync(path.join(output,'deps.edn'),deps+'\n');
const cp=run('clojure',['-Srepro','-Sdeps',deps,'-Spath'],'resolve').stdout.trim();
assert(!cp.includes('kotoba.text')&&!cp.includes('kotoba.spec'),
  'the compiled bridge must not introduce the property-testing runtime dependency graph');
const classpath=[sources,...cp.split(path.delimiter).map(p=>path.resolve(output,p))].join(path.delimiter);
run('java',['-Xmx1200m','-cp',classpath,'clojure.main','-m','cljs.main','--target','node',
  '--output-dir','build/out','--output-to','build/tests.cjs',
  '-c','kotoba.fixture.compiled-test'],'compile');
const command=path.join(build,'tests.cjs');
const positive=run(process.execPath,[command],'positive');
assert(positive.stdout.includes('compiled-bridge-summary [3 7 0 0]'));
env.KOTOBA_TEST_PLANTED_FAILURE='1';
const negative=run(process.execPath,[command],'planted-failure',1);
assert(negative.stdout.includes('compiled-bridge-summary [3 5 1 1]'));
console.log('Compiled CLJS bridge: 3 tests / 7 assertions PASS; planted async failure + exception counted and exit 1; shared report/fixtures verified');
console.log('Evidence: '+output);
