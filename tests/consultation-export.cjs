'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const headers=['ID заявки','Дата создания','Студент','Telegram chat ID','Желаемая дата','Желаемое время','Длительность, мин','Тема','Статус','Решение / причина','ID события календаря'];
const row=['synthetic-request',new Date('2026-10-29T04:00:00Z'),'Synthetic student','00123','2026-10-29','10:00',20,'Synthetic topic','Ожидает решения','','synthetic-hold'];
function fixture(options={}) {
 const calls=[];
 const sheet={getDataRange(){calls.push('getDataRange');return {getValues(){calls.push('getValues');if(options.fail)throw Error('private details');return options.values||[headers,row];}}}};
 const book={getSpreadsheetTimeZone(){return options.zone||'Asia/Yekaterinburg';},getSheetByName(name){calls.push(name);return options.missing?null:sheet;}};
 const ctx=vm.createContext({Date,SpreadsheetApp:{openById(id){calls.push('open:'+id);return book;}},Utilities:{formatDate(value,zone,format){assert.equal(zone,'Asia/Yekaterinburg');const p=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(value).map(item=>[item.type,item.value]));if(format==='ss')return p.second;return format==='yyyy-MM-dd'?p.year+'-'+p.month+'-'+p.day:p.hour+':'+p.minute;}}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/tools/consultation_snapshot_export.gs'),'utf8'),ctx);
 return {run:()=>JSON.parse(JSON.stringify(ctx.exportConsultationSnapshotReadOnly('synthetic-sheet'))),calls};
}
test('read-only export preserves 11 columns, IDs and true source timestamp',()=>{
 const f=fixture(),result=f.run();assert.equal(result.format_version,1);assert.deepEqual(result.headers,headers);assert.equal(result.rows[0][3],'00123');assert.equal(result.rows[0][1],'2026-10-29T04:00:00.000Z');assert.equal(result.complete,true);assert.ok(!Number.isNaN(Date.parse(result.observed_at)));assert.deepEqual(f.calls,['open:synthetic-sheet','Заявки на консультации','getDataRange','getValues']);
});
test('typed desired date and time use declared spreadsheet timezone',()=>{
 const copy=[...row];copy[4]=new Date('2026-10-28T19:00:00Z');copy[5]=new Date('2026-10-29T05:00:00Z');const result=fixture({values:[headers,copy]}).run();assert.equal(result.rows[0][4],'2026-10-29');assert.equal(result.rows[0][5],'10:00');
});
test('missing sheet fails instead of creating one',()=>assert.throws(fixture({missing:true}).run,/Snapshot unavailable/));
test('unknown timezone and reordered headers fail',()=>{
 assert.throws(fixture({zone:'UTC'}).run,/Snapshot unavailable/);assert.throws(fixture({values:[[...headers].reverse(),row]}).run,/Snapshot unavailable/);
});
test('empty existing sheet with exact headers is explicitly empty',()=>assert.deepEqual(fixture({values:[headers]}).run().rows,[]));
test('blank padding skipped but partial nonblank rows not silently lost',()=>{
 assert.equal(fixture({values:[headers,row,Array(11).fill('')]}).run().rows.length,1);
 assert.throws(fixture({values:[headers,['broken']]}).run,/Snapshot unavailable/);
});
test('read failures sanitized, no result or log side effects',()=>{
 assert.throws(fixture({fail:true}).run,error=>error.message==='Snapshot unavailable; verify source');
});
test('extra columns and invalid creation date rejected',()=>{
 assert.throws(fixture({values:[[...headers,'Unexpected'],[...row,'extra']]}).run,/Snapshot unavailable/);
 const copy=[...row];copy[1]=new Date(NaN);assert.throws(fixture({values:[headers,copy]}).run,/Snapshot unavailable/);
});
test('typed time with seconds is not silently rounded',()=>{
 const copy=[...row];copy[5]=new Date('2026-10-29T05:00:30Z');assert.throws(fixture({values:[headers,copy]}).run,/Snapshot unavailable/);
});
