'use strict';
/** Offline stable-ID binding recipe. No real Google/Telegram operations. */
const fs=require('node:fs'),path=require('node:path');
const {patchMain}=require('./prepare-legacy-candidate.cjs'),{patchFileRecovery}=require('./legacy-file-recovery.cjs'),{patchUpdateQueue}=require('./legacy-update-queue.cjs'),{patchReplyRecovery}=require('./legacy-reply-recovery.cjs');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const candidate=fs.readFileSync(path.join(__dirname,'../../src/telegram_assistant_v2_0_5_candidate.gs'),'utf8');
const base=patchReplyRecovery(patchUpdateQueue(patchFileRecovery(patchMain(archive.replace(/  \/\/ Callback confirmation is best-effort:[\s\S]*?(?=  if\(!isOwner_)/,"  tg_('answerCallbackQuery',{callback_query_id:q.id});\n")))));
function extract(source,name){const start=source.indexOf('function '+name+'(');if(start<0)throw Error('Reviewed function missing');const end=source.indexOf('\nfunction ',start+1);return source.slice(start,end<0?source.length:end).trimEnd()+'\n';}
const keyboard=`function taskKeyboard_(chatId) {
  const own=rows_('Поручения',CFG.taskHeaders).slice(1).filter(r=>String(r[9])===String(chatId));
  const active=own.filter(r=>['Отправлено','В работе','Доработка'].includes(String(r[5])));
  for(const row of active) {
    const id=String(row[0]||'');
    if(!validLegacyTaskId_(id)||own.filter(r=>String(r[0]||'')===id).length!==1)
      throw Error('Идентификаторы поручений требуют проверки');
  }
  return active.slice(0,20).map(row=>[{text:String(row[0]).slice(0,40),callback_data:'taskid:'+String(row[0])}]);
}
`;
const choose=`function chooseTask_(chatId) {
  let buttons;
  try { buttons=taskKeyboard_(chatId); }
  catch(error) { return send_(chatId,'Не удалось безопасно показать поручения. Попробуйте позже или обратитесь к преподавателю.'); }
  if(!buttons.length) return send_(chatId,'Активных поручений для ответа пока нет. Можете отправить обычное сообщение.');
  return send_(chatId,'Выберите поручение, на которое хотите ответить. Затем пришлите текст или файл:',{reply_markup:{inline_keyboard:buttons}});
}
`;
const callback=`function processCallback_(q) {
  if(!q||!q.message||!q.message.chat||!q.from) return;
  const id=String(q.message.chat.id),data=String(q.data||'');
  if(q.message.chat.type!=='private'||String(q.from.id)!==id) return;
  try { tg_('answerCallbackQuery',{callback_query_id:q.id}); }
  catch(error) { log_('Устаревший callback',q.id,'Подтверждение кнопки недоступно'); }
  if(!isOwner_(id)&&accessStatus_(id)!=='approved') { send_(id,'Доступ к поручениям не разрешён.'); return; }
  if(!data.startsWith('taskid:')&&!data.startsWith('task:')) return;
  const task=data.startsWith('taskid:')?legacyTaskForId_(id,data.slice(7)):null;
  // Old row buttons cannot prove which task they displayed before a sort.
  // Null is a persistent reselection requirement, not an automatic choice.
  PropertiesService.getScriptProperties().setProperty('SELECTED_TASK_'+id,JSON.stringify({version:1,chat_id:id,task_id:task?String(task.row[0]):null}));
  if(!task) { send_(id,'Эта кнопка устарела или поручение недоступно. Откройте /tasks и выберите поручение заново.'); return; }
  send_(id,'Выбрано поручение '+String(task.row[0])+'. Теперь отправьте ответ или файл.');
}
`;
const snapshot=extract(candidate,'operationSnapshot_').replace("const sh=tab_('Снимки операций',['Ключ','Payload JSON','Создано']);","const sh=legacyBindingSnapshots_();");
const helper=String.raw`function validLegacyTaskId_(id) {
  return typeof id==='string'&&id!==''&&id===id.trim()&&!/[\x00-\x1f\x7f]/.test(id)&&Utilities.newBlob('taskid:'+id).getBytes().length<=64;
}
function legacyTaskForId_(chatId,id) {
  if(!validLegacyTaskId_(id)) return null;
  const all=rows_('Поручения',CFG.taskHeaders);
  const matches=all.slice(1).map((row,i)=>({row,index:i+2})).filter(t=>String(t.row[9])===String(chatId)&&String(t.row[0]||'')===id);
  return matches.length===1&&['Отправлено','В работе','Доработка'].includes(String(matches[0].row[5]))?matches[0]:null;
}
function legacyBindingSnapshots_() {
  const headers=['Ключ','Payload JSON','Создано'],existing=ss_().getSheetByName('Снимки операций');
  if(existing) {
    const row=existing.getRange(1,1,1,headers.length).getValues()[0];
    if(existing.getLastRow()<1||headers.some((h,i)=>String(row[i])!==h)) throw Error('Несовместимая схема снимков операций');
    return existing;
  }
  return tab_('Снимки операций',headers);
}
function resolveLegacyTaskBinding_(message) {
  const chatId=String(message.chat.id),messageId=String(message.message_id),owner=isOwner_(chatId);
  if(!/^-?[0-9]{1,24}$/.test(chatId)||!/^[0-9]{1,24}$/.test(messageId)) throw Error('Некорректный ключ сообщения');
  const key='LEGACY-TASK-BIND:'+chatId+':'+messageId;
  const sheet=legacyBindingSnapshots_(),existing=sheet.getDataRange().getValues().slice(1).some(r=>String(r[0])===key);
  let binding;
  if(existing) binding=operationSnapshot_(key);
  else {
    legacyBindingAttemptSafe_(chatId,messageId);
    let decision='UNLINKED',task=null;
    const chosen=prop_('SELECTED_TASK_'+chatId);
    if(chosen) {
      let selected=null;
      try { selected=JSON.parse(chosen); } catch(error) {}
      if(selected&&typeof selected==='object'&&selected.version===1&&selected.chat_id===chatId&&Object.keys(selected).sort().join('|')==='chat_id|task_id|version')
        task=legacyTaskForId_(chatId,selected.task_id);
      decision=task?'BOUND':'RESELECT';
    } else if(!owner) {
      const active=activeTasks_(chatId).filter(t=>['Отправлено','В работе','Доработка'].includes(String(t.row[5])));
      if(active.length===1) { task=legacyTaskForId_(chatId,String(active[0].row[0]||''));decision=task?'BOUND':'RESELECT'; }
    }
    binding=operationSnapshot_(key,{version:1,chat_id:chatId,message_id:messageId,owner,decision,task_id:task?String(task.row[0]):null});
  }
  if(!binding||typeof binding!=='object'||binding.version!==1||binding.chat_id!==chatId||binding.message_id!==messageId||binding.owner!==owner||Object.keys(binding).sort().join('|')!=='chat_id|decision|message_id|owner|task_id|version'||!['BOUND','UNLINKED','RESELECT'].includes(binding.decision))
    throw Error('Снимок привязки сообщения требует сверки');
  if(binding.decision!=='BOUND') {
    if(binding.task_id!==null) throw Error('Некорректный снимок привязки');
    return {decision:binding.decision,task:null};
  }
  const task=legacyTaskForId_(chatId,binding.task_id);
  if(!task) throw Error('Сохранённая привязка требует сверки: другое поручение не выбирается');
  return {decision:'BOUND',task};
}
function clearLegacyTaskSelection_(chatId,taskId) {
  const key='SELECTED_TASK_'+String(chatId);
  let selected=null;
  try { selected=JSON.parse(prop_(key)||'null'); } catch(error) {}
  if(selected&&selected.version===1&&selected.chat_id===String(chatId)&&selected.task_id===String(taskId)&&Object.keys(selected).sort().join('|')==='chat_id|task_id|version')
    PropertiesService.getScriptProperties().deleteProperty(key);
}
`+snapshot+String.raw`function legacyBindingAttemptSafe_(chatId,messageId) {
  const queue=ss_().getSheetByName('Очередь updates');
  if(!queue) return; // Offline/direct calls are not a supported production entry point.
  const queued=queue.getDataRange().getValues().slice(1);
  const matches=queued.filter(row=>{
    try { const update=JSON.parse(String(row[3]));return update.message&&String(update.message.chat.id)===chatId&&String(update.message.message_id)===messageId; }
    catch(error) { return false; }
  });
  if(matches.length!==1||Number(matches[0][2])!==1||matches[0][1]!=='PROCESSING'||String(matches[0][5]||'')!=='')
    throw Error('Первичная привязка не подтверждена; требуется сверка, а не новый выбор');
  const currentId=JSON.parse(String(matches[0][3])).update_id;
  let latest=null;
  for(const row of queued) {
    let update;
    try { update=JSON.parse(String(row[3])); } catch(error) { continue; }
    const q=update.callback_query;
    if(Number.isSafeInteger(update.update_id)&&update.update_id<currentId&&q&&q.from&&q.message&&q.message.chat&&q.message.chat.type==='private'&&String(q.message.chat.id)===chatId&&String(q.from.id)===chatId&&/^(taskid:|task:)/.test(String(q.data||''))&&(!latest||update.update_id>latest.id))
      latest={id:update.update_id,status:String(row[1])};
  }
  if(latest&&latest.status!=='DONE') throw Error('Последний выбор поручения не подтверждён; требуется сверка');
}
function legacyReplayBindingGuard_(update) {
  const message=update&&update.message;
  if(!message||!message.chat||message.chat.type!=='private'||/^\/\w+/.test(message.text||message.caption||'')) return;
  const chatId=String(message.chat.id),messageId=String(message.message_id);
  const present=name=>rows_(name,name==='Ответы'?CFG.replyHeaders:['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл'])
    .slice(1).some(r=>String(r[3])===chatId&&String(r[6])===messageId);
  if(present('Ответы')||present('Входящие')) return;
  const sheet=ss_().getSheetByName('Снимки операций'),key='LEGACY-TASK-BIND:'+chatId+':'+messageId;
  if(!sheet||!sheet.getDataRange().getValues().slice(1).some(r=>String(r[0])===key))
    throw Error('Повтор без подтверждённого снимка привязки запрещён; требуется ручная сверка');
  operationSnapshot_(key); // Reject duplicate/corrupt snapshots without inventing a choice.
}
`;
const start=base.indexOf("  const replies=tab_('Ответы'");
const end=base.indexOf('  if(isOwner_(chatId) && !task)',start);
const oldSelection=base.slice(start,end);
const selection=`  const resolved=resolveLegacyTaskBinding_(m);
  if(resolved.decision==='RESELECT') {
    send_(chatId,'Выбор поручения устарел. Откройте /tasks, выберите поручение заново и отправьте ответ новым сообщением.');
    return;
  }
  const taskId=resolved.task?String(resolved.task.row[0]):'';
  const replies=tab_('Ответы',CFG.replyHeaders);
  const stored=storeFile_(m);
  let task=taskId?legacyTaskForId_(chatId,taskId):null;
  if(taskId&&!task) throw Error('Поручение изменилось при сохранении файла; требуется сверка');
`;
const recovery=extract(base,'recoverLegacyReply_');
const nextRecovery=recovery.replace("  const key='SELECTED_TASK_'+String(chatId);\n  if(prop_(key)===String(item.index)) PropertiesService.getScriptProperties().deleteProperty(key);","  clearLegacyTaskSelection_(chatId,linkedId);");
const replay=extract(base,'replayDeadUpdate_');
const nextReplay=replay.replace("    sheet.getRange(item.index,3).setValue(0);","    legacyReplayBindingGuard_(update);\n    sheet.getRange(item.index,3).setValue(0);");
const pairs=[['taskKeyboard_',keyboard],['chooseTask_',choose],['processCallback_',callback]].map(([n,value])=>[extract(base,n),value]);
pairs.push(["  if(task) {\n    const s=tab_('Поручения',CFG.taskHeaders);","  if(taskId) {\n    const s=tab_('Поручения',CFG.taskHeaders);\n    task=legacyTaskForId_(chatId,taskId);\n    if(!task) throw Error('Поручение изменилось после записи ответа; требуется сверка');"],[replay,nextReplay],[oldSelection,selection],[recovery,nextRecovery],["    PropertiesService.getScriptProperties().deleteProperty('SELECTED_TASK_'+chatId);","    clearLegacyTaskSelection_(chatId,taskId);"]);
function patchTaskBinding(source){
 const names=[...helper.matchAll(/^function\s+(\w+)\(/gm)].map(m=>m[1]);
 if(typeof source!=='string'||names.some(n=>source.includes('function '+n+'('))||pairs.some(([old])=>!old||source.split(old).length!==2))throw Error('Reviewed task binding precondition mismatch');
 let next=source;for(const [old,value] of pairs)next=next.replace(old,value);
 return next.replace('function processCallback_(',helper+'function processCallback_(');
}
module.exports={patchTaskBinding};
