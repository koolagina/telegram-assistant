'use strict';
/** Offline legacy reply-projection repair. No Sheets/Drive/Telegram calls from Node. */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const begin=archive.indexOf("  const alreadyInReplies=rows_('Ответы'");
const end=archive.indexOf("  const replies=tab_('Ответы'",begin);
const original=archive.slice(begin,end);
const replacement=`  const existingReplies=rows_('Ответы',CFG.replyHeaders).slice(1)
    .filter(r=>String(r[3])===chatId && String(r[6])===messageId);
  const alreadyInInbox=rows_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']).slice(1)
    .some(r=>String(r[3])===chatId && String(r[6])===messageId);
  if(existingReplies.length>1||(existingReplies.length && alreadyInInbox))
    throw Error('Неоднозначный сохранённый ответ: требуется сверка');
  if(existingReplies.length) { recoverLegacyReply_(chatId,existingReplies[0]); return; }
  if(alreadyInInbox) return;
`;
const helper=`function recoverLegacyReply_(chatId,reply) {
  // The saved reply, not the current task selection, binds a retry to a task.
  const linkedId=String(reply[7]||'');
  if(!linkedId) return;
  const sheet=tab_('Поручения',CFG.taskHeaders),rows=sheet.getDataRange().getValues();
  const matches=rows.slice(1).map((row,i)=>({row,index:i+2}))
    .filter(item=>String(item.row[0])===linkedId && String(item.row[9])===String(chatId));
  if(matches.length!==1) throw Error('Поручение сохранённого ответа требует сверки');
  const item=matches[0],row=item.row,status=String(row[5]);
  if(!['Отправлено','В работе','Доработка','Ответ получен'].includes(status)) return;
  const content=String(reply[5]||'['+reply[4]+']'),link=String(reply[8]||'');
  // Do not mix an older reply with a later response or a manual edit.
  if((row[7] && String(row[7])!==content)||(row[8] && link && String(row[8])!==link))
    throw Error('Данные поручения отличаются от сохранённого ответа: требуется сверка');
  if(!row[6] && (!(reply[0] instanceof Date)||isNaN(reply[0].getTime())))
    throw Error('Дата сохранённого ответа требует сверки');
  if(!row[6]) sheet.getRange(item.index,7).setValue(reply[0]);
  if(!row[7]) sheet.getRange(item.index,8).setValue(content);
  if(!row[8] && link) sheet.getRange(item.index,9).setValue(link);
  if(status!=='Ответ получен') sheet.getRange(item.index,6).setValue('Ответ получен');
  const key='SELECTED_TASK_'+String(chatId);
  if(prop_(key)===String(item.index)) PropertiesService.getScriptProperties().deleteProperty(key);
}
`;
function patchReplyRecovery(source){
 if(typeof source!=='string'||source.split(original).length!==2||source.includes('function recoverLegacyReply_(')||source.split('function processCallback_(').length!==2)
  throw Error('Reviewed legacy reply precondition mismatch');
 return source.replace(original,replacement).replace('function processCallback_(',helper+'function processCallback_(');
}
function restoreReplyRecovery(source){
 if(typeof source!=='string'||source.split(replacement).length!==2||source.split(helper).length!==2)throw Error('Exact reply patch required');
 return source.replace(helper,'').replace(replacement,original);
}
module.exports={patchReplyRecovery,restoreReplyRecovery};
