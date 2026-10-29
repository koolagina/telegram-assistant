'use strict';
/** Offline narrow backport of the existing 2.0.5 durable inbox. Never runs Apps Script. */
const fs=require('node:fs'),path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../../src',name),'utf8');
const legacy=read('archive/telegram_assistant_v1_4_3_reference.gs'),current=read('telegram_assistant_v2_0_5_candidate.gs');
function extract(source,name){const start=source.indexOf('function '+name+'(');if(start<0)throw Error('Missing reviewed function');const next=source.indexOf('\nfunction ',start+1);return source.slice(start,next<0?source.length:next).trimEnd()+'\n';}
const original=extract(legacy,'pollTelegramUpdates');
const names=['withScriptLock_','appendOnce_','updateInbox_','inboxItem_','processInboxItem_','replayDeadUpdate_'];
const helper=names.map(n=>{
 let code=extract(current,n);
 if(n==='processInboxItem_'){
  code=code.replaceAll('CFG.maxUpdateRetries','3');
  code=code.replace('  const update=JSON.parse(String(item.row[3]));',"  const update=JSON.parse(String(item.row[3]));\n  if(!update||!Number.isSafeInteger(update.update_id)||update.update_id<0||String(item.row[0])!=='U-'+update.update_id)\n    throw Error('Payload очереди не соответствует ключу');");
 }
 if(n==='updateInbox_')code=`function updateInbox_() {
  const headers=['Ключ','Статус','Попытки','Payload JSON','Обновлено','Ошибка'];
  const existing=ss_().getSheetByName('Очередь updates');
  if(existing) {
    const row=existing.getRange(1,1,1,headers.length).getValues()[0];
    if(existing.getLastRow()<1||headers.some((h,i)=>String(row[i])!==h))
      throw Error('Несовместимая схема очереди updates');
    return existing;
  }
  return tab_('Очередь updates',headers);
}
`;
 return code;
}).join('\n');
const replacement=extract(current,'pollTelegramUpdates')+'\n'+helper;
function patchUpdateQueue(source){
 if(typeof source!=='string'||source.split(original).length!==2||names.some(n=>source.includes('function '+n+'(')))throw Error('Reviewed legacy queue precondition mismatch');
 return source.replace(original,replacement);
}
module.exports={patchUpdateQueue};
