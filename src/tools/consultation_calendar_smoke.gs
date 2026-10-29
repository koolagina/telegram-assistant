/** One approved TEST-only Calendar round trip for the exact user preview.
 * Never reset the receipt to retry unknown outcomes. No messages/Sheets/polling.
 */
function testKulaginaCalendarOnce() { return kulaginaCalendarSmoke_(false); }
function inspectKulaginaCalendarTest() { return kulaginaCalendarSmoke_(true); }

function kulaginaCalendarSmoke_(inspectOnly) {
  const key='KULAGINA_CALENDAR_TEST_V1',zone='Asia/Yekaterinburg';
  const start='2026-10-30T10:00:00+05:00',end='2026-10-30T10:20:00+05:00';
  const initialTitle='TEST — проверка подключения (временно)',updatedTitle='TEST — проверка обновления (временно)';
  const description='Временная техническая проверка. Не консультация и не занятие.';
  const report={status:'not_started',purpose:'temporary_TEST_only',test_start:start,test_end:end,teaching_schedule_verified:false,create_verified:false,update_verified:false,
    cleanup_confirmed:false,cleanup_required:false,write_requests_this_run:0,messages_sent:0,api_error_code:null};
  const emit=status=>{report.status=status;console.log(JSON.stringify(report));return report;};
  let properties,calendarId,record,token;
  function locked(action) {
    const lock=LockService.getScriptLock();
    if(!lock.tryLock(1000)) throw Error('Working lock busy');
    try { return action(); } finally { lock.releaseLock(); }
  }
  function parseStored(text) {
    if(!text) return null;
    const value=JSON.parse(text);
    if(value.version!==1||typeof value.marker!=='string'||!/^[0-9a-f]{32}$/.test(value.marker)||value.event_id!=='ktest'+value.marker||value.start!==start||value.end!==end||
      !['creating','created','updating','updated','deleting','finished'].includes(value.phase)) throw Error('Unverified state');
    return value;
  }
  function save(phase,etag) {
    locked(()=>{
      const current=parseStored(properties.getProperty(key));
      if(!current||current.marker!==record.marker||current.phase!==record.phase||properties.getProperty('ASSISTANT_CALENDAR_ID').trim()!==calendarId) throw Error('Claim changed');
      const next={...record,phase:phase,etag:etag===undefined?record.etag:etag,
        create_verified:report.create_verified,update_verified:report.update_verified,cleanup_confirmed:report.cleanup_confirmed};
      properties.setProperty(key,JSON.stringify(next));record=next;
    });
  }
  function request(method,path,body,etag,missingOkay) {
    const args={method:method,headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false,validateHttpsCertificates:true};
    if(etag) args.headers['If-Match']=etag;
    if(body!==undefined){args.contentType='application/json';args.payload=JSON.stringify(body);}
    if(method!=='get')report.write_requests_this_run++;
    const response=UrlFetchApp.fetch('https://www.googleapis.com/calendar/v3'+path,args);
    const code=response.getResponseCode();
    if(method==='get'&&missingOkay&&(code===404||code===410))return null;
    if(![200,201,204].includes(code)){report.api_error_code=Number.isInteger(code)?code:null;throw Error('Calendar API rejected');}
    if(code===204)return {};
    const text=response.getContentText();
    if(typeof text!=='string'||text.length>65536)throw Error('Invalid API response');
    return JSON.parse(text);
  }
  function owns(event) {
    return !!(event&&event.id===record.event_id&&event.extendedProperties&&event.extendedProperties.private&&event.extendedProperties.private.kulagina_test_probe===record.marker&&
      event.start&&new Date(event.start.dateTime).getTime()===new Date(start).getTime()&&event.end&&new Date(event.end.dateTime).getTime()===new Date(end).getTime()&&
      [initialTitle,updatedTitle].includes(event.summary)&&event.description===description&&event.location==='Кабинет 317 (TEST)'&&
      !event.recurringEventId&&!event.recurrence&&(!event.attendees||event.attendees.length===0)&&!event.attachments&&!event.conferenceData);
  }
  function validEtag(event){return typeof event.etag==='string'&&event.etag.length>0&&event.etag.length<512&&!/[\x00-\x1f\x7f]/.test(event.etag);}
  try {
    properties=PropertiesService.getScriptProperties();
    calendarId=String(properties.getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
    if(!calendarId||calendarId.toLowerCase()==='primary'||calendarId.length>1000||/\s|[\x00-\x1f\x7f]/.test(calendarId))return emit('invalid_target');
    try { record=parseStored(properties.getProperty(key)); } catch(error) {return emit('local_state_unavailable');}
    if(record&&record.calendar_id!==calendarId)return emit('target_changed_requires_review');
    if(record&&!inspectOnly){
      report.create_verified=record.create_verified===true;report.update_verified=record.update_verified===true;report.cleanup_confirmed=record.cleanup_confirmed===true;
      report.cleanup_required=record.phase==='finished'?false:null;
      return emit(record.phase==='finished'?'already_complete':'inflight_or_unknown');
    }
    if(!record&&inspectOnly)return emit('not_run');
    const calendar=CalendarApp.getCalendarById(calendarId);
    if(!calendar||calendar.getId()!==calendarId||calendar.getTimeZone()!==zone)return emit('unverified_target');
    token=ScriptApp.getOAuthToken();
    if(typeof token!=='string'||!token)return emit('authorization_unavailable');
    const base='/calendars/'+encodeURIComponent(calendarId),eventPath=()=>base+'/events/'+encodeURIComponent(record.event_id);
    if(inspectOnly){
      const actual=request('get',eventPath(),undefined,undefined,true);
      if(!actual||(actual.id===record.event_id&&actual.status==='cancelled')){
        report.cleanup_confirmed=true;report.cleanup_required=false;report.owned_test_event_found=false;return emit('test_event_absent');
      }
      report.owned_test_event_found=owns(actual);report.cleanup_required=report.owned_test_event_found?true:null;
      report.unchanged_since_ack=!!(validEtag(actual)&&actual.etag===record.etag);
      return emit(report.owned_test_event_found?'test_event_present':'manual_review_required');
    }
    if(new Date(start).getTime()-new Date().getTime()<30*60000)return emit('test_window_expired');
    const membership=request('get','/users/me/calendarList/'+encodeURIComponent(calendarId));
    if(!membership||membership.id!==calendarId||membership.accessRole!=='owner')return emit('calendar_owner_not_verified');
    const metadata=request('get',base);
    if(!metadata||metadata.id!==calendarId||metadata.timeZone!==zone)return emit('unverified_target');
    const busy=request('get',base+'/events?singleEvents=true&showDeleted=false&maxResults=1&timeMin='+encodeURIComponent(start)+'&timeMax='+encodeURIComponent(end));
    if(!busy||busy.kind!=='calendar#events'||(busy.items!==undefined&&!Array.isArray(busy.items)))return emit('unverified_busy_response');
    if((busy.items&&busy.items.length)||busy.nextPageToken)return emit('test_slot_became_busy');
    locked(()=>{
      if(properties.getProperty(key))throw Error('Another attempt already claimed');
      if(String(properties.getProperty('ASSISTANT_CALENDAR_ID')||'').trim()!==calendarId)throw Error('Target changed');
      if(new Date(start).getTime()-new Date().getTime()<30*60000)throw Error('Window expired');
      const marker=Utilities.getUuid().replace(/-/g,'').toLowerCase();
      if(!/^[0-9a-f]{32}$/.test(marker))throw Error('Invalid operation identity');
      record={version:1,calendar_id:calendarId,event_id:'ktest'+marker,marker:marker,start:start,end:end,phase:'creating',etag:null,create_verified:false,update_verified:false,cleanup_confirmed:false};
      properties.setProperty(key,JSON.stringify(record));
    });
    report.cleanup_required=null;
    const created=request('post',base+'/events?sendUpdates=none',{id:record.event_id,summary:initialTitle,description:description,location:'Кабинет 317 (TEST)',
      start:{dateTime:start,timeZone:zone},end:{dateTime:end,timeZone:zone},visibility:'private',reminders:{useDefault:false},
      extendedProperties:{private:{kulagina_test_probe:record.marker}}});
    if(!owns(created)||created.summary!==initialTitle||!validEtag(created))throw Error('Unverified create acknowledgement');
    report.create_verified=true;report.cleanup_required=true;save('created',created.etag);
    const beforeUpdate=request('get',eventPath());
    if(!owns(beforeUpdate)||beforeUpdate.summary!==initialTitle||beforeUpdate.etag!==record.etag||!validEtag(beforeUpdate))throw Error('Manual change before update');
    save('updating');
    const updated=request('patch',eventPath()+'?sendUpdates=none',{summary:updatedTitle},beforeUpdate.etag);
    if(!owns(updated)||updated.summary!==updatedTitle||!validEtag(updated))throw Error('Unverified update acknowledgement');
    report.update_verified=true;save('updated',updated.etag);
    const beforeDelete=request('get',eventPath());
    if(!owns(beforeDelete)||beforeDelete.summary!==updatedTitle||beforeDelete.etag!==record.etag||!validEtag(beforeDelete))throw Error('Manual change before cleanup');
    save('deleting');
    request('delete',eventPath()+'?sendUpdates=none',undefined,beforeDelete.etag);
    const afterDelete=request('get',eventPath(),undefined,undefined,true);
    if(afterDelete&&!(afterDelete.id===record.event_id&&afterDelete.status==='cancelled'))throw Error('Cleanup not confirmed');
    report.cleanup_confirmed=true;report.cleanup_required=false;save('finished');return emit('complete');
  } catch(error) {return emit(record?'needs_review':'preflight_unavailable');}
}
