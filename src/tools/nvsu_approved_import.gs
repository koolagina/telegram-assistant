/** Thin, create-only executor for a private plan made by existing Python nvsu_sync.
 * Not an HTML parser or general synchronizer. Never PATCH/DELETE, notify or poll.
 * Public template contains no Calendar IDs, source snapshots or approved lessons.
 */
function kulaginaNvsuApprovedImport_(serialized,expectedDigest) {
  const zone='Asia/Yekaterinburg',rootKey='KULAGINA_NVSU_IMPORT_20261109_20261116_V1';
  const report={status:'not_started',purpose:'approved_18_lesson_import',calendar_writes_this_run:0,api_confirmed:0,events_verified:0,not_attempted:18,messages_sent:0,teaching_schedule_verified:false,reason:null,api_error_code:null};
  let props,id,token,base,plan,record=null;
  const emit=status=>{report.status=status;console.log(JSON.stringify(report));return report;};
  const hash=s=>(typeof s==='string'?Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,s,Utilities.Charset.UTF_8):Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,s)).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
  const hex=x=>typeof x==='string'&&/^[0-9a-f]{64}$/.test(x);
  function stop(reason){report.reason=reason;throw Error('Stopped');}
  function keys(x,wanted){return x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===wanted.slice().sort().join('|');}
  function time(x){if(typeof x!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(x)||!Number.isFinite(Date.parse(x)))stop('invalid_time');const wall=x.slice(0,19);if(new Date(wall+'Z').toISOString().slice(0,19)!==wall)stop('invalid_time');return Date.parse(x);}
  function lock(action){const l=LockService.getScriptLock();if(!l.tryLock(5000))stop('lock_busy');try{return action();}finally{l.releaseLock();}}
  function target(){if(hash(String(props.getProperty('ASSISTANT_CALENDAR_ID')||'').trim())!==plan.calendar_hash)stop('target_changed');}
  function parseRecord(raw){if(!raw)return null;const r=JSON.parse(raw);if(r.version!==1||r.plan_digest!==expectedDigest||r.calendar_hash!==plan.calendar_hash||typeof r.run_id!=='string'||!['APPLYING','NEEDS_REVIEW','COMPLETE'].includes(r.phase)||!Array.isArray(r.states)||r.states.length!==18||r.states.some(s=>!['PENDING','SENDING','CONFIRMED'].includes(s)))stop('unverified_journal');return r;}
  function current(){target();const r=parseRecord(props.getProperty(rootKey));if(!r||r.run_id!==record.run_id||JSON.stringify(r)!==JSON.stringify(record))stop('journal_changed');return r;}
  function save(next){lock(()=>{current();props.setProperty(rootKey,JSON.stringify(next));record=next;});}
  function request(method,path,body,missing){
    const args={method:method,headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false,validateHttpsCertificates:true};
    if(method==='post'){if(path!==base+'/events?sendUpdates=none')stop('invalid_write');args.contentType='application/json';args.payload=JSON.stringify(body);report.calendar_writes_this_run++;}
    else if(method!=='get')stop('invalid_write');
    const r=UrlFetchApp.fetch('https://www.googleapis.com/calendar/v3'+path,args),code=r.getResponseCode();
    if(method==='get'&&missing&&(code===404||code===410))return null;
    if(![200,201].includes(code)){report.api_error_code=Number.isInteger(code)?code:null;stop('calendar_api_error');}
    const text=r.getContentText();if(typeof text!=='string'||text.length>1048576)stop('invalid_response');return JSON.parse(text);
  }
  const eventId=op=>'nvsu'+hash(id+'\0'+op.operation_key);
  const bindingKey=op=>'KULAGINA_NVSU_BINDING_'+eventId(op);
  function safeEvent(e,op){
    if(!e||e.id!==eventId(op)||e.status!=='confirmed'||typeof e.etag!=='string'||!e.etag||!e.start||!e.end||e.start.date||e.end.date)return false;
    const p=op.event;
    if(e.summary!==p.title||e.location!==p.location||time(e.start.dateTime)!==time(p.start)||time(e.end.dateTime)!==time(p.end))return false;
    if(e.description||e.recurringEventId||e.recurrence||e.originalStartTime||e.attachments||e.conferenceData||e.extendedProperties||e.colorId||(e.eventType&&e.eventType!=='default')||(e.transparency&&e.transparency!=='opaque')||(e.visibility&&e.visibility!=='default'))return false;
    if(e.attendees!==undefined&&(!Array.isArray(e.attendees)||e.attendees.length))return false;
    if(e.reminders&&e.reminders.overrides&&(!Array.isArray(e.reminders.overrides)||e.reminders.overrides.length))return false;
    return true;
  }
  function source(s){
    const r=UrlFetchApp.fetch(s.url,{method:'get',muteHttpExceptions:true,followRedirects:false,validateHttpsCertificates:true});
    if(r.getResponseCode()!==200)stop('source_unavailable');
    const h=r.getHeaders(),type=String(h['Content-Type']||h['content-type']||'').split(';')[0].trim().toLowerCase(),bytes=r.getContent();
    if(type!=='text/html'||!bytes||bytes.length>1048576||hash(bytes)!==s.raw_sha256)stop('source_changed');
  }
  function weekEvents(s){
    const until=new Date(Date.parse(s.week_start+'T00:00:00Z')+7*86400000).toISOString().slice(0,10),items=[],ids=new Set(),tokens=new Set();let tokenPage='';
    for(let page=0;page<5;page++){
      const b=request('get',base+'/events?singleEvents=true&showDeleted=false&maxResults=100&timeZone='+encodeURIComponent(zone)+'&timeMin='+encodeURIComponent(s.week_start+'T00:00:00+05:00')+'&timeMax='+encodeURIComponent(until+'T00:00:00+05:00')+(tokenPage?'&pageToken='+encodeURIComponent(tokenPage):''));
      if(!b||b.kind!=='calendar#events'||(b.items!==undefined&&!Array.isArray(b.items)))stop('incomplete_calendar');
      for(const e of b.items||[]){if(!e||typeof e.id!=='string'||!e.id||ids.has(e.id)||items.length>=200)stop('incomplete_calendar');ids.add(e.id);items.push(e);}
      if(!b.nextPageToken)return items;
      if(typeof b.nextPageToken!=='string'||b.nextPageToken.length>4096||tokens.has(b.nextPageToken))stop('incomplete_calendar');tokens.add(b.nextPageToken);tokenPage=b.nextPageToken;
    }
    stop('incomplete_calendar');
  }
  function checkWeek(s){
    const listed=weekEvents(s),present=new Set(listed.map(e=>e.id));
    if(record)for(let i=0;i<18;i++)if(record.states[i]==='CONFIRMED'&&plan.operations[i].week_start===s.week_start&&!present.has(eventId(plan.operations[i])))stop('calendar_changed');
    for(const e of listed){
      const index=plan.operations.findIndex(op=>eventId(op)===e.id);
      if(index<0||!record||record.states[index]!=='CONFIRMED'||!safeEvent(e,plan.operations[index]))stop('calendar_changed');
    }
  }
  function inspect(){
    report.api_confirmed=record.states.filter(x=>x==='CONFIRMED').length;report.not_attempted=record.states.filter(x=>x==='PENDING').length;
    let all=true;
    for(let i=0;i<18;i++){
      if(record.states[i]==='PENDING'){all=false;continue;}
      const op=plan.operations[i],e=request('get',base+'/events/'+encodeURIComponent(eventId(op)),undefined,true);
      if(!safeEvent(e,op)){all=false;continue;}
      report.events_verified++;
      if(record.states[i]==='CONFIRMED'){
        const raw=props.getProperty(bindingKey(op));if(!raw){all=false;continue;}
        const receipt=JSON.parse(raw);if(receipt.plan_digest!==expectedDigest||receipt.calendar_hash!==plan.calendar_hash||receipt.receipt!=='api_confirmed'||!receipt.binding||receipt.binding.event_id!==eventId(op)||receipt.binding.operation_key!==op.operation_key)all=false;
      }else all=false;
    }
    return emit(record.phase==='COMPLETE'&&all&&report.events_verified===18?'already_complete':'in_progress_or_review');
  }
  try {
    if(typeof serialized!=='string'||serialized.length>200000||!hex(expectedDigest)||hash(serialized)!==expectedDigest)stop('invalid_plan');
    plan=JSON.parse(serialized);
    if(!keys(plan,['format_version','purpose','approved_at','expires_at','calendar_hash','sources','operations'])||plan.format_version!==1||plan.purpose!=='approved_18_lesson_import'||!hex(plan.calendar_hash)||!Array.isArray(plan.sources)||plan.sources.length!==2||!Array.isArray(plan.operations)||plan.operations.length!==18)stop('invalid_plan');
    const starts=['2026-11-09','2026-11-16'],seen=new Set(),pairs=new Set();
    for(let i=0;i<2;i++){
      const s=plan.sources[i],d=starts[i];
      if(!keys(s,['week_start','week_end','url','raw_sha256'])||s.week_start!==d||s.week_end!==new Date(Date.parse(d+'T00:00:00Z')+6*86400000).toISOString().slice(0,10)||s.url!=='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648//0/?date='+d.slice(8)+'_11_2026'||!hex(s.raw_sha256))stop('invalid_source_proof');
      if(plan.operations.filter(x=>x.week_start===d).length!==9)stop('invalid_plan');
    }
    for(const op of plan.operations){
      if(!keys(op,['week_start','operation_key','source_refs','event'])||!starts.includes(op.week_start)||!hex(op.operation_key)||seen.has(op.operation_key)||!Array.isArray(op.source_refs)||!op.source_refs.length||op.source_refs.length>100||op.source_refs.some(x=>typeof x!=='string'||!x||x.length>1024)||!keys(op.event,['start','end','title','location']))stop('invalid_operation');
      if(JSON.stringify(op).length>2000)stop('operation_too_large');
      seen.add(op.operation_key);const p=op.event,a=time(p.start),b=time(p.end),lower=Date.parse(op.week_start+'T00:00:00+05:00');
      if(typeof p.title!=='string'||!p.title.trim()||p.title.length>2000||typeof p.location!=='string'||!p.location.trim()||p.location.length>1000||a<lower||b>a+24*3600000||b<=a||b>lower+7*86400000)stop('invalid_operation');
      const pair=JSON.stringify([a,b,p.title,p.location]);if(pairs.has(pair))stop('duplicate_operation');pairs.add(pair);
    }
    for(let i=0;i<18;i++)for(let j=0;j<i;j++)if(time(plan.operations[i].event.start)<time(plan.operations[j].event.end)&&time(plan.operations[i].event.end)>time(plan.operations[j].event.start))stop('source_overlap');
    const approved=time(plan.approved_at),expires=time(plan.expires_at);if(expires<=approved||expires-approved>24*3600000)stop('invalid_expiry');
    props=PropertiesService.getScriptProperties();id=String(props.getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
    if(!id||id.toLowerCase()==='primary'||id.length>1000||/\s|[\x00-\x1f\x7f]/.test(id))stop('invalid_target');target();
    const native=CalendarApp.getCalendarById(id);if(!native||native.getId()!==id||native.getTimeZone()!==zone)stop('invalid_target');
    token=ScriptApp.getOAuthToken();if(typeof token!=='string'||!token)stop('authorization_unavailable');base='/calendars/'+encodeURIComponent(id);
    const metadata=request('get',base),role=request('get','/users/me/calendarList/'+encodeURIComponent(id));
    if(!metadata||metadata.id!==id||metadata.timeZone!==zone||!role||role.id!==id||role.accessRole!=='owner')stop('unverified_calendar_owner');
    record=parseRecord(props.getProperty(rootKey));if(record)return inspect();
    const runStart=Date.now();if(runStart<approved-60000||runStart>expires)stop('plan_expired');
    for(const s of plan.sources){source(s);checkWeek(s);}
    for(const op of plan.operations)if(request('get',base+'/events/'+encodeURIComponent(eventId(op)),undefined,true))stop('preexisting_event_id');
    lock(()=>{target();if(props.getProperty(rootKey))stop('claim_exists');const r={version:1,plan_digest:expectedDigest,calendar_hash:plan.calendar_hash,run_id:Utilities.getUuid(),phase:'APPLYING',states:Array(18).fill('PENDING')};props.setProperty(rootKey,JSON.stringify(r));record=r;});
    for(let i=0;i<18;i++){
      if(Date.now()>expires||Date.now()-runStart>240000)stop('execution_window_expired');
      const op=plan.operations[i],s=plan.sources.find(x=>x.week_start===op.week_start);
      target();source(s);checkWeek(s);
      if(request('get',base+'/events/'+encodeURIComponent(eventId(op)),undefined,true))stop('preexisting_event_id');
      const states=record.states.slice();states[i]='SENDING';save({...record,states:states});target();
      if(Date.now()>expires||Date.now()-runStart>240000)stop('execution_window_expired');
      const p=op.event,result=request('post',base+'/events?sendUpdates=none',{id:eventId(op),summary:p.title,location:p.location,start:{dateTime:p.start,timeZone:zone},end:{dateTime:p.end,timeZone:zone}});
      if(!safeEvent(result,op))stop('unverified_insert_receipt');
      lock(()=>{current();props.setProperty(bindingKey(op),JSON.stringify({version:1,plan_digest:expectedDigest,calendar_hash:plan.calendar_hash,receipt:'api_confirmed',observed_etag:result.etag,binding:{event_id:eventId(op),operation_key:op.operation_key,ownership:'created',source_refs:op.source_refs,last_event:op.event}}));const done=record.states.slice();done[i]='CONFIRMED';const next={...record,states:done};props.setProperty(rootKey,JSON.stringify(next));record=next;});
      report.api_confirmed=record.states.filter(x=>x==='CONFIRMED').length;report.not_attempted=record.states.filter(x=>x==='PENDING').length;
    }
    for(const s of plan.sources){source(s);checkWeek(s);}
    for(const op of plan.operations)if(!safeEvent(request('get',base+'/events/'+encodeURIComponent(eventId(op)),undefined,true),op))stop('verification_failed');
    report.events_verified=18;save({...record,phase:'COMPLETE'});return emit('complete');
  }catch(error){
    if(record){report.api_confirmed=record.states.filter(x=>x==='CONFIRMED').length;report.not_attempted=record.states.filter(x=>x==='PENDING').length;}
    if(record&&record.phase==='APPLYING')try{save({...record,phase:'NEEDS_REVIEW'});}catch(_){}
    return emit(record?'needs_review':'blocked');
  }
}
