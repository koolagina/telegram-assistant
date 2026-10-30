'use strict';
const fs=require('node:fs'),vm=require('node:vm');
const {fixture}=require('./apps-script.cjs');
function consultationFlow(handoff,{patched=true}={}){
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs'),events=[],created=[],deleted=[];
 let now=new Date(handoff.now).getTime(),provider=()=>handoff.proof;
 const NativeDate=Date;class Clock extends NativeDate{constructor(...args){super(...(args.length?args:[now]));}static now(){return now;}static [Symbol.hasInstance](v){return v instanceof NativeDate;}}
 f.ctx.Date=Clock;
 if(patched){const source=require('../../tools/clasp/consultation-teaching-guard.cjs').patchConsultationTeachingGuard(fs.readFileSync('src/telegram_assistant_v2_0_5_candidate.gs','utf8'));vm.runInContext(source.slice(source.indexOf('function prop_(')),f.ctx);}
 f.ctx.log_=()=>{};f.ctx.syncGeneralTask_=()=>{};f.ctx.updateGeneralTaskStatus_=()=>{};
 f.ctx.send_=(id,text,extra)=>{f.sent.push([String(id),text,extra]);return {message_id:f.sent.length};};f.ctx.tg_=()=>true;
 f.properties.set('ASSISTANT_CALENDAR_ID','synthetic-calendar');f.properties.set('ASSISTANT_TEACHING_CALENDAR_ID','synthetic-calendar');
 function event(raw,hold=false){let title=raw.title,description=raw.description||'';const start=new Date(raw.start),end=new Date(raw.end);return {start,end,getId:()=>raw.id,getTitle:()=>title,getDescription:()=>description,getStartTime:()=>start,getEndTime:()=>end,setTitle:v=>title=v,setDescription:v=>description=v,deleteEvent(){if(!hold)throw Error('Unexpected deletion of a lesson');deleted.push(raw.id);events.splice(events.findIndex(e=>e.getId()===raw.id),1);}};}
 events.push(...handoff.events.map(e=>event(e)));
 const calendar={getId:()=> 'synthetic-calendar',getEvents:(start,end)=>events.filter(e=>e.start<end&&e.end>start),getEventById:id=>events.find(e=>e.getId()===id)||null,createEvent(title,start,end,options){const raw={id:'synthetic-hold-'+(created.length+1),title,start:start.toISOString(),end:end.toISOString(),description:options.description};created.push(raw);const e=event(raw,true);events.push(e);return e;}};
 f.ctx.CalendarApp={getCalendarById:id=>id==='synthetic-calendar'?calendar:null};
 f.ctx.consultationTeachingProof_=(...args)=>provider(...args);
 return {f,events,created,deleted,calendar,setProvider:fn=>provider=fn,setNow:stamp=>now=new Date(stamp).getTime(),request:(time='09:00',message=31)=>f.ctx.processMessage_(f.message('/consult '+handoff.requested_date+' '+time+' Synthetic topic',message)),ownerApprove:id=>f.ctx.ownerApproveConsultation_('9001','/approveconsult '+id),ownerReject:id=>f.ctx.ownerRejectConsultation_('9001','/rejectconsult '+id+' Synthetic reason'),cancel:id=>f.ctx.studentCancelConsultation_('1001',id)};
}
module.exports={consultationFlow};
