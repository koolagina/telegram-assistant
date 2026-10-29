'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function fixture(options={}) {
 const calls=[];
 const values={TELEGRAM_BOT_TOKEN:'1:fake',OWNER_CHAT_ID:'101',ASSISTANT_CALENDAR_ID:'synthetic-calendar',...(options.props||{})};
 const context=vm.createContext({Date,console:{log(value){calls.push({kind:'console',value});}},PropertiesService:{getScriptProperties(){return {getProperty(key){calls.push({kind:'property',key});return values[key]||'';}};}},
  UrlFetchApp:{fetch(url,args){calls.push({kind:'http',method:args.method,url,args});if(options.networkError)throw Error('private URL '+url);return {getResponseCode(){return options.code||200;},getContentText(){return options.raw===undefined?JSON.stringify(options.body||{ok:true,result:{id:1,is_bot:true,username:'synthetic_bot'}}):options.raw;}};}},
  CalendarApp:{getCalendarById(id){calls.push({kind:'calendar',id});if(options.calendarError)throw Error('private calendar details');if(options.missingCalendar)return null;return {getId(){return options.wrongCalendar?'foreign':id;},getTimeZone(){return options.zone||'Asia/Yekaterinburg';}};}}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/tools/consultation_connection_probe.gs'),'utf8'),context);
 return {run(){return JSON.parse(JSON.stringify(context.probeKulaginaConnectionsReadOnly()));},show(){context.showKulaginaConnectionProbe();return calls.find(c=>c.kind==='console').value;},calls};
}
test('probe checks metadata only and returns no secret or personal IDs',()=>{
 const f=fixture(),report=f.run();assert.equal(report.mode,'read_only_metadata');assert.equal(report.telegram.verified,true);assert.equal(report.calendar.read_access_verified,true);assert.equal(report.owner_target.configured,true);assert.equal(report.ready_for_private_preview,true);
 const encoded=JSON.stringify(report);for(const value of ['1:fake','101','synthetic-calendar','synthetic_bot'])assert.equal(encoded.includes(value),false);
 assert.deepEqual(f.calls.map(c=>c.kind),['property','property','property','http','calendar']);assert.equal(report.writes_performed,0);assert.equal(report.messages_sent,0);
});
test('only fixed getMe endpoint is called with verified TLS and redirects disabled',()=>{
 const f=fixture();f.run();const call=f.calls.find(c=>c.kind==='http');assert.equal(call.url,'https://api.telegram.org/bot1:fake/getMe');assert.equal(call.method,'post');assert.equal(call.args.followRedirects,false);assert.equal(call.args.validateHttpsCertificates,true);assert.equal(call.args.muteHttpExceptions,true);
 assert.equal(f.calls.filter(c=>c.kind==='http').length,1);assert.equal(reportHasWrites(f.calls),false);
});
function reportHasWrites(calls){return calls.some(c=>c.kind==='http'&&/sendMessage|getUpdates|Webhook|delete|set/i.test(c.url));}
test('missing settings do not discover resources or make requests',()=>{
 const f=fixture({props:{TELEGRAM_BOT_TOKEN:'',OWNER_CHAT_ID:'',ASSISTANT_CALENDAR_ID:''}}),r=f.run();assert.equal(r.ready_for_private_preview,false);assert.equal(r.telegram.status,'not_configured');assert.equal(r.calendar.status,'not_configured');assert.equal(f.calls.filter(c=>c.kind!=='property').length,0);
});
test('invalid token or primary calendar fail closed without guessing',()=>{
 const f=fixture({props:{TELEGRAM_BOT_TOKEN:'1:fake/other',ASSISTANT_CALENDAR_ID:'primary'}}),r=f.run();assert.equal(r.telegram.status,'invalid_configuration');assert.equal(r.calendar.status,'invalid_target');assert.equal(f.calls.filter(c=>c.kind!=='property').length,0);
});
test('API rejection and token-bearing exceptions never expose response or URL',()=>{
 for(const options of [{code:401,raw:'private response 1:fake'}, {networkError:true}]){
  const report=fixture(options).run();assert.equal(report.telegram.verified,false);assert.equal(report.ready_for_private_preview,false);assert.equal(JSON.stringify(report).includes('1:fake'),false);
  assert.equal(JSON.stringify(report).includes('private response'),false);assert.equal(JSON.stringify(report).includes('https://'),false);
 }
});
test('wrong bot identity, bool ID, non-bot and malformed/oversize responses rejected',()=>{
 for(const options of [{body:{ok:true,result:{id:2,is_bot:true}}},{body:{ok:true,result:{id:true,is_bot:true}}},{body:{ok:true,result:{id:1,is_bot:false}}},{raw:'not json'},{raw:'x'.repeat(65537)}]){
  const report=fixture(options).run();assert.equal(report.telegram.verified,false);assert.equal(report.ready_for_private_preview,false);
 }
});
test('unavailable or wrong calendar is not reported accessible',()=>{
 for(const options of [{calendarError:true},{missingCalendar:true},{wrongCalendar:true}]){const report=fixture(options).run();assert.equal(report.ready_for_private_preview,false);assert.equal(report.calendar.read_access_verified,false);assert.equal(JSON.stringify(report).includes('private calendar details'),false);}
 const mismatch=fixture({zone:'UTC'}).run();assert.equal(mismatch.calendar.read_access_verified,true);assert.equal(mismatch.calendar.timezone_matches,false);assert.equal(mismatch.calendar.status,'accessible_timezone_review');assert.equal(mismatch.ready_for_private_preview,true);
});
test('owner target is routing configuration only, not proof of identity or delivery',()=>{
 const r=fixture().run();assert.equal(r.owner_target.identity_verified,false);assert.equal(r.messages_sent,0);assert.equal(r.polling_started,false);
 for(const id of ['-100','true','0','1.5'])assert.equal(fixture({props:{OWNER_CHAT_ID:id}}).run().ready_for_private_preview,false);
});
test('helper does not depend on initialize, triggers, sheets, cache or bot globals',()=>{
 const f=fixture();assert.equal(f.run().ready_for_private_preview,true);assert.equal(f.run().ready_for_private_preview,true);assert.equal(f.calls.filter(c=>c.kind==='http').length,2);assert.equal(reportHasWrites(f.calls),false);
});

test('manual runner logs only sanitized JSON even on token-bearing exception',()=>{
 const encoded=fixture({networkError:true,calendarError:true}).show();const report=JSON.parse(encoded);assert.equal(report.ready_for_private_preview,false);assert.equal(encoded.includes('1:fake'),false);assert.equal(encoded.includes('synthetic-calendar'),false);assert.equal(encoded.includes('private URL'),false);assert.equal(encoded.includes('private calendar details'),false);
});
