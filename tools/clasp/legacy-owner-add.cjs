'use strict';
/** Offline narrow backport of the candidate's Telegram-derived personal-task ID.
 * No general registry migration or live source update.
 */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const begin=archive.indexOf('function ownerAdd_('),end=archive.indexOf('function ownerDone_(',begin);
const original=archive.slice(begin,end).replace("sheet.appendRow([key,'Личное',text,","sheet.appendRow([key,'Личное',legacySheetLiteral_(text),");
const replacement=String.raw`function ownerAdd_(id,raw,messageId) {
  if(!isOwner_(id))throw Error('Требуются права владельца');
  const text=raw.replace(/^\/add(?:\s+|$)/,'').trim();
  if(!text)return send_(id,'Напишите: /add Купить корм Уле');
  const chat=String(id),message=String(messageId);
  if(!/^[1-9][0-9]{0,23}$/.test(chat)||!Number.isSafeInteger(Number(chat))||!Number.isSafeInteger(Number(message))||!/^[1-9][0-9]{0,23}$/.test(message))
    throw Error('Для добавления задачи требуется исходное Telegram сообщение');
  return withScriptLock_(()=>{
    const sheet=tab_('Личные задачи',CFG.personalHeaders),key='L-TG-'+chat+'-'+message;
    const matches=sheet.getDataRange().getValues().slice(1).filter(row=>String(row[0])===key);
    if(matches.length>1)throw Error('Дубликат ID личной задачи; требуется сверка');
    if(matches.length){
      if(String(matches[0][2])!==text)throw Error('Текст личной задачи отличается; требуется сверка');
      return send_(id,'Эта задача уже записана: '+key+' — '+text);
    }
    appendOnce_(sheet,[key,'Личное',legacySheetLiteral_(text),'','Открыто','Обычный','',new Date()]);
    return send_(id,'Добавила задачу '+key+': '+text);
  });
}
`;
const dispatch=['return ownerAdd_(chatId,raw);','return ownerAdd_(chatId,raw,m.message_id);'];
function patchOwnerAdd(source){
 if(typeof source!=='string'||source.split(original).length!==2||source.split(dispatch[0]).length!==2)throw Error('Reviewed owner add precondition mismatch');
 return source.replace(original,replacement).replace(...dispatch);
}
function restoreOwnerAdd(source){
 if(typeof source!=='string'||source.split(replacement).length!==2||source.split(dispatch[1]).length!==2)throw Error('Exact owner add patch required');
 return source.replace(replacement,original).replace(dispatch[1],dispatch[0]);
}
module.exports={patchOwnerAdd,restoreOwnerAdd};
