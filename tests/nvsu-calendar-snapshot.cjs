'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
function event(extra={}){return {id:'private-event',status:'confirmed',summary:'PRIVATE PERSONAL TITLE',location:'PRIVATE ROOM',start:{dateTime:'2026-11-02T10:00:00+05:00'},end:{dateTime:'2026-11-02T11:00:00+05:00'},...extra};}
function fixture(o={}){
 const calls=[],logs=[];let page=0;
 const c=vm.createContext({console:{log:s=>logs.push(s)},PropertiesService:{getScriptProperties:()=>({getProperty:()=>o.target===undefined?'private-calendar':o.target})},CalendarApp:{getCalendarById:id=>({getId:()=>id,getTimeZone:()=>o.zone||'Asia/Yekaterinburg'})},ScriptApp:{getOAuthToken:()=> 'private-token'},Utilities:{DigestAlgorithm:{SHA_256:'sha'},Charset:{UTF_8:'utf8'},computeDigest:(_a,s)=>Array.from(crypto.createHash('sha256').update(s).digest()).map(x=>x>127?x-256:x)},UrlFetchApp:{fetch:(url,args)=>{
 calls.push({url,args});assert.equal(args.method,'get');let b;
 if(!url.includes('/events?'))b={kind:'calendar#calendar',id:'private-calendar',timeZone:'Asia/Yekaterinburg'};
 else b=o.month?{kind:'calendar#events',items:o.monthCount?Array.from({length:o.monthCount},(_,i)=>event({id:'private-'+i,start:{dateTime:new URL(url).searchParams.get('timeMin').slice(0,10)+'T10:00:00+05:00'},end:{dateTime:new URL(url).searchParams.get('timeMin').slice(0,10)+'T11:00:00+05:00'}})):[]}:(o.pages?o.pages[page++]:{kind:'calendar#events',items:[event()]});
 return {getResponseCode:()=>o.code||(o.failWeek&&url.includes('timeMin=2026-11-16T')?403:200),getContentText:()=>JSON.stringify(b)};
 }}});
 vm.runInContext(fs.readFileSync('src/tools/nvsu_calendar_snapshot.gs','utf8'),c);
 return {calls,logs,run:()=>o.month?c.exportKulaginaNvsuNovemberReadOnly():c.exportKulaginaNvsuWeekReadOnly()};
}
function decode(logs){const parts=logs.map(JSON.parse).sort((a,b)=>a.index-b.index);assert.ok(parts.every(p=>p.sha256===parts[0].sha256&&p.total===parts.length));const data=parts.map(p=>p.data).join('');assert.equal(hash(data),parts[0].sha256);return JSON.parse(data);}
test('GET-only week export excludes raw IDs, names, notes, credentials',()=>{
 const f=fixture();assert.equal(f.run().status,'snapshot_ready');const s=decode(f.logs);assert.equal(s.events.length,1);assert.equal(s.events[0].title_hash,hash('PRIVATE PERSONAL TITLE'));assert.equal(s.complete,true);assert.equal(s.week_start,'2026-11-02');
 for(const secret of ['private-event','private-calendar','private-token','PRIVATE PERSONAL TITLE','PRIVATE ROOM'])assert.equal(f.logs.join('').includes(secret),false);
 for(const c of f.calls){assert.equal(c.args.method,'get');assert.equal(c.args.followRedirects,false);assert.equal(c.args.validateHttpsCertificates,true);assert.ok(c.url.startsWith('https://www.googleapis.com/calendar/v3/calendars/'));}
 assert.ok(f.calls[1].url.includes('2026-11-02T00%3A00%3A00%2B05%3A00'));assert.ok(f.calls[1].url.includes('2026-11-09T00%3A00%3A00%2B05%3A00'));
});
test('pagination includes every page before emitting chunks',()=>{
 const f=fixture({pages:[{kind:'calendar#events',items:[],nextPageToken:'next'},{kind:'calendar#events',items:[event()]}]});assert.equal(f.run().status,'snapshot_ready');assert.equal(f.calls.length,3);assert.equal(decode(f.logs).events.length,1);
});
test('repeating token, duplicate events, malformed page reject entire snapshot',()=>{
 for(const pages of [[{kind:'calendar#events',items:[],nextPageToken:'x'},{kind:'calendar#events',items:[],nextPageToken:'x'}],[{kind:'calendar#events',items:[event(),event()]}],[{kind:'calendar#events',items:'broken'}]]){
 const f=fixture({pages});assert.notEqual(f.run().status,'snapshot_ready');assert.equal(f.logs.length,1);assert.equal(JSON.parse(f.logs[0]).snapshot_available,false);
 }
});
test('API error, wrong timezone, invalid target return no partial/secret output',()=>{
 for(const o of [{code:403},{zone:'UTC'},{target:'primary'},{target:''}]){const f=fixture(o);assert.notEqual(f.run().status,'snapshot_ready');assert.equal(f.logs.join('').includes('private-'),false);}
});
test('all-day busy event retained, decorated/recurring events protected',()=>{
 const f=fixture({pages:[{kind:'calendar#events',items:[event({start:{date:'2026-11-03'},end:{date:'2026-11-04'},description:'PRIVATE NOTES',recurringEventId:'private-series'})]}]});f.run();const e=decode(f.logs).events[0];assert.equal(e.start,'2026-11-03T00:00:00+05:00');assert.equal(e.protected,true);assert.equal(f.logs.join('').includes('PRIVATE NOTES'),false);
});
test('invalid dates, naive timestamps, missing end, out-of-range events fail closed',()=>{
 for(const extra of [{start:{date:'2026-02-30'}},{start:{dateTime:'2026-11-02T24:00:00+05:00'},end:{dateTime:'2026-11-03T11:00:00+05:00'}},{start:{dateTime:'2026-11-00T10:00:00+05:00'}},{start:{dateTime:'2026-11-31T10:00:00+05:00'},end:{dateTime:'2026-12-01T11:00:00+05:00'}},{start:{dateTime:'2026-11-02T10:00:00'}},{end:null},{start:{dateTime:'2026-12-02T10:00:00+05:00'},end:{dateTime:'2026-12-02T11:00:00+05:00'}}]){
 const f=fixture({pages:[{kind:'calendar#events',items:[event(extra)]}]});assert.notEqual(f.run().status,'snapshot_ready');assert.equal(JSON.parse(f.logs[0]).snapshot_available,false);
 }
});
test('large snapshots chunk below console-line limit with matching digest',()=>{
 const items=Array.from({length:50},(_,i)=>event({id:'private-'+i}));const f=fixture({pages:[{kind:'calendar#events',items}]});f.run();assert.ok(f.logs.length>1);assert.ok(f.logs.every(x=>x.length<4000));assert.equal(decode(f.logs).events.length,50);
});
test('event limit and unread page limit reject without emitting partial snapshot',()=>{
 for(const pages of [[{kind:'calendar#events',items:Array.from({length:201},(_,i)=>event({id:String(i)}))}],Array.from({length:5},(_,i)=>({kind:'calendar#events',items:[],nextPageToken:String(i)}))]){
 const f=fixture({pages});assert.notEqual(f.run().status,'snapshot_ready');assert.equal(f.logs.length,1);
 }
});

test('actual JavaScript chunks decode in Python without JSON reserialization',()=>{
 const {spawnSync}=require('node:child_process');const f=fixture();f.run();
 const r=spawnSync(process.env.KULAGINA_PYTHON||'python3',['-c',"import sys;sys.path.insert(0,'tools');from nvsu_private_snapshot import decode_chunks;s=decode_chunks(sys.stdin.read());assert len(s['events'])==1;assert s['week_start']=='2026-11-02'"],{input:f.logs.join('\n'),encoding:'utf8'});assert.equal(r.status,0,r.stderr);
});

test('four-week wrapper uses existing collector with exact weekly boundaries and one payload',()=>{
 const f=fixture({month:true});assert.equal(f.run().status,'snapshot_ready');const s=decode(f.logs);assert.equal(s.purpose,'nvsu_read_only_november_comparison');assert.equal(s.snapshots.length,4);assert.deepEqual(s.snapshots.map(x=>x.week_start),['2026-11-02','2026-11-09','2026-11-16','2026-11-23']);assert.equal(s.snapshots[3].week_end,'2026-11-29');assert.equal(f.calls.length,8);assert.ok(f.calls.every(x=>x.args.method==='get'));
 const {spawnSync}=require('node:child_process');const py=spawnSync(process.env.KULAGINA_PYTHON||'python3',['-c',"import sys;sys.path.insert(0,'tools');from nvsu_private_snapshot import decode_chunks,compare_november_snapshots;s=decode_chunks(sys.stdin.read());w=[dict(week_start=x['week_start'],week_end=x['week_end'],status='source_reports_no_schedule',lessons=[]) for x in s['snapshots']];r=compare_november_snapshots(w,s);assert len(r['weeks'])==4;assert not r['ready_for_apply']"],{input:f.logs.join('\n'),encoding:'utf8'});assert.equal(py.status,0,py.stderr);

});
test('four-week failure emits one failure and no earlier-week payload',()=>{
 const f=fixture({month:true,code:403});assert.notEqual(f.run().status,'snapshot_ready');assert.equal(f.logs.length,1);assert.equal(JSON.parse(f.logs[0]).snapshot_available,false);
});

test('late-week failure buffers and discards all prior snapshots',()=>{const f=fixture({month:true,failWeek:true});assert.equal(f.run().snapshot_available,false);assert.equal(f.logs.length,1);assert.equal(JSON.parse(f.logs[0]).status,'snapshot_unavailable');assert.ok(f.calls.length>4);});
test('batch exports nonempty weeks but rejects combined event limit without partial output',()=>{const f=fixture({month:true,monthCount:2});assert.equal(f.run().events,8);assert.equal(decode(f.logs).snapshots.length,4);const bad=fixture({month:true,monthCount:100});assert.equal(bad.run().snapshot_available,false);assert.equal(bad.logs.length,1);});
