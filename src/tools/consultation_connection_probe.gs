/** Read-only connection probe, not a bot deployment or integration acceptance.
 * Uses EXISTING Script Properties; never returns/logs token/IDs/user data.
 * No polling, messages, Calendar events, Sheets, initialize or trigger operations.
 * The caller must run it only in their authorized Apps Script project.
 */
function probeKulaginaConnectionsReadOnly() {
  const report={format_version:1,mode:'read_only_metadata',
    telegram:{credential_present:false,verified:false,status:'not_configured'},
    calendar:{configured:false,read_access_verified:false,timezone_matches:false,status:'not_configured'},
    owner_target:{configured:false,identity_verified:false},
    ready_for_private_preview:false,writes_performed:0,messages_sent:0,polling_started:false};
  let token='',owner='',calendarId='';
  try {
    const properties=PropertiesService.getScriptProperties();
    token=String(properties.getProperty('TELEGRAM_BOT_TOKEN')||'').trim();
    owner=String(properties.getProperty('OWNER_CHAT_ID')||'').trim();
    calendarId=String(properties.getProperty('ASSISTANT_CALENDAR_ID')||'').trim();
  } catch(error) {
    report.telegram.status='configuration_unavailable';report.calendar.status='configuration_unavailable';return report;
  }
  report.owner_target.configured=/^[1-9][0-9]*$/.test(owner)&&Number.isSafeInteger(Number(owner))&&Number(owner)<Math.pow(2,52);
  report.telegram.credential_present=token.length>0;
  if(token) {
    const match=token.match(/^([1-9][0-9]*):[A-Za-z0-9_-]+$/);
    const botId=match?Number(match[1]):0;
    if(!match||token.length>4096||!Number.isSafeInteger(botId)||botId>=Math.pow(2,52)) report.telegram.status='invalid_configuration';
    else {
      try {
        const response=UrlFetchApp.fetch('https://api.telegram.org/bot'+token+'/getMe',{
          method:'post',contentType:'application/json',payload:'{}',muteHttpExceptions:true,
          followRedirects:false,validateHttpsCertificates:true});
        if(response.getResponseCode()!==200) report.telegram.status='api_rejected';
        else {
          const text=response.getContentText();
          if(typeof text!=='string'||text.length>65536) throw Error('Invalid response');
          const body=JSON.parse(text),result=body&&body.result;
          report.telegram.verified=!!(body&&body.ok===true&&result&&result.is_bot===true&&Number.isSafeInteger(result.id)&&result.id===botId);
          report.telegram.status=report.telegram.verified?'verified':'unverified_response';
        }
      } catch(error) { report.telegram.status='unavailable'; } // Never expose token-bearing exception/URL.
    }
  }
  report.calendar.configured=calendarId.length>0;
  if(calendarId) {
    if(calendarId.toLowerCase()==='primary'||calendarId.length>1000||/\s|[\x00-\x1f\x7f]/.test(calendarId)) report.calendar.status='invalid_target';
    else {
      try {
        const calendar=CalendarApp.getCalendarById(calendarId);
        if(!calendar||calendar.getId()!==calendarId) report.calendar.status='unverified_resource';
        else {
          report.calendar.timezone_matches=calendar.getTimeZone()==='Asia/Yekaterinburg';
          report.calendar.read_access_verified=true;
          report.calendar.status=report.calendar.timezone_matches?'accessible':'accessible_timezone_review';
        }
      } catch(error) { report.calendar.status='unavailable'; }
    }
  }
  report.ready_for_private_preview=report.telegram.verified&&report.calendar.read_access_verified&&report.owner_target.configured;
  return report;
}

/** Convenience runner: logs ONLY the sanitized report above, no raw data.
 * Running this function does not start the bot or change its resources.
 */
function showKulaginaConnectionProbe() {
  console.log(JSON.stringify(probeKulaginaConnectionsReadOnly()));
}
