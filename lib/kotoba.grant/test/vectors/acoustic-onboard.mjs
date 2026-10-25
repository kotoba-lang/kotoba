#!/usr/bin/env node
// Golden vectors for grant.acoustic-onboard (ADR-0243). Test-only: fixed private keys, never real ones.
//   node test/vectors/acoustic-onboard.mjs print    emit the EDN vectors
//   node test/vectors/acoustic-onboard.mjs verify   recompute every vector with node:crypto and compare
//   node test/vectors/acoustic-onboard.mjs webcrypto  open the vector's message with WebCrypto (the browser path)
import crypto from 'node:crypto';
const hex=b=>Buffer.from(b).toString('hex'), u=s=>Buffer.from(s,'hex'), b64u=b=>Buffer.from(b).toString('base64url');
const PKCS8=Buffer.from('302e020100300506032b656e04220420','hex'), SPKI=Buffer.from('302a300506032b656e032100','hex');
const priv=seed=>crypto.createPrivateKey({key:Buffer.concat([PKCS8,u(seed)]),format:'der',type:'pkcs8'});
const rawPub=k=>crypto.createPublicKey(k).export({format:'der',type:'spki'}).subarray(-32);
const pubOf=raw=>crypto.createPublicKey({key:Buffer.concat([SPKI,raw]),format:'der',type:'spki'});

export const INPUT={
  deviceSeed:'00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff',
  ephemeralSeed:'ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100',
  code:'K7QX3M', fp:'2c3b85f8', labelSecret:'AAECAwQFBgcICQoLDA0ODw',   // 16 bytes 00..0f
  profile:{ssid:'Home-WiFi-5G',security:1,passphrase:'correct horse battery'}
};
export function compute(i=INPUT){
  const dev=priv(i.deviceSeed), eph=priv(i.ephemeralSeed), devPub=rawPub(dev), ephPub=rawPub(eph);
  const shared=crypto.diffieHellman({privateKey:eph,publicKey:pubOf(devPub)});
  const aad=Buffer.from(`aiueos-wifi-profile-v1-acoustic\n${i.code}\n${i.fp}`), salt=Buffer.from(i.labelSecret);
  const okm=Buffer.from(crypto.hkdfSync('sha256',shared,salt,aad,44)), key=okm.subarray(0,32), iv=okm.subarray(32);
  const pt=Buffer.concat([Buffer.from([i.profile.security]),Buffer.from(i.profile.ssid),Buffer.from([0]),Buffer.from(i.profile.passphrase)]);
  const c=crypto.createCipheriv('aes-256-gcm',key,iv); c.setAAD(aad);
  const ct=Buffer.concat([c.update(pt),c.final(),c.getAuthTag()]);
  const message=Buffer.concat([Buffer.from([0x57]),ephPub,ct]);
  return {...i, devicePublicKey:hex(devPub), ephemeralPublicKey:hex(ephPub), sharedSecret:hex(shared), aad:aad.toString(), salt:salt.toString(),
    okm:hex(okm), plaintext:hex(pt), ciphertextAndTag:hex(ct), message:hex(message),
    beacon:`mk1|${i.code}|${i.fp}|${b64u(devPub)}`, ack:`ack|${i.code}`};
}
const edn=v=>`{:code "${v.code}" :fp "${v.fp}" :label-secret "${v.labelSecret}"\n :profile {:ssid "${v.profile.ssid}" :security :wpa2-personal :passphrase "${v.profile.passphrase}"}\n :device-public-key "${v.devicePublicKey}" :ephemeral-public-key "${v.ephemeralPublicKey}"\n :shared-secret "${v.sharedSecret}"\n :aad ${JSON.stringify(v.aad)} :salt "${v.salt}"\n :okm "${v.okm}"\n :plaintext "${v.plaintext}"\n :ciphertext-and-tag "${v.ciphertextAndTag}"\n :message "${v.message}"\n :beacon "${v.beacon}" :ack "${v.ack}"}`;
const mode=process.argv[2];
if(process.argv[1]===new URL(import.meta.url).pathname){
  const v=compute();
  if(mode==='print') console.log(`;; Golden vectors for grant.acoustic-onboard (ADR-0243). TEST KEYS ONLY. Regenerate with:\n;;   node test/vectors/acoustic-onboard.mjs print\n[${edn(v)}]`);
  if(mode==='verify'){ // independent recomputation: decrypt with the DEVICE's private key, as the box would
    const dev=priv(v.deviceSeed), m=u(v.message), peer=pubOf(m.subarray(1,33)), shared=crypto.diffieHellman({privateKey:dev,publicKey:peer});
    const okm=Buffer.from(crypto.hkdfSync('sha256',shared,Buffer.from(v.salt),Buffer.from(v.aad),44));
    const ct=m.subarray(33), d=crypto.createDecipheriv('aes-256-gcm',okm.subarray(0,32),okm.subarray(32)); d.setAAD(Buffer.from(v.aad)); d.setAuthTag(ct.subarray(-16));
    const pt=Buffer.concat([d.update(ct.subarray(0,-16)),d.final()]);
    const ok=hex(pt)===v.plaintext&&hex(okm)===v.okm&&hex(shared)===v.sharedSecret&&m.length===84;
    let wrong=true; try{ const o=Buffer.from(crypto.hkdfSync('sha256',shared,Buffer.from('AAAAAAAAAAAAAAAAAAAAAA'),Buffer.from(v.aad),44)); const d2=crypto.createDecipheriv('aes-256-gcm',o.subarray(0,32),o.subarray(32)); d2.setAAD(Buffer.from(v.aad)); d2.setAuthTag(ct.subarray(-16)); d2.update(ct.subarray(0,-16)); d2.final(); wrong=false; }catch{}
    console.log(ok&&wrong?'vectors OK (84-byte message opens with the device key; a wrong label secret is refused)':'vectors FAILED'); process.exit(ok&&wrong?0:1);
  }
  if(mode==='webcrypto'){ // the browser path: WebCrypto X25519 + HKDF + AES-GCM
    const s=crypto.webcrypto.subtle, m=u(v.message);
    const devKey=await s.importKey('pkcs8',Buffer.concat([PKCS8,u(v.deviceSeed)]),{name:'X25519'},false,['deriveBits']);
    const peer=await s.importKey('raw',m.subarray(1,33),{name:'X25519'},false,[]);
    const shared=await s.deriveBits({name:'X25519',public:peer},devKey,256);
    const hk=await s.importKey('raw',shared,'HKDF',false,['deriveBits']);
    const okm=new Uint8Array(await s.deriveBits({name:'HKDF',hash:'SHA-256',salt:Buffer.from(v.salt),info:Buffer.from(v.aad)},hk,352));
    const key=await s.importKey('raw',okm.slice(0,32),'AES-GCM',false,['decrypt']);
    const pt=Buffer.from(await s.decrypt({name:'AES-GCM',iv:okm.slice(32),additionalData:Buffer.from(v.aad),tagLength:128},key,m.subarray(33)));
    const ok=hex(pt)===v.plaintext; console.log(ok?'webcrypto OK':'webcrypto FAILED'); process.exit(ok?0:1);
  }
}
