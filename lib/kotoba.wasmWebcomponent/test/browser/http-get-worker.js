import { actorHostImports, hostCaps } from '../../src/actor-host.js';
import { createSabHttpGetClient, createSabHttpPostClient } from '../../src/http-sab-bridge.js';

try {
  const memoryBox = {};
  const caps = hostCaps({
    grants: ['http-get'],
    limits: {
      maxHttpGets: 1,
      allowWriteImports: true,
      httpUrlAllowlist: ['https://example.test:443/bounded'],
    },
  });
  const imports = actorHostImports(['http-get'], caps, memoryBox, {
    httpGet: createSabHttpGetClient(),
  });
  const response = await fetch('./http-get-sab.wasm');
  const { instance } = await WebAssembly.instantiate(await response.arrayBuffer(), { kotoba: imports });
  memoryBox.memory = instance.exports.memory;
  const length = instance.exports.main();
  const text = new TextDecoder().decode(new Uint8Array(memoryBox.memory.buffer, 64, length));

  const postMemoryBox = {};
  const postCaps = hostCaps({
    grants: ['http-post'],
    limits: {
      maxHttpPosts: 1,
      httpUrlAllowlist: ['https://api.example.test/v1'],
    },
  });
  const postImports = actorHostImports(['http-post'], postCaps, postMemoryBox, {
    httpPost: createSabHttpPostClient(),
  });
  const postResponse = await fetch('./http-post-sab.wasm');
  const { instance: postInstance } = await WebAssembly.instantiate(
    await postResponse.arrayBuffer(), { kotoba: postImports });
  postMemoryBox.memory = postInstance.exports.memory;
  const postLength = postInstance.exports.main();
  const postText = new TextDecoder().decode(
    new Uint8Array(postMemoryBox.memory.buffer, 128, postLength));
  postMessage({ type: 'result', ok: true, length, text, postLength, postText });
} catch (error) {
  postMessage({ type: 'result', ok: false, error: String(error?.stack || error) });
}
