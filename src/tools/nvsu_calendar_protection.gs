/** GET-only aggregate diagnosis of the previous snapshot's protection flags.
 * Fixed 2–8 November 2026. No raw IDs/text/extensions, writes, sends or setup.
 * Reasons mirror nvsu_calendar_snapshot.gs; they are NOT ownership evidence.
 */
function inspectKulaginaNvsuProtectionReadOnly() {
  const zone='Asia/Yekaterinburg',lower='2026-11-02T00:00:00+05:00',upper='2026-11-09T00:00:00+05:00';
  function emit(status,events,reasons,protectedEvents){const r={status:status,purpose:'nvsu_protection_diagnosis',week_start:'2026-11-02',week_end:'2026-11-08',events:events,reasons:reasons,protected_events:protectedEvents,ownership_verified:false,teaching_schedule_verified:false,calendar_writes:0,messages_sent:0};console.log(JSON.stringify(r));return r;}
  try {
    const id=String(PropertiesService.getScriptProperties().getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
    if(!id||id.toLowerCase()==='primary'||id.length>1000||/\s|[\x00-\x1f\x7f]/.test(id))throw Error('Invalid target');
    const cal=CalendarApp.getCalendarById(id);
    if(!cal||cal.getId()!==id||cal.getTimeZone()!==zone)throw Error('Target unavailable');
    const token=ScriptApp.getOAuthToken();if(typeof token!=='string'||!token)throw Error('Authorization unavailable');
    const base='https://www.googleapis.com/calendar/v3/calendars/'+encodeURIComponent(id);
    function get(path){const r=UrlFetchApp.fetch(base+path,{method:'get',headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false,validateHttpsCertificates:true});const text=r.getContentText();if(r.getResponseCode()!==200||typeof text!=='string'||text.length>1048576)throw Error('Unavailable response');return JSON.parse(text);}
    function time(v) {
      if(!v||typeof v!=='object')throw Error('Invalid time');
      if(v.dateTime!==undefined){if(typeof v.dateTime!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(v.dateTime)||!Number.isFinite(Date.parse(v.dateTime)))throw Error('Invalid timestamp');const wall=v.dateTime.slice(0,19);if(new Date(wall+'Z').toISOString().slice(0,19)!==wall)throw Error('Normalized time');return Date.parse(v.dateTime);}
      if(typeof v.date!=='string'||!/^\d{4}-\d\d-\d\d$/.test(v.date)||new Date(v.date+'T00:00:00Z').toISOString().slice(0,10)!==v.date)throw Error('Invalid date');
      return Date.parse(v.date+'T00:00:00+05:00');
    }
    const meta=get('');if(!meta||meta.kind!=='calendar#calendar'||meta.id!==id||meta.timeZone!==zone)throw Error('Target mismatch');
    const reasons={all_day:0,tentative:0,description:0,attendees:0,recurrence:0,extended_properties:0,attachments:0,conference:0,transparent:0,special_event:0};
    const ids=new Set(),tokens=new Set();let pageToken='',complete=false,protectedEvents=0;
    for(let page=0;page<5;page++){
      const b=get('/events?singleEvents=true&showDeleted=false&maxResults=100&timeZone='+encodeURIComponent(zone)+'&timeMin='+encodeURIComponent(lower)+'&timeMax='+encodeURIComponent(upper)+(pageToken?'&pageToken='+encodeURIComponent(pageToken):''));
      if(!b||b.kind!=='calendar#events'||(b.items!==undefined&&!Array.isArray(b.items))||(b.timeZone!==undefined&&b.timeZone!==zone))throw Error('Invalid page');
      for(const e of b.items||[]){
        if(!e||typeof e.id!=='string'||!e.id||ids.has(e.id)||ids.size>=200||!['confirmed','tentative'].includes(e.status))throw Error('Invalid event');
        const start=time(e.start),end=time(e.end);
        if(end<=start||start>=Date.parse(upper)||end<=Date.parse(lower))throw Error('Invalid interval');
        ids.add(e.id);
        const flags={all_day:!!(e.start.date||e.end.date),tentative:e.status!=='confirmed',description:!!e.description,attendees:!!e.attendees,recurrence:!!(e.recurringEventId||e.recurrence||e.originalStartTime),extended_properties:!!e.extendedProperties,attachments:!!e.attachments,conference:!!e.conferenceData,transparent:e.transparency==='transparent',special_event:!!(e.eventType&&e.eventType!=='default')};
        if(Object.values(flags).some(Boolean))protectedEvents++;
        for(const k of Object.keys(flags))if(flags[k])reasons[k]++;
      }
      if(!b.nextPageToken){complete=true;break;}
      if(typeof b.nextPageToken!=='string'||b.nextPageToken.length>4096||tokens.has(b.nextPageToken))throw Error('Invalid pagination');
      pageToken=b.nextPageToken;tokens.add(pageToken);
    }
    if(!complete)throw Error('Incomplete snapshot');
    return emit('complete',ids.size,reasons,protectedEvents);
  }catch(error){return emit('unavailable',null,null,null);}
}
