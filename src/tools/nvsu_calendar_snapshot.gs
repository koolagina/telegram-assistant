/** Read-only manual comparison snapshot, fixed week 2–8 November 2026.
 * No writes/messages/polling/properties updates/deployment. No raw event text/IDs.
 * Hashes are not encryption/authentication. Times and equality remain visible.
 */
function exportKulaginaNvsuWeekReadOnly() {
  const zone='Asia/Yekaterinburg',lower='2026-11-02T00:00:00+05:00',upper='2026-11-09T00:00:00+05:00';
  const fail=()=>{const r={status:'snapshot_unavailable',snapshot_available:false,calendar_writes:0,messages_sent:0};console.log(JSON.stringify(r));return r;};
  try {
    const id=String(PropertiesService.getScriptProperties().getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
    if(!id||id.toLowerCase()==='primary'||id.length>1000||/\s|[\x00-\x1f\x7f]/.test(id))return fail();
    const cal=CalendarApp.getCalendarById(id);
    if(!cal||cal.getId()!==id||cal.getTimeZone()!==zone)return fail();
    const token=ScriptApp.getOAuthToken();if(typeof token!=='string'||!token)return fail();
    const base='https://www.googleapis.com/calendar/v3/calendars/'+encodeURIComponent(id);
    function get(path) {
      const r=UrlFetchApp.fetch(base+path,{method:'get',headers:{Authorization:'Bearer '+token},muteHttpExceptions:true,followRedirects:false,validateHttpsCertificates:true});
      const text=r.getContentText();if(r.getResponseCode()!==200||typeof text!=='string'||text.length>1048576)throw Error('Unavailable');
      return JSON.parse(text);
    }
    function hash(s){return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,s,Utilities.Charset.UTF_8).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');}
    function time(v) {
      if(!v||typeof v!=='object')throw Error('Invalid time');
      if(v.dateTime!==undefined){if(typeof v.dateTime!=='string'||!/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(v.dateTime)||!Number.isFinite(Date.parse(v.dateTime)))throw Error('Invalid timestamp');const wall=v.dateTime.slice(0,19),canonical=new Date(wall+'Z').toISOString().slice(0,19);
        if(wall!==canonical)throw Error('Normalized invalid time');
        return new Date(v.dateTime).toISOString();}
      if(typeof v.date!=='string'||!/^\d{4}-\d\d-\d\d$/.test(v.date)||new Date(v.date+'T00:00:00Z').toISOString().slice(0,10)!==v.date)throw Error('Invalid date');
      return v.date+'T00:00:00+05:00';
    }
    const metadata=get('');
    if(!metadata||metadata.kind!=='calendar#calendar'||metadata.id!==id||metadata.timeZone!==zone)return fail();
    const observed=new Date().toISOString(),events=[],ids=new Set(),tokens=new Set();let pageToken='',complete=false;
    for(let page=0;page<5;page++) {
      const body=get('/events?singleEvents=true&showDeleted=false&maxResults=100&timeZone='+encodeURIComponent(zone)+'&timeMin='+encodeURIComponent(lower)+'&timeMax='+encodeURIComponent(upper)+(pageToken?'&pageToken='+encodeURIComponent(pageToken):''));
      if(!body||body.kind!=='calendar#events'||(body.items!==undefined&&!Array.isArray(body.items)))throw Error('Invalid events page');
      if(body.timeZone!==undefined&&body.timeZone!==zone)throw Error('Timezone mismatch');
      for(const e of body.items||[]) {
        if(!e||typeof e.id!=='string'||!e.id||ids.has(e.id)||!['confirmed','tentative'].includes(e.status))throw Error('Invalid event');
        ids.add(e.id);if(events.length>=200)throw Error('Event limit');
        if((e.summary!==undefined&&typeof e.summary!=='string')||(e.location!==undefined&&typeof e.location!=='string'))throw Error('Invalid text');
        const start=time(e.start),end=time(e.end);
        if(Date.parse(end)<=Date.parse(start)||Date.parse(start)>=Date.parse(upper)||Date.parse(end)<=Date.parse(lower))throw Error('Invalid interval');
        const protectedEvent=!!(e.start.date||e.end.date||e.status!=='confirmed'||e.description||e.attendees||e.recurringEventId||e.recurrence||e.originalStartTime||e.extendedProperties||e.attachments||e.conferenceData||e.transparency==='transparent'||(e.eventType&&e.eventType!=='default'));
        events.push({id_hash:hash(e.id),start:start,end:end,title_hash:hash((e.summary||'').trim()),location_hash:hash((e.location||'').trim()),protected:protectedEvent});
      }
      if(!body.nextPageToken){complete=true;break;}
      if(typeof body.nextPageToken!=='string'||body.nextPageToken.length>4096||tokens.has(body.nextPageToken))throw Error('Invalid page token');
      pageToken=body.nextPageToken;tokens.add(pageToken);
    }
    if(!complete)throw Error('Incomplete snapshot');
    const data=JSON.stringify({format_version:1,purpose:'nvsu_read_only_comparison',complete:true,timezone:zone,week_start:'2026-11-02',week_end:'2026-11-08',observed_at:observed,calendar_hash:hash(id),events:events});
    const digest=hash(data),total=Math.ceil(data.length/3000),lines=[];
    for(let i=0;i<total;i++)lines.push(JSON.stringify({kind:'kulagina_calendar_chunk',index:i,total:total,sha256:digest,data:data.slice(i*3000,(i+1)*3000)}));
    // Buffer all pages and chunks first: an API failure emits no partial snapshot.
    for(const line of lines)console.log(line);
    return {status:'snapshot_ready',snapshot_available:true,events:events.length,chunks:total,calendar_writes:0,messages_sent:0,teaching_schedule_verified:false};
  } catch(error) {return fail();}
}
