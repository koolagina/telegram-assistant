'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
function fixture(options={}) {
 const calls=[],logs=[];const instant=options.now||'2026-10-29T07:58:00Z';let clockMs=new Date(instant).getTime();
 class Clock extends Date {constructor(...args){super(...(args.length?args:[clockMs]));}static now(){return clockMs;}}
 const context=vm.createContext({Date:Clock,console:{log(value){logs.push(value);}},PropertiesService:{getScriptProperties(){return {getProperty(key){assert.equal(key,'ASSISTANT_CALENDAR_ID');return options.target===undefined?'synthetic-calendar':options.target;}};}},
 CalendarApp:{getCalendarById(id){return {getId(){return id;},getTimeZone(){return 'Asia/Yekaterinburg';}};}},ScriptApp:{getOAuthToken(){return 'fake-oauth';}},
 Utilities:{formatDate(date,zone,pattern){const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}).formatToParts(date).map(x=>[x.type,x.value]));return pattern==='yyyy-MM-dd'?parts.year+'-'+parts.month+'-'+parts.day:String({Mon:1,Tue:2,Wed:3,Thu:4,Fri:5,Sat:6,Sun:7}[parts.weekday]);}},
 UrlFetchApp:{fetch(url,args){calls.push({url,args});assert.equal(args.method,'get');if(options.slowOnce&&url.includes('/events?')&&calls.filter(c=>c.url.includes('/events?')).length===1)clockMs+=31*60000;let body;if(options.code&&options.code!==200)body={error:{errors:[{reason:'accessNotConfigured'}],message:'PRIVATE fake-oauth URL '+url}};
 else if(!url.includes('/events?'))body={kind:'calendar#calendar',id:'synthetic-calendar',timeZone:'Asia/Yekaterinburg'};
 else if(options.unreadPage)body={kind:'calendar#events',items:[],nextPageToken:'unread'};
 else body=options.malformed?{kind:'calendar#events',items:'broken'}:{kind:'calendar#events',items:options.busy?[{summary:'PRIVATE STUDENT'}]:[]};
 return {getResponseCode(){return options.code||200;},getContentText(){return JSON.stringify(body);}};}}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/tools/consultation_calendar_preview.gs'),'utf8'),context);
 return {calls,logs,run(){return JSON.parse(JSON.stringify(context.previewKulaginaCalendarTest()));}};
}
test('read-only preview finds one future test slot with no mutation or secret output',()=>{
 const f=fixture(),r=f.run();assert.equal(r.status,'preview_ready');assert.equal(r.test_slot.start,'2026-10-30T10:00:00+05:00');assert.equal(r.test_slot.end,'2026-10-30T10:20:00+05:00');assert.equal(r.calendar_writes,0);assert.equal(r.messages_sent,0);assert.equal(r.teaching_schedule_verified,false);assert.equal(f.calls.length,2);
 for(const text of ['fake-oauth','synthetic-calendar','PRIVATE','https://'])assert.equal(f.logs.join('').includes(text),false);
});
test('weekends and thirty-minute lead are checked in Yekaterinburg',()=>{
 assert.equal(fixture({now:'2026-10-30T12:00:00Z'}).run().test_slot.start,'2026-11-02T10:00:00+05:00');
 assert.equal(fixture({now:'2026-10-29T04:30:00Z'}).run().test_slot.start,'2026-10-29T10:00:00+05:00');
 assert.equal(fixture({now:'2026-10-29T04:30:01Z'}).run().test_slot.start,'2026-10-29T10:40:00+05:00');
});
test('busy calendar yields no proposed slot and bounded GET requests only',()=>{
 const f=fixture({busy:true}),r=f.run();assert.equal(r.status,'no_test_slot_found');assert.equal(r.test_slot,null);assert.ok(f.calls.length<=13);assert.ok(f.calls.every(c=>c.args.method==='get'));assert.equal(f.logs.join('').includes('PRIVATE STUDENT'),false);
});
test('API disabled or rejected does not become empty/free or leak response',()=>{
 const f=fixture({code:403}),r=f.run();assert.equal(r.status,'calendar_api_unavailable');assert.equal(r.api_error_code,403);assert.equal(r.api_error_reason,'accessNotConfigured');assert.equal(r.test_slot,null);assert.equal(f.logs.join('').includes('fake-oauth'),false);assert.equal(f.calls.length,1);
});
test('malformed events cannot be interpreted as absent appointments',()=>{
 const f=fixture({malformed:true}),r=f.run();assert.equal(r.status,'unverified_response');assert.equal(r.test_slot,null);
});
test('missing/primary/invalid target makes no network request or fallback',()=>{
 for(const target of ['', 'primary','unsafe calendar']){const f=fixture({target}),r=f.run();assert.notEqual(r.status,'preview_ready');assert.equal(f.calls.length,0);}
});
test('all API traffic is fixed-origin GET with TLS/redirect guards',()=>{
 const f=fixture();f.run();for(const call of f.calls){assert.ok(call.url.startsWith('https://www.googleapis.com/calendar/v3/calendars/'));assert.equal(call.args.followRedirects,false);assert.equal(call.args.validateHttpsCertificates,true);assert.equal(call.args.headers.Authorization,'Bearer fake-oauth');}
});
test('preview does not offer a consultation or prove write access/full timetable',()=>{
 const r=fixture().run();assert.equal(r.purpose,'temporary_TEST_only');assert.equal(r.write_access_verified,false);assert.equal(r.teaching_schedule_verified,false);assert.equal(r.only_selected_calendar_checked,true);
});

test('slow availability read does not return a slot inside the thirty-minute lead',()=>{
 const r=fixture({now:'2026-10-29T04:00:00Z',slowOnce:true}).run();assert.equal(r.test_slot.start,'2026-10-29T10:40:00+05:00');
});
test('unread events page is not treated as verified empty',()=>{
 const r=fixture({unreadPage:true}).run();assert.equal(r.status,'no_test_slot_found');assert.equal(r.test_slot,null);
});
