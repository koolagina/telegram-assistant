'use strict';
/** Offline synthetic Python -> Apps Script consultation lifecycle demo. */
const {execFileSync}=require('node:child_process'),assert=require('node:assert/strict');
const {consultationFlow}=require('../tests/helpers/consultation-flow.cjs');
const h=JSON.parse(execFileSync(process.env.KULAGINA_PYTHON||'python3',['tools/schedule_consultation_demo.py','--fixture-handoff'],{encoding:'utf8'}));
const results=[];
for(const action of ['approve_then_cancel','reject']){
 const w=consultationFlow(h);w.request();const row=w.f.sheet('Заявки на консультации').rows[1];
 if(action==='approve_then_cancel'){w.ownerApprove(row[0]);assert.equal(row[8],'Подтверждена');w.cancel(row[0]);}else w.ownerReject(row[0]);
 assert.equal(w.created.length,1);assert.equal(w.deleted.length,1);assert.equal(w.events.length,h.events.length);
 results.push({scenario:action,requests:1,preliminary_events:1,removed_owned_events:1,preserved_lessons:w.events.length,final_status:row[8],delivery_verified:false});
}
console.log(JSON.stringify({mode:'offline_schedule_booking_demo',scenarios:results,real_calendar_writes:0,real_messages_sent:0},null,2));
