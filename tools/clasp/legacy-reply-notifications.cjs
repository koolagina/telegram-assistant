'use strict';
/** Offline candidate. New technical outbox requires separate live authorization. */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const start=archive.indexOf("  send_(chatId,task?'Ответ сохранён");
const end=archive.indexOf('\n}',start);
const oldSends=archive.slice(start,end);
const helpers=String.raw`
function prepareKulaginaReplyNotifications() {
  return withScriptLock_(()=>{
    const existed=!!ss_().getSheetByName('Уведомления ответов');
    legacyReplyNotificationSheet_();SpreadsheetApp.flush();
    const report={status:'reply_notifications_ready',created:!existed,columns:6,business_writes:0,messages_sent:0,polling_started:false};
    console.log(JSON.stringify(report));return report;
  });
}
function legacyReplyNotificationSheet_() {
  const headers=['Ключ','Payload JSON','Статус','Telegram message ID','Обновлено','Ошибка'];
  const existing=ss_().getSheetByName('Уведомления ответов');
  if(existing){
    const h=existing.getRange(1,1,1,headers.length).getValues()[0];
    if(existing.getLastRow()<1||headers.some((v,i)=>String(h[i])!==v))throw Error('Несовместимая схема уведомлений');
    return existing;
  }
  return tab_('Уведомления ответов',headers);
}
function prepareLegacyReplyNotifications_(chatId,messageId,name,taskId,stored,inbox) {
  return withScriptLock_(()=>{
    const owner=isOwner_(chatId),proof=[String(name),String(stored.type),String(stored.description||''),String(taskId||''),String(stored.link||'')];
    const items=inbox?[{role:'inbox',target:String(chatId),text:'Сообщение сохранено в личных входящих.'}]:[
      {role:'student',target:String(chatId),text:taskId?'Ответ сохранён по поручению '+taskId+'. Ожидайте проверки.':'Сообщение сохранено. Чтобы связать ответ с заданием, используйте /tasks.'},
      ...(!owner?[{role:'owner',target:String(owner_()),text:'Новый ответ от '+name+(taskId?' по '+taskId:' (без привязки к заданию)')+': '+(stored.description||'['+stored.type+']').slice(0,400)+(stored.link?'\nФайл: '+stored.link:'')}]:[])
    ];
    const sh=legacyReplyNotificationSheet_();
    for(const item of items){
      if(!/^[1-9][0-9]{0,23}$/.test(item.target))throw Error('Адресат уведомления требует сверки');
      const key='REPLY-NOTIFY:'+chatId+':'+messageId+':'+item.role;
      const payload=JSON.stringify({version:1,chat_id:String(chatId),message_id:String(messageId),role:item.role,target:item.target,text:String(item.text).slice(0,4000),proof});
      const row=appendOnce_(sh,[key,payload,'PREPARED','',new Date(),'']);
      if(row[1]!==payload)throw Error('План уведомления отличается; требуется сверка');
    }
  });
}
function flushLegacyReplyNotifications_(chatId,messageId) {
  return withScriptLock_(()=>{
    const sh=legacyReplyNotificationSheet_(),prefix='REPLY-NOTIFY:'+chatId+':'+messageId+':';
    const rows=sh.getDataRange().getValues().slice(1).map((row,i)=>({row,index:i+2})).filter(x=>String(x.row[0]).startsWith(prefix));
    if(!rows.length)return {status:'historical_no_plan',delivered:null};
    const roles=new Set(),validated=[];let unknown=false;
    for(const item of rows){
      const row=item.row;let p;
      try{p=JSON.parse(String(row[1]));}catch(error){throw Error('План уведомления повреждён');}
      if(!p||p.version!==1||p.chat_id!==String(chatId)||p.message_id!==String(messageId)||!['student','owner','inbox'].includes(p.role)||roles.has(p.role)||row[0]!==prefix+p.role||typeof p.text!=='string'||p.text.length>4000||!Array.isArray(p.proof)||p.proof.length!==5)throw Error('Неоднозначный план уведомления');
      roles.add(p.role);
      if(p.target!==(p.role==='owner'?String(owner_()):String(chatId)))throw Error('Адресат изменился; требуется сверка');
      const replies=rows_('Ответы',CFG.replyHeaders).slice(1).filter(r=>String(r[3])===String(chatId)&&String(r[6])===String(messageId));
      const incoming=rows_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']).slice(1).filter(r=>String(r[3])===String(chatId)&&String(r[6])===String(messageId));
      const saved=p.role==='inbox'?incoming:replies;
      if(saved.length!==1||(p.role==='inbox'?replies.length:incoming.length))throw Error('Сохранённый ответ требует сверки');
      const r=saved[0],proof=[String(r[1]),String(r[4]),String(r[5]||''),p.role==='inbox'?'':String(r[7]||''),String(r[p.role==='inbox'?7:8]||'')];
      if(JSON.stringify(proof)!==JSON.stringify(p.proof))throw Error('Содержимое ответа изменилось; требуется сверка');
      validated.push({item,p});
    }
    const expected=roles.has('inbox')?['inbox']:(isOwner_(chatId)?['student']:['student','owner']);
    if(roles.size!==expected.length||expected.some(role=>!roles.has(role)))throw Error('Неполный план уведомлений');
    for(const {item,p} of validated){
      const row=item.row;
      if(row[2]==='API_CONFIRMED'){
        if(!Number.isSafeInteger(Number(row[3]))||Number(row[3])<=0)throw Error('Подтверждение API требует сверки');
        continue;
      }
      if(row[2]==='SENDING'||row[2]==='UNKNOWN'){unknown=true;continue;}
      if(row[2]!=='PREPARED'||row[3])throw Error('Статус уведомления требует сверки');
      try{
        sh.getRange(item.index,3).setValue('SENDING');SpreadsheetApp.flush();
        const result=send_(p.target,p.text);
        if(!result||!Number.isSafeInteger(result.message_id)||result.message_id<=0||(result.chat&&String(result.chat.id)!==p.target))throw Error('Unknown API result');
        sh.getRange(item.index,4).setValue(result.message_id);
        sh.getRange(item.index,5).setValue(new Date());
        sh.getRange(item.index,3).setValue('API_CONFIRMED');SpreadsheetApp.flush();
      }catch(error){
        unknown=true;
        try{sh.getRange(item.index,3).setValue('UNKNOWN');sh.getRange(item.index,6).setValue('REVIEW_REQUIRED');SpreadsheetApp.flush();}catch(ignored){}
      }
    }
    if(unknown)throw Error('Исход уведомления неизвестен; автоматический повтор запрещён');
    return {status:'api_confirmed',delivered:null};
  });
}
`;
const pairs=[
 ["recoverLegacyReply_(chatId,existingReplies[0]); return;","recoverLegacyReply_(chatId,existingReplies[0]); flushLegacyReplyNotifications_(chatId,messageId); return;"],
 ["if(alreadyInInbox) return;","if(alreadyInInbox) { flushLegacyReplyNotifications_(chatId,messageId); return; }"],
 ["    incoming.appendRow(","    prepareLegacyReplyNotifications_(chatId,messageId,name,'',stored,true);\n    incoming.appendRow("],
 ["    send_(chatId,'Сообщение сохранено в личных входящих.');","    flushLegacyReplyNotifications_(chatId,messageId);"],
 ["  replies.appendRow(","  prepareLegacyReplyNotifications_(chatId,messageId,name,taskId,stored,false);\n  replies.appendRow("],
 [oldSends,'  // Dispatch the complete prepared reply plan.\n  flushLegacyReplyNotifications_(chatId,messageId);']
];
function patchReplyNotifications(source){
 if(source.includes('function legacyReplyNotificationSheet_('))throw Error('Already patched');
 for(const [old,next]of pairs){if(!old||source.split(old).length!==2)throw Error('Reviewed notification precondition mismatch');source=source.replace(old,next);}
 return source+helpers;
}
function restoreReplyNotifications(source){
 if(typeof source!=='string'||!source.endsWith(helpers))throw Error('Exact notification patch required');
 let before=source.slice(0,-helpers.length);
 for(const [old,next] of pairs.slice().reverse()){
  if(before.split(next).length!==2)throw Error('Exact notification patch required');
  before=before.replace(next,old);
 }
 if(patchReplyNotifications(before)!==source)throw Error('Exact notification patch required');
 return before;
}
module.exports={patchReplyNotifications,restoreReplyNotifications};
