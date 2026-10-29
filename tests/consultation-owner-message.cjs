'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const KEY='KULAGINA_OWNER_MESSAGE_PROBE_V1';
function fixture(options={}) {
 const values={TELEGRAM_BOT_TOKEN:'1:fake',OWNER_CHAT_ID:'101',...(options.props||{})};const logs=[];const calls=[];let held=false;let context;
 const lock={tryLock(){if(held||options.busy)return false;held=true;return true;},releaseLock(){held=false;}};
 const properties={getProperty(key){return values[key]||'';},setProperty(key,value){if(options.failClaim&&JSON.parse(value).phase==='sending')throw Error('private storage');if(options.failReceipt&&JSON.parse(value).phase!=='sending')throw Error('private receipt');values[key]=value;}};
 context=vm.createContext({Date,console:{log(value){logs.push(value);}},PropertiesService:{getScriptProperties(){return properties;}},LockService:{getScriptLock(){return lock;}},UrlFetchApp:{fetch(url,args){assert.equal(held,false,'network under ScriptLock');calls.push({url,args});if(options.peer)options.peer(context);if(options.timeout)throw Error('private token URL '+url);const body=options.body||{ok:true,result:{message_id:10,chat:{id:101,type:'private'},from:{id:1,is_bot:true}}};return {getResponseCode(){return options.code||200;},getContentText(){return options.raw===undefined?JSON.stringify(body):options.raw;}};}}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/tools/consultation_owner_message_probe.gs'),'utf8'),context);
 return {values,logs,calls,run(){return JSON.parse(JSON.stringify(context.testKulaginaOwnerMessageOnce()));}};
}
test('one owner message only, durable claim, safe report and no polling',()=>{
 const f=fixture(),r=f.run();assert.equal(r.status,'api_confirmed');assert.equal(r.api_accepted,true);assert.equal(r.delivered,null);assert.equal(f.calls.length,1);assert.equal(JSON.parse(f.values[KEY]).phase,'api_confirmed');
 const request=f.calls[0];assert.equal(request.url,'https://api.telegram.org/bot1:fake/sendMessage');assert.equal(request.args.followRedirects,false);assert.equal(request.args.validateHttpsCertificates,true);assert.equal(JSON.parse(request.args.payload).chat_id,101);assert.equal(JSON.parse(request.args.payload).parse_mode,undefined);
 for(const secret of ['1:fake','101','https://'])assert.equal(f.logs.join('').includes(secret),false);
});
test('repeat and restart do not send again',()=>{
 const f=fixture();f.run();assert.equal(f.run().status,'already_api_confirmed');assert.equal(f.calls.length,1);
 const next=fixture({props:{[KEY]:f.values[KEY]}});assert.equal(next.run().status,'already_api_confirmed');assert.equal(next.calls.length,0);
});
test('network timeout leaves unknown without blind retry or raw error',()=>{
 const f=fixture({timeout:true});assert.equal(f.run().status,'unknown');assert.equal(f.run().status,'inflight_or_unknown');assert.equal(f.calls.length,1);assert.equal(f.logs.join('').includes('private token'),false);assert.equal(f.logs.join('').includes('1:fake'),false);
});
test('receipt failure keeps pre-send claim and never retries',()=>{
 const f=fixture({failReceipt:true});assert.equal(f.run().status,'needs_recovery');assert.equal(JSON.parse(f.values[KEY]).phase,'sending');assert.equal(f.run().status,'inflight_or_unknown');assert.equal(f.calls.length,1);
});
test('claim failure and busy lock make no HTTP call',()=>{
 for(const options of [{failClaim:true},{busy:true}]){const f=fixture(options);f.run();assert.equal(f.calls.length,0);}
});
test('changed target or malformed claim require review, no overwrite',()=>{
 const f=fixture();f.run();const old=f.values[KEY];f.values.OWNER_CHAT_ID='102';assert.equal(f.run().status,'target_changed_requires_review');assert.equal(f.values[KEY],old);assert.equal(f.calls.length,1);
 const corrupt=fixture({props:{[KEY]:'not json'}});assert.equal(corrupt.run().status,'local_state_unavailable');assert.equal(corrupt.calls.length,0);
});
test('invalid token and group/invalid owner routing are blocked',()=>{
 for(const props of [{TELEGRAM_BOT_TOKEN:'1:fake/evil'},{OWNER_CHAT_ID:'-100'},{OWNER_CHAT_ID:'0'},{OWNER_CHAT_ID:'true'}]){const f=fixture({props});assert.equal(f.run().status,'invalid_configuration');assert.equal(f.calls.length,0);}
});
test('wrong bot/chat/message IDs and malformed ack are uncertain',()=>{
 for(const options of [{body:{ok:true,result:{message_id:10,chat:{id:102,type:'private'},from:{id:1,is_bot:true}}}},{body:{ok:true,result:{message_id:true,chat:{id:101,type:'private'},from:{id:1,is_bot:true}}}},{body:{ok:true,result:{message_id:10,chat:{id:101,type:'private'},from:{id:2,is_bot:true}}}},{raw:'not JSON'}]){const f=fixture(options);assert.equal(f.run().status,'unknown');assert.equal(f.calls.length,1);assert.equal(f.run().status,'inflight_or_unknown');}
});
test('API rejection is saved and not retried',()=>{
 const f=fixture({code:403,body:{ok:false,error_code:403}});assert.equal(f.run().status,'api_rejected');assert.equal(f.run().status,'already_api_rejected');assert.equal(f.calls.length,1);
});
test('active peer observes durable in-flight claim, cannot duplicate send',()=>{
 const nested=[];const f=fixture({peer(context){nested.push(context.testKulaginaOwnerMessageOnce());}});assert.equal(f.run().status,'api_confirmed');assert.equal(nested[0].status,'inflight_or_unknown');assert.equal(f.calls.length,1);
});
