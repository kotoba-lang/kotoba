import {serve} from './serve-browser-tools.mjs';
import {createHuggingFaceRelay} from './huggingface-relay.mjs';
const [source,endpoint=process.env.HF_ENDPOINT_URL,model=process.env.HF_MODEL]=process.argv.slice(2);
if(!source||!endpoint||!model)throw Error('Usage: serve-hermes-hf.mjs /path/to/native/hermes https://<id>.endpoints.huggingface.cloud served-model');
const relay=createHuggingFaceRelay({source,endpoint,model});
const {server,url}=await serve(undefined,8123,{handleRequest:relay.handleRequest});
console.log(url+'/hermes.html');
for(const event of ['SIGINT','SIGTERM'])process.once(event,()=>{relay.close();server.closeAllConnections();server.close();});
