'use strict';
/** Local 2.0.5 candidate gate. No installed bot change or live provider bootstrap. */
const fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../src/telegram_assistant_v2_0_5_candidate.gs'),'utf8');
const a=source.indexOf('function consultationTeachingCalendar_('),b=source.indexOf('function consultationAvailability_(',a),original=source.slice(a,b);
const replacement=original.replace('function consultationTeachingCalendar_()','function consultationConfiguredTeachingCalendar_()')+String.raw`function consultationTeachingCalendar_(start,end) {
  const calendar=consultationConfiguredTeachingCalendar_();
  if(start===undefined&&end===undefined)return calendar; // Menu only; never offer/book without a range proof.
  if(!(start instanceof Date)||!(end instanceof Date)||!Number.isFinite(start.getTime())||!Number.isFinite(end.getTime())||end<=start||typeof consultationTeachingProof_!=='function')throw Error('Полнота расписания не подтверждена');
  const before=Date.now(),proof=consultationTeachingProof_(new Date(start.getTime()),new Date(end.getTime()),String(calendar.getId())),now=Date.now();
  const fields='calendar_id|calendar_revision|covered_end|covered_start|observed_at|owner_chat_id|source_observed_at|source_revision|version';
  const stamp=value=>typeof value==='string'&&/T.*(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(value)?Date.parse(value):NaN;
  if(!proof||typeof proof!=='object'||Array.isArray(proof)||Object.keys(proof).sort().join('|')!==fields||proof.version!==1||proof.owner_chat_id!==String(owner_())||proof.calendar_id!==String(calendar.getId())||typeof proof.source_revision!=='string'||!/^[a-f0-9]{64}$/.test(proof.source_revision)||typeof proof.calendar_revision!=='string'||!/^[a-f0-9]{64}$/.test(proof.calendar_revision))throw Error('Неподтверждённый источник расписания');
  const observed=stamp(proof.observed_at),sourceObserved=stamp(proof.source_observed_at),from=stamp(proof.covered_start),to=stamp(proof.covered_end);
  if(![observed,sourceObserved,from,to].every(Number.isFinite)||now<before||observed>now||sourceObserved>observed||now-sourceObserved>300000||now-observed>300000||from>start.getTime()||to<end.getTime()||to<=from)throw Error('Проверка расписания устарела или не покрывает дату');
  return calendar;
}
`;
const pairs=[[original,replacement],['consultationTeachingCalendar_().getEvents(result.start,result.end)','consultationTeachingCalendar_(result.start,result.end).getEvents(result.start,result.end)'],['consultationTeachingCalendar_().getEvents(day,end)','consultationTeachingCalendar_(day,end).getEvents(day,end)']];
function patchConsultationTeachingGuard(value){
 for(const [old,next]of pairs){if(value.split(old).length!==2)throw Error('Reviewed consultation teaching precondition mismatch');value=value.replace(old,next);}
 return value;
}
function restoreConsultationTeachingGuard(value){
 for(const [old,next]of pairs.slice().reverse()){if(value.split(next).length!==2)throw Error('Exact consultation teaching patch required');value=value.replace(next,old);}
 return value;
}
module.exports={patchConsultationTeachingGuard,restoreConsultationTeachingGuard};
