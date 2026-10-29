/** One non-sensitive test message to configured owner only.
 * Authorized owner-resource test; no polling/Calendar/Sheets/triggers/deployment.
 * Never remove/reset its receipt to retry unknown outcomes. No secrets in logs.
 */
function testKulaginaOwnerMessageOnce() {
  const key='KULAGINA_OWNER_MESSAGE_PROBE_V1';
  const report={status:'not_attempted',messages_attempted_this_run:0,api_accepted:false,delivered:null};
  const emit=status=>{report.status=status;console.log(JSON.stringify(report));return report;};
  const lock=LockService.getScriptLock();
  let held=false,properties,token,owner,botId,claim;
  try {
    if(!lock.tryLock(1000)) return emit('busy');
    held=true;
    properties=PropertiesService.getScriptProperties();
    token=String(properties.getProperty('TELEGRAM_BOT_TOKEN')||'').trim();
    owner=String(properties.getProperty('OWNER_CHAT_ID')||'').trim();
    const match=token.match(/^([1-9][0-9]*):[A-Za-z0-9_-]+$/);
    botId=match?Number(match[1]):0;
    if(!match||token.length>4096||!Number.isSafeInteger(botId)||botId>=Math.pow(2,52)||!/^[1-9][0-9]*$/.test(owner)||!Number.isSafeInteger(Number(owner))||Number(owner)>=Math.pow(2,52)) return emit('invalid_configuration');
    const stored=properties.getProperty(key);
    if(stored) {
      const previous=JSON.parse(stored);
      if(previous.version!==1||!['sending','unknown','api_confirmed','api_rejected'].includes(previous.phase)) return emit('local_state_unavailable');
      if(previous.bot_id!==botId||previous.owner!==owner) return emit('target_changed_requires_review');
      report.api_accepted=previous.phase==='api_confirmed';
      return emit(previous.phase==='api_confirmed'?'already_api_confirmed':previous.phase==='api_rejected'?'already_api_rejected':'inflight_or_unknown');
    }
    claim={version:1,phase:'sending',bot_id:botId,owner:owner,started_at:new Date().toISOString()};
    properties.setProperty(key,JSON.stringify(claim));
  } catch(error) { return emit('local_state_unavailable'); }
  finally { if(held) {lock.releaseLock();held=false;} }

  // Claim is durable; no network call while holding the working bot's lock.
  let phase='unknown',messageId=null;
  report.messages_attempted_this_run=1;
  try {
    const response=UrlFetchApp.fetch('https://api.telegram.org/bot'+token+'/sendMessage',{
      method:'post',contentType:'application/json',muteHttpExceptions:true,
      followRedirects:false,validateHttpsCertificates:true,
      payload:JSON.stringify({chat_id:Number(owner),
        text:'Проверка подключения Telegram-ассистента. Это тестовое сообщение; отвечать в боте не нужно.',
        link_preview_options:{is_disabled:true}})});
    const code=response.getResponseCode();
    if(code>=400&&code<=499&&code!==408) phase='api_rejected';
    else if(code===200) {
      const text=response.getContentText();
      if(typeof text!=='string'||text.length>65536) throw Error('Invalid response');
      const body=JSON.parse(text),result=body&&body.result;
      if(body&&body.ok===false&&Number.isInteger(body.error_code)&&body.error_code>=100&&body.error_code<=599) phase='api_rejected';
      else if(body&&body.ok===true&&result&&Number.isSafeInteger(result.message_id)&&result.message_id>0&&result.message_id<Math.pow(2,52)&&
        result.chat&&Number.isSafeInteger(result.chat.id)&&result.chat.id===Number(owner)&&result.chat.type==='private'&&
        result.from&&Number.isSafeInteger(result.from.id)&&result.from.id===botId&&result.from.is_bot===true) {
        phase='api_confirmed';messageId=result.message_id;report.api_accepted=true;
      }
    }
  } catch(error) { phase='unknown'; }

  try {
    if(!lock.tryLock(1000)) return emit('needs_recovery');
    held=true;
    const current=JSON.parse(properties.getProperty(key)||'null');
    if(!current||current.phase!=='sending'||current.started_at!==claim.started_at||current.bot_id!==botId||current.owner!==owner) return emit('needs_recovery');
    properties.setProperty(key,JSON.stringify({...claim,phase:phase,message_id:messageId}));
  } catch(error) { return emit('needs_recovery'); }
  finally { if(held) lock.releaseLock(); }
  return emit(phase);
}
