'use strict';
/** Offline candidate: task API receipt and recoverable Sheets projection, not delivery proof. */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const start=archive.indexOf('function sendPendingTasks('),end=archive.indexOf('function dateKey_(',start);
const original=archive.slice(start,end).replace("log_('Не найден адресат',i+1,r[1]);","log_('Не найден адресат',i+1,'Проверьте справочник');");
// Installed access/ACK patch does not necessarily replace the old diagnostic text.
const rawOriginal=archive.slice(start,end);
const replacement=String.raw`function sendPendingTasks() {
  const lock=LockService.getScriptLock();if(!lock.tryLock(1000))return;
  try{
    const sheet=tab_('Поручения',CFG.taskHeaders),rows=sheet.getDataRange().getValues();
    for(let i=1;i<rows.length;i++){
      const row=rows[i];
      if(!['Не отправлено','Отправляется','Ошибка отправки','Отправлено'].includes(String(row[5])))continue;
      if(!row[1]||!row[2])continue;
      if(row[5]==='Отправлено'&&row[3]&&row[9])continue; // No per-task receipt reads for completed sends.
      let id=String(row[0]||'').trim();
      try{
        if(!id){
          if(row[5]!=='Не отправлено')continue;
          const current=sheet.getRange(i+1,1,1,CFG.taskHeaders.length).getValues()[0];
          if(JSON.stringify(current)!==JSON.stringify(row))throw Error('Task changed before ID assignment');
          id='T-'+Utilities.getUuid();sheet.getRange(i+1,1).setValue(id);SpreadsheetApp.flush();
        }
        dispatchLegacyTask_(id);
      }catch(error){log_('Требуется сверка отправки',id,'Не удалось безопасно завершить отправку; автоматический повтор неизвестного API запрещён');}
    }
  }finally{lock.releaseLock();}
}
function legacyTaskDispatchSnapshot_(key,value) {
  const sheet=legacyBindingSnapshots_();
  if(value!==undefined)return operationSnapshot_(key,value);
  const rows=sheet.getDataRange().getValues().slice(1).filter(row=>String(row[0])===key);
  if(!rows.length)return null;
  if(rows.length!==1)throw Error('Ambiguous task dispatch receipt');
  return operationSnapshot_(key);
}
function dispatchLegacyTask_(id) {
  return withScriptLock_(()=>{
    if(!validLegacyTaskId_(id))throw Error('Invalid task ID');
    const sheet=tab_('Поручения',CFG.taskHeaders);
    const resolve=()=>{
      const matches=sheet.getDataRange().getValues().slice(1).map((row,i)=>({row,index:i+2})).filter(x=>String(x.row[0])===id);
      if(matches.length!==1)throw Error('Ambiguous task ID');return matches[0];
    };
    let item=resolve(),row=item.row;
    if(!['Не отправлено','Отправляется','Ошибка отправки','Отправлено'].includes(String(row[5])))return;
    const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(s=>String(s[0]||'').trim().toLowerCase()===String(row[1]).trim().toLowerCase());
    if(students.length!==1)throw Error('Ambiguous student');
    const target=String(students[0][3]||'');
    if(!/^[1-9][0-9]{0,23}$/.test(target)||(!isOwner_(target)&&accessStatus_(target)!=='approved'))throw Error('Access not approved');
    if(row[9]&&String(row[9])!==target)throw Error('Task recipient changed');
    const due=r=>r[4]?(r[4] instanceof Date?Utilities.formatDate(r[4],CFG.timezone,'dd.MM.yyyy'):String(r[4])):'не указан';
    const proof=r=>[String(r[1]),String(r[2]),due(r)];
    const expected={version:1,task_id:id,target,proof:proof(row),text:('Новое поручение № '+id+'\n\n'+row[2]+'\n\nСрок: '+due(row)+'\n\nДля ответа нажмите /tasks.').slice(0,4000)};
    const key='LEGACY-TASK-DISPATCH:'+id;
    let plan=legacyTaskDispatchSnapshot_(key),ack=legacyTaskDispatchSnapshot_(key+':ACK'),claim=legacyTaskDispatchSnapshot_(key+':CLAIM');
    if(!plan){
      if(ack||claim)throw Error('Orphan dispatch receipt');
      if(row[5]!=='Не отправлено')return; // No blind migration/retry of old uncertain sends.
      plan=legacyTaskDispatchSnapshot_(key,expected);
    }
    if(JSON.stringify(plan)!==JSON.stringify(expected))throw Error('Task dispatch plan changed');
    const planJson=JSON.stringify(plan);
    if(claim&&(!claim||claim.version!==1||claim.plan_json!==planJson))throw Error('Dispatch claim changed');
    const current=()=>{
      const next=resolve();
      if(JSON.stringify(proof(next.row))!==JSON.stringify(plan.proof)||(next.row[9]&&String(next.row[9])!==target))throw Error('Task changed during dispatch');
      if(!['Не отправлено','Отправляется','Ошибка отправки','Отправлено'].includes(String(next.row[5])))throw Error('Task status changed');
      return next;
    };
    if(!ack){
      if(claim)throw Error('Unknown Telegram outcome; do not resend');
      if(!['Не отправлено','Отправляется'].includes(String(row[5])))throw Error('Unverified previous send');
      item=current();sheet.getRange(item.index,10).setValue(target);
      item=current();sheet.getRange(item.index,6).setValue('Отправляется');SpreadsheetApp.flush();
      const intent={version:1,plan_json:planJson};
      const savedClaim=legacyTaskDispatchSnapshot_(key+':CLAIM',intent);
      if(JSON.stringify(savedClaim)!==JSON.stringify(intent))throw Error('Dispatch claim changed');
      const result=send_(target,plan.text);
      if(!result||!Number.isSafeInteger(result.message_id)||result.message_id<=0||(result.chat&&String(result.chat.id)!==target))throw Error('Unverified API result');
      ack=legacyTaskDispatchSnapshot_(key+':ACK',{version:1,plan_json:planJson,api_message_id:result.message_id,sent_at:new Date().toISOString()});
    }
    if(!claim)claim=legacyTaskDispatchSnapshot_(key+':CLAIM');
    if(!claim||claim.version!==1||claim.plan_json!==planJson||!ack||ack.version!==1||ack.plan_json!==planJson||!Number.isSafeInteger(ack.api_message_id)||ack.api_message_id<=0||typeof ack.sent_at!=='string'||isNaN(new Date(ack.sent_at).getTime()))throw Error('Invalid API receipt');
    item=current();row=item.row;
    const sentAt=new Date(ack.sent_at);
    if(row[3]&&(!(row[3] instanceof Date)||row[3].getTime()!==sentAt.getTime()))throw Error('Dispatch date changed manually');
    if(!row[9]){item=current();sheet.getRange(item.index,10).setValue(target);}
    if(!row[3]){item=current();sheet.getRange(item.index,4).setValue(sentAt);}
    item=current();if(item.row[5]!=='Отправлено')sheet.getRange(item.index,6).setValue('Отправлено');
    SpreadsheetApp.flush();
  });
}
`;
function patchTaskDispatch(source){
 const base=source.includes(rawOriginal)?rawOriginal:original;
 if(source.split(base).length!==2||source.includes('function dispatchLegacyTask_('))throw Error('Reviewed task dispatch precondition mismatch');
 return source.replace(base,replacement);
}
module.exports={patchTaskDispatch};
