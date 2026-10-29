'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const KEY='KULAGINA_CALENDAR_TEST_V1';
function fixture(options={}) {
 const values={ASSISTANT_CALENDAR_ID:'synthetic-calendar',...(options.props||{})},events=new Map(),calls=[],logs=[];let held=false;
 class Clock extends Date {constructor(...args){super(...(args.length?args:[options.now||'2026-10-29T08:25:00Z']));}}
 const properties={getProperty(key){return values[key]||'';},setProperty(key,value){const phase=JSON.parse(value).phase;if(options.failPhase===phase)throw Error('private state failure');values[key]=value;}};
 const lock={tryLock(){if(held||options.busyLock)return false;held=true;return true;},releaseLock(){held=false;}};
 const ctx=vm.createContext({Date:Clock,console:{log(text){logs.push(text);}},PropertiesService:{getScriptProperties(){return properties;}},LockService:{getScriptLock(){return lock;}},Utilities:{getUuid(){return '12345678-1234-1234-1234-123456789abc';}},ScriptApp:{getOAuthToken(){return 'fake-oauth';}},CalendarApp:{getCalendarById(id){return {getId(){return id;},getTimeZone(){return 'Asia/Yekaterinburg';}};}},UrlFetchApp:{fetch(url,args){
  assert.equal(held,false,'network under working ScriptLock');calls.push({url,args});const path=new URL(url).pathname;let code=200,body;
  if(path.includes('/users/me/calendarList/'))body={id:'synthetic-calendar',accessRole:options.reader?'reader':'owner'};
  else if(path.endsWith('/calendars/synthetic-calendar'))body={id:'synthetic-calendar',timeZone:'Asia/Yekaterinburg'};
  else if(path.endsWith('/events')&&args.method==='get')body={kind:'calendar#events',items:options.busy?[{summary:'PRIVATE EVENT'}]:[]};
  else if(path.endsWith('/events')&&args.method==='post'){
   body=JSON.parse(args.payload);body.etag='"v1"';body.kind='calendar#event';events.set(body.id,structuredClone(body));code=201;
   if(options.timeoutCreate)throw Error('private OAuth '+url);
  } else {
   const id=decodeURIComponent(path.split('/').pop());body=events.get(id);
   if(options.manualBeforeDelete&&args.method==='get'&&body?.etag==='"v2"') {body.description+=' manual note';body.etag='"manual"';}
   if(!body){code=404;body={error:{message:'private event id'}};}
   else if(args.method==='patch') {
    if(options.rejectPatch||args.headers['If-Match']!==body.etag){code=412;body={error:{}};}
    else {Object.assign(body,JSON.parse(args.payload));body.etag='"v2"';events.set(id,structuredClone(body));if(options.timeoutPatch)throw Error('private accepted patch');}
   } else if(args.method==='delete') {
    if(args.headers['If-Match']!==body.etag){code=412;body={error:{}};}
    else {events.delete(id);code=204;body={};if(options.timeoutDelete)throw Error('private accepted delete');}
   }
  }
  return {getResponseCode(){return code;},getContentText(){return JSON.stringify(body);}};
 }}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/tools/consultation_calendar_smoke.gs'),'utf8'),ctx);
 return {values,events,calls,logs,run(){return JSON.parse(JSON.stringify(ctx.testKulaginaCalendarOnce()));},inspect(){return JSON.parse(JSON.stringify(ctx.inspectKulaginaCalendarTest()));}};
}
test('one owned TEST event created updated and deleted with conditional requests',()=>{
 const f=fixture(),r=f.run();assert.equal(r.status,'complete');assert.equal(r.create_verified,true);assert.equal(r.update_verified,true);assert.equal(r.cleanup_confirmed,true);assert.equal(r.write_requests_this_run,3);assert.equal(f.events.size,0);
 assert.deepEqual(f.calls.filter(c=>c.args.method!=='get').map(c=>c.args.method),['post','patch','delete']);
 for(const c of f.calls.filter(c=>['patch','delete'].includes(c.args.method)))assert.ok(c.args.headers['If-Match']);
 for(const c of f.calls){assert.equal(c.args.followRedirects,false);assert.equal(c.args.validateHttpsCertificates,true);}
 assert.equal(f.logs.join('').includes('fake-oauth'),false);assert.equal(f.logs.join('').includes('synthetic-calendar'),false);
});
test('repeat and restart cannot recreate or repeat mutations',()=>{
 const f=fixture();f.run();const count=f.calls.length;assert.equal(f.run().status,'already_complete');assert.equal(f.calls.length,count);
 const peer=fixture({props:{[KEY]:f.values[KEY]}});assert.equal(peer.run().status,'already_complete');assert.equal(peer.calls.length,0);
});
test('new busy event or non-owner target is blocked before any write',()=>{
 for(const options of [{busy:true},{reader:true}]){const f=fixture(options);assert.notEqual(f.run().status,'complete');assert.equal(f.calls.filter(c=>c.args.method!=='get').length,0);assert.equal(f.values[KEY],undefined);}
});
test('expired exact preview window is not moved to another date',()=>{
 const f=fixture({now:'2026-10-30T04:31:00Z'});assert.equal(f.run().status,'test_window_expired');assert.equal(f.calls.filter(c=>c.args.method!=='get').length,0);
});
test('creation timeout never posts again and can be inspected read-only',()=>{
 const f=fixture({timeoutCreate:true});assert.equal(f.run().status,'needs_review');assert.equal(f.events.size,1);f.run();assert.equal(f.calls.filter(c=>c.args.method==='post').length,1);
 const count=f.calls.filter(c=>c.args.method!=='get').length;const inspected=f.inspect();assert.equal(inspected.owned_test_event_found,true);assert.equal(inspected.cleanup_required,true);assert.equal(f.calls.filter(c=>c.args.method!=='get').length,count);
});
test('patch timeout is not retried and own event remains for review',()=>{
 const f=fixture({timeoutPatch:true});assert.equal(f.run().status,'needs_review');assert.equal(f.events.size,1);f.run();assert.equal(f.calls.filter(c=>c.args.method==='patch').length,1);assert.equal(f.calls.filter(c=>c.args.method==='delete').length,0);
});
test('delete timeout can confirm absence without repeating DELETE',()=>{
 const f=fixture({timeoutDelete:true});assert.equal(f.run().status,'needs_review');assert.equal(f.events.size,0);const r=f.inspect();assert.equal(r.cleanup_confirmed,true);assert.equal(r.cleanup_required,false);f.run();assert.equal(f.calls.filter(c=>c.args.method==='delete').length,1);
});
test('manual edits or 412 protect test event rather than forcing cleanup',()=>{
 for(const options of [{manualBeforeDelete:true},{rejectPatch:true}]){const f=fixture(options);assert.equal(f.run().status,'needs_review');assert.equal(f.calls.filter(c=>c.args.method==='delete').length,0);assert.equal(f.events.size,1);if(options.manualBeforeDelete){const r=f.inspect();assert.equal(r.owned_test_event_found,false);assert.equal(r.cleanup_required,null);}}
});
test('failure persisting create result leaves durable claim and blocks retry',()=>{
 const f=fixture({failPhase:'created'});assert.equal(f.run().status,'needs_review');assert.equal(JSON.parse(f.values[KEY]).phase,'creating');assert.equal(f.events.size,1);f.run();assert.equal(f.calls.filter(c=>c.args.method==='post').length,1);
});
test('different target and corrupt state do not redirect or overwrite claims',()=>{
 const f=fixture();f.run();f.values.ASSISTANT_CALENDAR_ID='other';const count=f.calls.length;assert.equal(f.run().status,'target_changed_requires_review');assert.equal(f.calls.length,count);
 const corrupt=fixture({props:{[KEY]:'not JSON'}});assert.equal(corrupt.run().status,'local_state_unavailable');assert.equal(corrupt.calls.length,0);
});
test('busy working lock makes no write; no Telegram or Sheet APIs exist in harness',()=>{
 const f=fixture({busyLock:true});f.run();assert.equal(f.calls.filter(c=>c.args.method!=='get').length,0);assert.equal(f.values[KEY],undefined);
});
