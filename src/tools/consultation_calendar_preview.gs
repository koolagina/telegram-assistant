/** READ-ONLY preview for one temporary TEST event, not a student booking.
 * Existing Calendar ID + existing Apps Script OAuth; GET only, no secret/ID logs.
 * No writes, property updates, messages, polling, triggers or deployment.
 */
function previewKulaginaCalendarTest() {
  const zone='Asia/Yekaterinburg';
  const report={status:'not_checked',purpose:'temporary_TEST_only',test_slot:null,
    calendar_writes:0,messages_sent:0,write_access_verified:false,
    teaching_schedule_verified:false,only_selected_calendar_checked:true,
    http_gets:0,api_error_code:null,api_error_reason:null};
  const emit=status=>{report.status=status;console.log(JSON.stringify(report));return report;};
  try {
    const id=String(PropertiesService.getScriptProperties().getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
    if(!id||id.toLowerCase()==='primary'||id.length>1000||/\s|[\x00-\x1f\x7f]/.test(id)) return emit('invalid_target');
    const calendar=CalendarApp.getCalendarById(id);
    if(!calendar||calendar.getId()!==id) return emit('unverified_target');
    if(calendar.getTimeZone()!==zone) return emit('timezone_review_required');
    const token=ScriptApp.getOAuthToken();
    if(typeof token!=='string'||!token) return emit('authorization_unavailable');
    const base='https://www.googleapis.com/calendar/v3/calendars/'+encodeURIComponent(id);
    function get(path) {
      report.http_gets++;
      const response=UrlFetchApp.fetch(base+path,{method:'get',
        headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,
        followRedirects:false,validateHttpsCertificates:true});
      const code=response.getResponseCode(),text=response.getContentText();
      if(typeof text!=='string'||text.length>65536) {report.status='unverified_response';throw Error('Invalid response');}
      const body=JSON.parse(text);
      if(code!==200) {
        report.status='calendar_api_unavailable';report.api_error_code=Number.isInteger(code)?code:null;
        const errors=body&&body.error&&body.error.errors;
        const reason=Array.isArray(errors)&&errors[0]?errors[0].reason:null;
        if(['accessNotConfigured','forbidden','insufficientPermissions','authError','rateLimitExceeded'].includes(reason)) report.api_error_reason=reason;
        throw Error('API unavailable');
      }
      return body;
    }
    const metadata=get('');
    if(!metadata||metadata.kind!=='calendar#calendar'||metadata.id!==id||metadata.timeZone!==zone) return emit('unverified_response');
    const now=new Date();
    for(let day=0;day<8;day++) {
      const date=Utilities.formatDate(new Date(now.getTime()+day*86400000),zone,'yyyy-MM-dd');
      for(const time of ['10:00','10:40']) {
        const startText=date+'T'+time+':00+05:00',start=new Date(startText);
        const weekday=Number(Utilities.formatDate(start,zone,'u'));
        if(weekday<1||weekday>5||start.getTime()-now.getTime()<30*60000) continue;
        const end=new Date(start.getTime()+20*60000);
        const endText=Utilities.formatDate(end,zone,'yyyy-MM-dd')+'T'+(time==='10:00'?'10:20':'11:00')+':00+05:00';
        const body=get('/events?singleEvents=true&showDeleted=false&maxResults=1&timeZone='+encodeURIComponent(zone)+
          '&timeMin='+encodeURIComponent(startText)+'&timeMax='+encodeURIComponent(endText));
        if(!body||body.kind!=='calendar#events'||(body.items!==undefined&&!Array.isArray(body.items))) return emit('unverified_response');
        const after=new Date();
        if(after.getTime()<now.getTime()) return emit('clock_review_required');
        if(start.getTime()-after.getTime()<30*60000) continue;
        if((body.items&&body.items.length)||body.nextPageToken) continue; // Never mistake an unread page for an empty calendar.
        report.test_slot={start:startText,end:endText,timezone:zone,busy_count:0};
        return emit('preview_ready');
      }
    }
    return emit('no_test_slot_found');
  } catch(error) { return emit(report.status==='not_checked'?'unavailable':report.status); }
}
