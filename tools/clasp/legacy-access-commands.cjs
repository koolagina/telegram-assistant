'use strict';
/** Offline candidate only: freezes command identity and never replays an uncertain rights mutation. */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const begin=archive.indexOf('function ownerApprove_('),end=archive.indexOf('function ownerAdd_(',begin);
const original=archive.slice(begin,end).replace('.setValue(name)','.setValue(legacySheetLiteral_(name))');
const replacement=String.raw`function ownerApprove_(id,raw,messageId) {
  if(!isOwner_(id))throw Error('Требуются права владельца');
  const match=raw.replace(/^\/approve(?:\s+|$)/,'').trim().match(/^(\S+)\s+(.+)$/);
  if(!match)return send_(id,'Формат: /approve CHAT_ID Имя Фамилия');
  return legacyAccessCommand_(id,messageId,'approve',match[1],match[2].trim());
}
function ownerRevoke_(id,raw,messageId) {
  if(!isOwner_(id))throw Error('Требуются права владельца');
  const target=raw.replace(/^\/revoke(?:\s+|$)/,'').trim();
  if(!target)return send_(id,'Формат: /revoke CHAT_ID');
  return legacyAccessCommand_(id,messageId,'revoke',target,'');
}
function legacyAccessCommand_(owner,messageId,action,target,name) {
  if(!isOwner_(owner)||!['approve','revoke'].includes(action))throw Error('Требуются права владельца');
  const source=String(owner),message=String(messageId);
  if(![source,message,target].every(v=>/^[1-9][0-9]{0,23}$/.test(v)&&Number.isSafeInteger(Number(v))))throw Error('Некорректный ключ команды доступа');
  if(isOwner_(target))return send_(owner,action==='approve'?'Владелец уже имеет доступ.':'Нельзя отключить доступ владельцу.');
  return withScriptLock_(()=>{
    const sheet=tab_('Студенты',CFG.studentHeaders),snapshots=legacyBindingSnapshots_();
    const find=()=>sheet.getDataRange().getValues().slice(1).map((row,i)=>({row,index:i+2})).filter(x=>String(x.row[3])===target);
    let matches=find();
    if(matches.length>1)throw Error('Неоднозначный студент; требуется сверка');
    if(!matches.length)return send_(owner,'Пользователь с таким chat ID не найден. Пусть он сначала напишет боту /start.');
    const key='LEGACY-ACCESS:'+source+':'+message,request={action,target,name};
    const exists=k=>snapshots.getDataRange().getValues().slice(1).some(r=>String(r[0])===k);
    if(exists(key)){
      const plan=operationSnapshot_(key);
      if(!plan||plan.version!==1||JSON.stringify(plan.request)!==JSON.stringify(request))throw Error('Команда доступа изменилась; требуется сверка');
      if(!exists(key+':APPLIED'))throw Error('Незавершённая команда доступа; требуется сверка');
      const applied=operationSnapshot_(key+':APPLIED');
      if(!applied||applied.version!==1||JSON.stringify(applied.request)!==JSON.stringify(request))throw Error('Квитанция доступа требует сверки');
      return send_(owner,'Эта команда уже обработана. Текущее состояние: '+String(matches[0].row[5]));
    }
    if([':APPLIED',':NOTIFY_CLAIM',':NOTIFY_ACK'].some(suffix=>exists(key+suffix)))throw Error('Неполная история команды; требуется сверка');
    const queue=ss_().getSheetByName('Очередь updates');
    if(queue){
      const items=queue.getDataRange().getValues().slice(1).filter(row=>{
        try{const u=JSON.parse(String(row[3]));return u.message&&String(u.message.chat.id)===source&&String(u.message.message_id)===message;}catch(error){return false;}
      });
      if(items.length!==1||items[0][1]!=='PROCESSING'||Number(items[0][2])!==1||String(items[0][5]||'')!=='')throw Error('Первичная команда не подтверждена; требуется сверка');
    }
    for(const row of snapshots.getDataRange().getValues().slice(1)){
      const match=String(row[0]).match(/^LEGACY-ACCESS:([0-9]+):([0-9]+)$/);
      if(!match||match[1]!==source)continue;
      let prior;try{prior=JSON.parse(String(row[1]));}catch(error){throw Error('История доступа требует сверки');}
      if(!prior||prior.version!==1||!prior.request)throw Error('История доступа требует сверки');
      if(prior.request.target===target&&Number(match[2])>Number(message))throw Error('Есть более новая команда доступа; требуется сверка');
    }
    const before={name:String(matches[0].row[0]||''),status:String(matches[0].row[5]||'')};
    operationSnapshot_(key,{version:1,request,before});
    // Re-resolve after persistence; do not mutate a different student after a sort.
    matches=find();
    if(matches.length!==1||String(matches[0].row[0]||'')!==before.name||String(matches[0].row[5]||'')!==before.status)throw Error('Строка студента изменилась; требуется сверка');
    const index=matches[0].index;
    if(action==='approve')sheet.getRange(index,1).setValue(legacySheetLiteral_(name));
    sheet.getRange(index,6).setValue(action==='approve'?'Одобрен':'Доступ отключён');
    SpreadsheetApp.flush();
    operationSnapshot_(key+':APPLIED',{version:1,request});
    let apiConfirmed=false;
    try{
      operationSnapshot_(key+':NOTIFY_CLAIM',{version:1,target,status:'SENDING'});
      const result=send_(target,action==='approve'?'Доступ к помощнику подтверждён. Для списка поручений отправьте /tasks.':'Доступ к помощнику отключён.');
      if(!result||!Number.isSafeInteger(result.message_id)||result.message_id<=0||(result.chat&&String(result.chat.id)!==target))throw Error('Unverified API result');
      operationSnapshot_(key+':NOTIFY_ACK',{version:1,target,status:'API_CONFIRMED',message_id:result.message_id});
      apiConfirmed=true;
    }catch(error){} // Unknown student notification is never retried by this command.
    return send_(owner,(action==='approve'?'Доступ разрешён: '+name:'Доступ отключён')+' ('+target+'). '+
      (apiConfirmed?'Telegram API подтвердил уведомление; доставка неизвестна.':'Исход уведомления не подтверждён; автоматический повтор запрещён.'));
  });
}
`;
const replayOld='function legacyReplayBindingGuard_(update) {\n';
const replayNew=String.raw`function legacyReplayBindingGuard_(update) {
  const accessMessage=update&&update.message;
  if(accessMessage&&accessMessage.chat&&accessMessage.chat.type==='private'&&isOwner_(accessMessage.chat.id)&&/^\/(?:approve|revoke)(?:\s|$)/.test(accessMessage.text||'')){
    const sheet=ss_().getSheetByName('Снимки операций'),key='LEGACY-ACCESS:'+accessMessage.chat.id+':'+accessMessage.message_id;
    if(!sheet||!sheet.getDataRange().getValues().slice(1).some(row=>String(row[0])===key))throw Error('Нет исходного плана команды доступа; требуется сверка');
  }
`;
const pairs=[[original,replacement],[replayOld,replayNew],['return ownerApprove_(chatId,raw);','return ownerApprove_(chatId,raw,m.message_id);'],['return ownerRevoke_(chatId,raw);','return ownerRevoke_(chatId,raw,m.message_id);']];
function patchAccessCommands(source){
 for(const [old,next]of pairs){if(source.split(old).length!==2)throw Error('Reviewed access command precondition mismatch');source=source.replace(old,next);}
 return source;
}
function restoreAccessCommands(source){
 for(const [old,next]of pairs.slice().reverse()){if(source.split(next).length!==2)throw Error('Exact access command patch required');source=source.replace(next,old);}
 return source;
}
module.exports={patchAccessCommands,restoreAccessCommands};
