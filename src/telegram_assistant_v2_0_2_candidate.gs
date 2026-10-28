/**
 * Личный помощник Кулагиной Л. С. — Google Apps Script
 * Кандидат версии 2.0.2. Новые модули расписания, консультаций, справки и общего реестра; уточнён парсинг повторяющихся поручений и даты-времени.
 * Google Sheet: существующая таблица «Поручения студентам».
 *
 * В Script Properties сохранить:
 * TELEGRAM_BOT_TOKEN = токен от BotFather
 * OWNER_CHAT_ID = Telegram chat ID владелицы
 *
 * Новые Telegram-пользователи ожидают одобрения; /approve CHAT_ID Имя Фамилия разрешает доступ.
 * /revoke CHAT_ID отключает доступ. Личные сообщения владельца без выбранного задания записываются на лист «Входящие».
 * Повторяющиеся поручения задаются с разделителем: /repeat daily Имя Фамилия | текст задания.
 * Важно: при отправке в Telegram статус «Отправлено» означает
 * принятие сообщения сервером Telegram, а не прочтение человеком.
 */
const CFG = {
  spreadsheetId: '1UHFiOKoqX6ISD39X1B8ka-t8WYvPDYfxAweEvi2_Eeg',
  taskRegistrySpreadsheetId: '1dr1RWd9p-XG8cGXS5BbeB-JLOUCFbpclPZZs0ZbFgNE',
  timetableUrl: 'https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648',
  timetableCheckHour: 7,
  timetableCheckMinute: 30,
  timezone: 'Asia/Yekaterinburg',
  pollLimit: 50,
  maxUpdateRetries: 3,
  reminderDays: 1,
  maxFileBytes: 18 * 1024 * 1024,
  studentHeaders: ['Студент','Направление / проект','Telegram username','Telegram chat ID','Дата подключения','Примечания'],
  taskHeaders: ['ID поручения','Студент','Задание','Дата выдачи','Срок','Статус','Дата ответа','Ответ / комментарий','Ссылка на файл','Telegram chat ID','Последнее напоминание'],
  replyHeaders: ['Дата и время','Студент','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','ID поручения','Ссылка на файл'],
  personalHeaders: ['ID','Категория','Задача','Срок','Статус','Приоритет','Примечания','Создано'],
  logHeaders: ['Дата','Тип','Объект','Детали'],
  consultationHeaders: ['ID заявки','Дата создания','Студент','Telegram chat ID','Желаемая дата','Желаемое время','Длительность, мин','Тема','Статус','Решение / причина','ID события календаря'],
  timetableHeaders: ['Ключ','Значение','Обновлено'],
  broadcastHeaders: ['ID рассылки','Создано','Текст','Статус','Получателей','Подтверждено','Отправлено'],
  recurringHeaders: ['ID правила','Активно','Периодичность','День недели','Студент','Задание','Срок, дней после выдачи','Последняя выдача','Создано']
};
function prop_(key) { return PropertiesService.getScriptProperties().getProperty(key); }
function owner_() { const x=prop_('OWNER_CHAT_ID'); if(!x) throw Error('Задайте OWNER_CHAT_ID в свойствах скрипта'); return String(x); }
function token_() { const x=prop_('TELEGRAM_BOT_TOKEN'); if(!x) throw Error('Задайте TELEGRAM_BOT_TOKEN в свойствах скрипта'); return x; }
function ss_() { return SpreadsheetApp.openById(CFG.spreadsheetId); }
function tab_(name, headers) {
  const book=ss_(); let s=book.getSheetByName(name);
  if(!s) s=book.insertSheet(name);
  if(s.getLastRow()===0) { s.getRange(1,1,1,headers.length).setValues([headers]); s.setFrozenRows(1); }
  else {
    const existing=s.getRange(1,1,1,Math.max(headers.length,s.getLastColumn())).getValues()[0];
    headers.forEach((h,i)=>{ if(!existing[i]) s.getRange(1,i+1).setValue(h); });
  }
  return s;
}
function initialize() {
  tab_('Студенты',CFG.studentHeaders);
  tab_('Поручения',CFG.taskHeaders);
  tab_('Ответы',CFG.replyHeaders);
  tab_('Входящие', ['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']);
  tab_('Личные задачи',CFG.personalHeaders);
  tab_('Журнал бота',CFG.logHeaders);
  tab_('Заявки на консультации',CFG.consultationHeaders);
  tab_('Расписание НВГУ',CFG.timetableHeaders);
  tab_('Рассылки',CFG.broadcastHeaders);
  tab_('Повторяющиеся поручения',CFG.recurringHeaders);
  // Расширяем существующий выпадающий список статусов без удаления данных.
  const taskSheet=tab_('Поручения',CFG.taskHeaders);
  const statuses=['Не отправлено','Отправляется','Отправлено','В работе',
    'Ответ получен','На проверке','Доработка','Выполнено','Ошибка отправки','Отменено'];
  const rule=SpreadsheetApp.newDataValidation()
    .requireValueInList(statuses,true).setAllowInvalid(false).build();
  taskSheet.getRange(2,6,Math.max(1,taskSheet.getMaxRows()-1),1).setDataValidation(rule);
  const root=DriveApp.getRootFolder();
  const folderName='Файлы Telegram-помощника';
  const folders=DriveApp.getFoldersByName(folderName);
  if(!folders.hasNext()) root.createFolder(folderName);
}
function log_(type,object,details) {
  try { tab_('Журнал бота',CFG.logHeaders).appendRow([new Date(),type,String(object||''),String(details||'').slice(0,2000)]); }
  catch(e) { console.error(e); }
}
function tg_(method,payload) {
  const response=UrlFetchApp.fetch('https://api.telegram.org/bot'+token_()+'/'+method,{
    method:'post',contentType:'application/json',payload:JSON.stringify(payload||{}),muteHttpExceptions:true
  });
  let data; try { data=JSON.parse(response.getContentText()); }
  catch(e) { throw Error('Некорректный ответ Telegram: '+response.getResponseCode()); }
  if(!data.ok) throw Error(method+': '+(data.description||response.getResponseCode()));
  return data.result;
}
function send_(id,text,extra) {
  const body=Object.assign({chat_id:String(id),text:String(text).slice(0,4000)},extra||{});
  return tg_('sendMessage',body);
}
function rows_(name,headers) { return tab_(name,headers).getDataRange().getValues(); }
function findStudent_(chatId) {
  const rows=rows_('Студенты',CFG.studentHeaders);
  for(let i=1;i<rows.length;i++) if(String(rows[i][3])===String(chatId)) return {index:i+1,row:rows[i]};
  return null;
}
function register_(message) {
  const id=String(message.chat.id), from=message.from||{};
  const name=[from.first_name,from.last_name].filter(Boolean).join(' ')||'Неизвестный';
  const username=from.username||'';
  const sheet=tab_('Студенты',CFG.studentHeaders);
  const found=findStudent_(id);
  if(found) {
    // Не перезаписываем настоящее имя, назначенное вручную.
    if(String(found.row[2]||'')!==username) sheet.getRange(found.index,3).setValue(username);
    return found.row[0]||name;
  }
  sheet.appendRow([name,'',username,id,new Date(),'Новый контакт — требует проверки']);
  send_(owner_(),'Новый пользователь бота: '+name+' (@'+username+'), chat ID '+id+'. Проверьте имя в листе «Студенты».');
  return name;
}
function isOwner_(chatId) { return String(chatId)===owner_(); }
// Treat approval as an exact state, not a substring: 'не одобрен' must never grant access.
function isApprovedNote_(value) { return String(value||'').trim().toLowerCase()==='одобрен'; }
function accessStatus_(chatId) {
  if(isOwner_(chatId)) return 'owner';
  const found=findStudent_(chatId);
  if(!found) return 'unknown';
  const note=String(found.row[5]||'').toLowerCase();
  if(note.includes('доступ отключён')) return 'disabled';
  if(isApprovedNote_(note)) return 'approved';
  return 'pending';
}
function activeTasks_(chatId) {
  const rows=rows_('Поручения',CFG.taskHeaders), result=[];
  for(let i=1;i<rows.length;i++) {
    const r=rows[i];
    if(String(r[9])===String(chatId) && ['Отправлено','В работе','Доработка','Ответ получен','На проверке'].includes(String(r[5])))
      result.push({index:i+1,row:r});
  }
  return result;
}
function taskKeyboard_(chatId) {
  const active=activeTasks_(chatId).filter(t=>['Отправлено','В работе','Доработка'].includes(String(t.row[5])));
  return active.slice(0,20).map(t=>{
    const stableId=taskId_(t.row,t.index);
    const stableData='taskid:'+stableId;
    const callbackData=Utilities.newBlob(stableData).getBytes().length<=64 ? stableData : 'task:'+t.index;
    return [{text:String(t.row[0]||('Задание '+t.index)).slice(0,40),callback_data:callbackData}];
  });
}
function chooseTask_(chatId) {
  const buttons=taskKeyboard_(chatId);
  if(!buttons.length) return send_(chatId,'Активных поручений для ответа пока нет. Можете отправить обычное сообщение.');
  return send_(chatId,'Выберите поручение, на которое хотите ответить. Затем пришлите текст или файл:',{
    reply_markup:{inline_keyboard:buttons}
  });
}
function taskId_(row,index) { return String(row[0]||('строка-'+index)); }
function storeFile_(message) {
  const data=message.document||message.video||message.audio||message.voice||
    (message.photo&&message.photo[message.photo.length-1])||null;
  if(!data) return {type:'Текст',link:'',description:message.text||message.caption||''};
  const type=message.document?'Документ':message.video?'Видео':message.audio?'Аудио':message.voice?'Голосовое':'Фото';
  const label=message.caption||'';
  if(data.file_size && data.file_size>CFG.maxFileBytes)
    return {type,link:'',description:label+' [Файл слишком велик для автоматического сохранения]'};
  try {
    const meta=tg_('getFile',{file_id:data.file_id});
    const response=UrlFetchApp.fetch('https://api.telegram.org/file/bot'+token_()+'/'+meta.file_path,{muteHttpExceptions:true});
    if(response.getResponseCode()<200 || response.getResponseCode()>=300) throw Error('Telegram file download HTTP '+response.getResponseCode());
    const folders=DriveApp.getFoldersByName('Файлы Telegram-помощника');
    if(!folders.hasNext()) throw Error('Не найдена папка «Файлы Telegram-помощника»');
    const folder=folders.next();
    const safeName=(data.file_name||('telegram_'+message.chat.id+'_'+message.message_id+'_'+type)).replace(/[\\/:*?"<>|]/g,'_');
    const file=folder.createFile(response.getBlob().setName(safeName));
    // Файлы остаются закрытыми: доступ только по правам Google Drive.
    return {type,link:file.getUrl(),description:label};
  } catch(e) {
    log_('Ошибка файла',message.message_id,e.message);
    return {type,link:'',description:label+' [Не удалось сохранить файл]'};
  }
}
function processMessage_(m) {
  if(!m||!m.chat||!m.from||m.chat.type!=='private') return;
  const chatId=String(m.chat.id), raw=m.text||m.caption||'';
  const name=register_(m);
  const access=accessStatus_(chatId);
  if(!isOwner_(chatId) && access!=='approved') {
    const message=access==='disabled'
      ? 'Доступ к помощнику отключён. Если это ошибка, свяжитесь с Любовью Сергеевной.'
      : 'Ваш аккаунт ожидает подтверждения администратора. Пока поручения недоступны.';
    send_(chatId,message);
    return;
  }
  if(/^\/start(?:@\w+)?(?:\s|$)/.test(raw)) {
    send_(chatId,isOwner_(chatId)
      ? 'Личный помощник подключён. Команды: /plan, /tasks, /replies, /help.'
      : 'Здравствуйте! Здесь вы получаете поручения и отправляете ответы. Команды: /tasks — поручения; /schedule — расписание; /consult YYYY-MM-DD HH:MM [минуты] тема — заявка на консультацию; /faq — справка; /surprise — пасхалка.');
    return;
  }
  if(/^\/help/.test(raw)) {
    send_(chatId,isOwner_(chatId)
      ? '/plan — личные задачи\n/add текст — добавить задачу\n/done ID — выполнить задачу\n/calendar — события сегодня\n/event YYYY-MM-DD HH:MM минуты название — добавить событие\n/schedule — расписание НВГУ\n/consultations — заявки на консультацию\n/approveconsult ID — подтвердить консультацию\n/rejectconsult ID причина — отклонить заявку\n/faq — справочник\n/surprise — сюрприз\n/assign Имя Фамилия YYYY-MM-DD задание — поручение студенту\n/repeat daily Имя Фамилия задание — ежедневное поручение\n/repeat weekly ПН Имя Фамилия задание — еженедельное поручение\n/broadcast текст — подготовить рассылку\n/confirmbroadcast ID — подтвердить отправку рассылки\n/inbox — личные входящие\n/tasks — поручения\n/replies — ответы\n/brief — сводка\n/approve CHAT_ID Имя Фамилия — разрешить доступ\n/revoke CHAT_ID — отключить доступ'
      : '/tasks — выбрать поручение\nОтправьте текст или файл после выбора поручения.');
    return;
  }
  if(isOwner_(chatId)) {
    if(/^\/schedule(?:\s|$)/.test(raw)) return sendTimetableTo_(chatId);
    if(/^\/consultations(?:\s|$)/.test(raw)) return ownerConsultations_(chatId);
    if(/^\/approveconsult(?:\s|$)/.test(raw)) return ownerApproveConsultation_(chatId,raw);
    if(/^\/rejectconsult(?:\s|$)/.test(raw)) return ownerRejectConsultation_(chatId,raw);
    if(/^\/event(?:\s|$)/.test(raw)) return ownerCreateEvent_(chatId,raw,m.message_id);
    if(/^\/assign(?:\s|$)/.test(raw)) return ownerAssignTask_(chatId,raw);
    if(/^\/repeat(?:\s|$)/.test(raw)) return ownerCreateRecurring_(chatId,raw);
    if(/^\/broadcast(?:\s|$)/.test(raw)) return ownerPrepareBroadcast_(chatId,raw);
    if(/^\/confirmbroadcast(?:\s|$)/.test(raw)) return ownerConfirmBroadcast_(chatId,raw);
    if(/^\/faq(?:\s|$)/.test(raw)) return sendFAQ_(chatId);
    if(/^\/surprise(?:\s|$)/.test(raw)) return sendEasterEgg_(chatId);
    if(/^\/approve(?:\s|$)/.test(raw)) return ownerApprove_(chatId,raw);
    if(/^\/revoke(?:\s|$)/.test(raw)) return ownerRevoke_(chatId,raw);
    if(/^\/add(?:\s|$)/.test(raw)) return ownerAdd_(chatId,raw,m.message_id);
    if(/^\/done(?:\s|$)/.test(raw)) return ownerDone_(chatId,raw);
    if(/^\/calendar/.test(raw)) return ownerCalendar_(chatId);
    if(/^\/plan/.test(raw)) return ownerPlan_(chatId);
    if(/^\/brief/.test(raw)) return ownerBrief_(chatId);
    if(/^\/inbox/.test(raw)) return ownerInbox_(chatId);
    if(/^\/replies/.test(raw)) return ownerReplies_(chatId);
    if(/^\/tasks/.test(raw)) return ownerTasks_(chatId);
  } else if(/^\/tasks/.test(raw)) return chooseTask_(chatId);
  else if(/^\/schedule(?:\s|$)/.test(raw)) return sendTimetableTo_(chatId);
  else if(/^\/consult(?:\s|$)/.test(raw)) return studentRequestConsultation_(chatId,name,raw);
  else if(/^\/surprise(?:\s|$)/.test(raw)) return sendEasterEgg_(chatId);
  if(/^\/\w+/.test(raw)) return send_(chatId,'Неизвестная команда. Напишите /help.');
  // Idempotency check across both response and personal-inbox sheets.
  // This prevents duplicates if Telegram retries an update after a partial failure.
  const messageId=String(m.message_id);
  const replyRows=rows_('Ответы',CFG.replyHeaders);
  const existingReply=replyRows.slice(1).find(r=>String(r[3])===chatId && String(r[6])===messageId);
  const alreadyInInbox=rows_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']).slice(1)
    .some(r=>String(r[3])===chatId && String(r[6])===messageId);
  if(existingReply) {
    // Recover a partial write: if the reply row exists but task status update failed, finish it.
    const linkedId=String(existingReply[7]||'');
    if(linkedId) {
      const taskSheet=tab_('Поручения',CFG.taskHeaders), taskRows=taskSheet.getDataRange().getValues();
      for(let i=1;i<taskRows.length;i++) {
        if(String(taskRows[i][0])===linkedId && String(taskRows[i][9])===chatId && ['Отправлено','В работе','Доработка'].includes(String(taskRows[i][5]))) {
          taskSheet.getRange(i+1,6).setValue('Ответ получен');
          taskSheet.getRange(i+1,7).setValue(existingReply[0]||new Date());
          taskSheet.getRange(i+1,8).setValue(existingReply[5]||'['+existingReply[4]+']');
          if(existingReply[8]) taskSheet.getRange(i+1,9).setValue(existingReply[8]);
          break;
        }
      }
    }
    if(!isOwner_(chatId)) notifyOwnerReply_(chatId,existingReply);
    return;
  }
  if(alreadyInInbox) return;
  const replies=tab_('Ответы',CFG.replyHeaders);
  const stored=storeFile_(m);
  const chosen=prop_('SELECTED_TASK_'+chatId);
  const candidates=activeTasks_(chatId).filter(t=>['Отправлено','В работе','Доработка'].includes(String(t.row[5])));
  let task=candidates.find(t=>taskId_(t.row,t.index)===String(chosen) || String(t.index)===String(chosen))||null;
  // For the owner, never infer that an ordinary message is a student response.
  // Students may auto-link only when they have exactly one active assignment.
  if(!task && !isOwner_(chatId) && candidates.length===1) task=candidates[0];
  const taskId=task?taskId_(task.row,task.index):'';
  if(isOwner_(chatId) && !task) {
    const incoming=tab_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']);
    incoming.appendRow([new Date(),name,m.from.username||'',chatId,stored.type,stored.description,m.message_id,stored.link]);
    send_(chatId,'Сообщение сохранено в личных входящих.');
    return;
  }
  replies.appendRow([new Date(),name,m.from.username||'',chatId,stored.type,stored.description,m.message_id,taskId,stored.link]);
  if(task) {
    const s=tab_('Поручения',CFG.taskHeaders);
    s.getRange(task.index,6).setValue('Ответ получен');
    s.getRange(task.index,7).setValue(new Date());
    s.getRange(task.index,8).setValue(stored.description||'['+stored.type+']');
    if(stored.link) s.getRange(task.index,9).setValue(stored.link);
    updateGeneralTaskStatus_(taskId,'Ответ получен');
    PropertiesService.getScriptProperties().deleteProperty('SELECTED_TASK_'+chatId);
  }
  send_(chatId,task?'Ответ сохранён по поручению '+taskId+'. Ожидайте проверки.':
    'Сообщение сохранено. Чтобы связать ответ с заданием, используйте /tasks.');
  if(!isOwner_(chatId)) {
    const justSaved=[new Date(),name,m.from.username||'',chatId,stored.type,stored.description,m.message_id,taskId,stored.link];
    notifyOwnerReply_(chatId,justSaved);
  }
}
function notifyOwnerReply_(chatId,replyRow) {
  const cache=CacheService.getScriptCache();
  const key='OWNER_NOTIFIED_'+String(chatId)+'_'+String(replyRow[6]);
  if(cache.get(key)==='1') return;
  const name=String(replyRow[1]||'Студент');
  const taskId=String(replyRow[7]||'');
  const type=String(replyRow[4]||'Текст');
  const content=String(replyRow[5]||'['+type+']');
  const link=String(replyRow[8]||'');
  send_(owner_(),'Новый ответ от '+name+(taskId?' по '+taskId:' (без привязки к заданию)')+
    ': '+content.slice(0,400)+(link?'\nФайл: '+link:''));
  cache.put(key,'1',21600);
}
function processCallback_(q) {
  if(!q||!q.message||!q.from) return;
  const chatId=String(q.message.chat.id), data=String(q.data||'');
  // Callback confirmation is best-effort: Telegram expires callback queries quickly.
  try { tg_('answerCallbackQuery',{callback_query_id:q.id}); }
  catch(e) { log_('Устаревший callback',q.id,e.message||String(e)); }
  if(!isOwner_(chatId) && accessStatus_(chatId)!=='approved') {
    send_(chatId,'Доступ к поручениям не разрешён.'); return;
  }
  if(data==='week:prev'||data==='week:next') { handleWeekCallback_(chatId,data); return; }
  let task=null;
  if(data.startsWith('taskid:')) {
    const wanted=data.slice('taskid:'.length);
    const tasks=activeTasks_(chatId).filter(t=>['Отправлено','В работе','Доработка'].includes(String(t.row[5])));
    task=tasks.find(t=>taskId_(t.row,t.index)===wanted)||null;
  } else if(data.startsWith('task:')) {
    // Backward compatibility for buttons created before version 1.5.
    const rowIndex=Number(data.slice('task:'.length));
    const sheet=tab_('Поручения',CFG.taskHeaders);
    if(Number.isInteger(rowIndex)&&rowIndex>=2&&rowIndex<=sheet.getLastRow()) {
      const r=sheet.getRange(rowIndex,1,1,11).getValues()[0];
      if(String(r[9])===chatId && ['Отправлено','В работе','Доработка'].includes(String(r[5]))) task={index:rowIndex,row:r};
    }
  } else return;
  if(!task) { send_(chatId,'Это поручение больше недоступно для ответа. Откройте /tasks и выберите его заново.'); return; }
  const stableId=taskId_(task.row,task.index);
  PropertiesService.getScriptProperties().setProperty('SELECTED_TASK_'+chatId,stableId);
  send_(chatId,'Выбрано поручение '+stableId+'. Теперь отправьте ответ или файл.');
}
function pollTelegramUpdates() {
  const lock=LockService.getScriptLock(); if(!lock.tryLock(1000)) return;
  try {
    const props=PropertiesService.getScriptProperties();
    let offset=Number(props.getProperty('TELEGRAM_UPDATE_OFFSET')||'0');
    const updates=tg_('getUpdates',{offset,timeout:0,limit:CFG.pollLimit,allowed_updates:['message','callback_query']});
    for(const u of updates) {
      try {
        if(u.message) processMessage_(u.message);
        else if(u.callback_query) processCallback_(u.callback_query);
      } catch(e) {
        const retryKey='UPDATE_RETRY_'+u.update_id;
        const attempts=Number(props.getProperty(retryKey)||'0')+1;
        props.setProperty(retryKey,String(attempts));
        log_('Ошибка входящего',u.update_id,'Попытка '+attempts+'/'+CFG.maxUpdateRetries+': '+String(e.stack||e.message||e).slice(0,1500));
        if(attempts<CFG.maxUpdateRetries) {
          try { send_(owner_(),'Ошибка обработки сообщения Telegram (update '+u.update_id+', попытка '+attempts+'): '+String(e.message||e).slice(0,400)); } catch(_) {}
          break;
        }
        try { send_(owner_(),'Сообщение Telegram update '+u.update_id+' не обработано после '+attempts+' попыток. Очередь продолжена; проверьте лист «Журнал бота».'); } catch(_) {}
        log_('Обновление пропущено после повторов',u.update_id,String(e.message||e));
        props.deleteProperty(retryKey);
        offset=u.update_id+1;
        props.setProperty('TELEGRAM_UPDATE_OFFSET',String(offset));
        continue;
      }
      props.deleteProperty('UPDATE_RETRY_'+u.update_id);
      offset=u.update_id+1;
      props.setProperty('TELEGRAM_UPDATE_OFFSET',String(offset));
    }
  } finally { lock.releaseLock(); }
}
function sendPendingTasks() {
  const lock=LockService.getScriptLock(); if(!lock.tryLock(1000)) return;
  try {
    const sheet=tab_('Поручения',CFG.taskHeaders);
    const tasks=sheet.getDataRange().getValues();
    const students=rows_('Студенты',CFG.studentHeaders);
    for(let i=1;i<tasks.length;i++) {
      const r=tasks[i],status=String(r[5]||'');
      if(status==='Отправляется') {
        // Previous run may have stopped after Telegram accepted the message.
        // Avoid duplicate delivery; require a human check before retry.
        log_('Требуется сверка отправки',r[0]||i+1,'Статус «Отправляется» остался после прерывания; проверьте Telegram вручную.');
        continue;
      }
      if(status!=='Не отправлено'||!r[1]||!r[2]) continue;
      const matches=students.slice(1).filter(s=>String(s[0]||'').trim().toLowerCase()===String(r[1]).trim().toLowerCase());
      if(matches.length!==1||!matches[0][3]) { log_('Не найден адресат',i+1,r[1]); continue; }
      let id=String(r[0]||'').trim();
      if(!id) {
        id='T-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd')+'-'+(i+1);
        sheet.getRange(i+1,1).setValue(id);
      }
      const chatId=String(matches[0][3]);
      if(!isOwner_(chatId) && accessStatus_(chatId)!=='approved') {
        log_('Отправка отложена: нет доступа',id,chatId); continue;
      }
      const deadline=r[4]?(r[4] instanceof Date?Utilities.formatDate(r[4],CFG.timezone,'dd.MM.yyyy'):String(r[4])):'не указан';
      const msg='Новое поручение № '+id+'\n\n'+r[2]+'\n\nСрок: '+deadline+'\n\nДля ответа нажмите /tasks.';
      try {
        // Состояние «Отправляется» предотвращает повторную отправку при
        // повторном запуске; при сбое требуется ручная сверка с Telegram.
        sheet.getRange(i+1,6).setValue('Отправляется');
        const sent=send_(chatId,msg);
        sheet.getRange(i+1,4).setValue(new Date());
        sheet.getRange(i+1,6).setValue('Отправлено');
        sheet.getRange(i+1,10).setValue(chatId);
        log_('Отправлено',id,'message_id='+sent.message_id);
        updateGeneralTaskStatus_(id,'Отправлено');
      } catch(e) {
        sheet.getRange(i+1,6).setValue('Ошибка отправки');
        log_('Ошибка отправки',id,e.message);
      }
    }
  } finally { lock.releaseLock(); }
}
function dateKey_(d) { return Utilities.formatDate(d,CFG.timezone,'yyyy-MM-dd'); }
// Strictly parse supported deadline formats without silently rolling invalid dates.
function parseDeadline_(value) {
  if(value instanceof Date) return isNaN(value.getTime()) ? null : value;
  if(typeof value !== 'string' || !value.trim()) return null;
  const text=value.trim(); let y,m,d,match;
  if((match=text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) {
    y=Number(match[1]); m=Number(match[2]); d=Number(match[3]);
  } else if((match=text.match(/^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})$/))) {
    d=Number(match[1]); m=Number(match[2]); y=Number(match[3]);
  } else return null;
  if(y<2000 || y>2100 || m<1 || m>12 || d<1 || d>31) return null;
  const iso=String(y).padStart(4,'0')+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0');
  try {
    const parsed=Utilities.parseDate(iso,CFG.timezone,'yyyy-MM-dd');
    return parsed && !isNaN(parsed.getTime()) && dateKey_(parsed)===iso ? parsed : null;
  } catch(e) { return null; }
}
function daysFromToday_(dateValue,todayValue) {
  const due=Date.parse(dateValue+'T12:00:00Z'), today=Date.parse(todayValue+'T12:00:00Z');
  return Number.isFinite(due)&&Number.isFinite(today) ? Math.round((due-today)/86400000) : null;
}
function remindDeadlines() {
  const sheet=tab_('Поручения',CFG.taskHeaders);
  const rows=sheet.getDataRange().getValues(), now=new Date(), today=dateKey_(now);
  for(let i=1;i<rows.length;i++) {
    const r=rows[i],status=String(r[5]||''),chatId=String(r[9]||'');
    if(!chatId||(!isOwner_(chatId) && accessStatus_(chatId)!=='approved')||!['Отправлено','В работе','Доработка'].includes(status)) continue;
    const dueDate=parseDeadline_(r[4]);
    if(!dueDate) {
      if(r[4]!=='' && r[4]!==null) log_('Некорректный срок',taskId_(r,i+1),String(r[4]));
      continue;
    }
    const due=dateKey_(dueDate), days=daysFromToday_(due,today);
    if(days===null) continue;
    if(days>CFG.reminderDays) continue;
    const last=r[10] instanceof Date?dateKey_(r[10]):String(r[10]||'');
    if(last===today) continue;
    const id=taskId_(r,i+1);
    const text=days<0?'Поручение '+id+' просрочено. Пожалуйста, сообщите о ходе работы.':
      days===0?'Сегодня срок выполнения поручения '+id+'.':'Скоро срок выполнения поручения '+id+'.';
    try { send_(chatId,text); sheet.getRange(i+1,11).setValue(now); }
    catch(e) { log_('Ошибка напоминания',id,e.message); }
  }
}
function ownerApprove_(id,raw) {
  const args=raw.replace(/^\/approve(?:\s+|$)/,'').trim();
  const match=args.match(/^(\S+)\s+(.+)$/);
  if(!match) return send_(id,'Формат: /approve CHAT_ID Имя Фамилия');
  const chatId=match[1], name=match[2].trim();
  if(isOwner_(chatId)) return send_(id,'Владелец уже имеет доступ.');
  const sheet=tab_('Студенты',CFG.studentHeaders), rows=sheet.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][3])===chatId) {
    sheet.getRange(i+1,1).setValue(name);
    sheet.getRange(i+1,6).setValue('Одобрен');
    send_(id,'Доступ разрешён: '+name+' ('+chatId+').');
    try { send_(chatId,'Доступ к помощнику подтверждён. Для списка поручений отправьте /tasks.'); } catch(e) { log_('Ошибка уведомления об одобрении',chatId,e.message); }
    return;
  }
  send_(id,'Пользователь с таким chat ID не найден. Пусть он сначала напишет боту /start.');
}
function ownerRevoke_(id,raw) {
  const chatId=raw.replace(/^\/revoke(?:\s+|$)/,'').trim();
  if(!chatId) return send_(id,'Формат: /revoke CHAT_ID');
  if(isOwner_(chatId)) return send_(id,'Нельзя отключить доступ владельцу.');
  const sheet=tab_('Студенты',CFG.studentHeaders), rows=sheet.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][3])===chatId) {
    sheet.getRange(i+1,6).setValue('Доступ отключён');
    send_(id,'Доступ отключён для '+String(rows[i][0])+' ('+chatId+').');
    try { send_(chatId,'Доступ к помощнику отключён.'); } catch(e) { log_('Ошибка уведомления об отключении',chatId,e.message); }
    return;
  }
  send_(id,'Пользователь с таким chat ID не найден.');
}
function ownerAdd_(id,raw,messageId) {
  const text=raw.replace(/^\/add(?:\s|$)/,'').trim();
  if(!text) return send_(id,'Напишите: /add Купить корм Уле');
  const sheet=tab_('Личные задачи',CFG.personalHeaders);
  const key=messageId ? 'L-TG-'+String(id)+'-'+String(messageId) :
    'L-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd-HHmmss')+'-'+Utilities.getUuid().slice(0,8);
  const rows=sheet.getDataRange().getValues();
  const existing=rows.findIndex((r,i)=>i>0 && String(r[0])===key);
  if(existing>0) return send_(id,'Эта задача уже записана: '+key+' — '+text);
  sheet.appendRow([key,'Личное',text,'','Открыто','Обычный','',new Date()]);
  syncGeneralTask_(key,'Личное',text,'Открыто','Обычный','','Добавлено через Telegram-бот');
  send_(id,'Добавила задачу '+key+': '+text);
}
function ownerDone_(id,raw) {
  const key=raw.replace(/^\/done(?:\s+|$)/,'').trim();
  if(!key) return send_(id,'Укажите ID задачи из /plan: /done L-...');
  const sheet=tab_('Личные задачи',CFG.personalHeaders);
  const rows=sheet.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][0])===key) {
    sheet.getRange(i+1,5).setValue('Выполнено');
    updateGeneralTaskStatus_(key,'Выполнено');
    return send_(id,'Задача '+key+' выполнена.');
  }
  send_(id,'Задача с таким ID не найдена.');
}
function ownerCalendar_(id) {
  try {
    const date=dateKey_(new Date());
    const start=Utilities.parseDate(date,CFG.timezone,'yyyy-MM-dd');
    const end=new Date(start.getTime()+86400000);
    const events=CalendarApp.getDefaultCalendar().getEvents(start,end);
    const lines=events.map(e=>{
      if(e.isAllDayEvent()) return '• Весь день: '+e.getTitle();
      return '• '+Utilities.formatDate(e.getStartTime(),CFG.timezone,'HH:mm')+
        ' '+e.getTitle();
    });
    send_(id,'Календарь на сегодня:\n'+(lines.join('\n')||'Событий нет.'));
  } catch(e) {
    log_('Ошибка календаря','today',e.message);
    send_(id,'Не удалось прочитать календарь. Проверьте разрешения Apps Script.');
  }
}
function ownerPlan_(id) {
  const rows=rows_('Личные задачи',CFG.personalHeaders);
  const open=rows.slice(1).filter(r=>r[2]&&String(r[4])!=='Выполнено').slice(0,20);
  send_(id,open.length?'Личные задачи:\n'+open.map(r=>'• ['+r[0]+'] '+r[2]+(r[3]?' — '+(r[3] instanceof Date?Utilities.formatDate(r[3],CFG.timezone,'dd.MM.yyyy'):r[3]):'')).join('\n'):
    'В списке личных задач пока нет активных записей.');
}
function ownerTasks_(id) {
  const rows=rows_('Поручения',CFG.taskHeaders);
  const open=rows.slice(1).filter(r=>r[2]&&!['Выполнено','Отменено'].includes(String(r[5]))).slice(0,25);
  send_(id,open.length?'Поручения:\n'+open.map(r=>'• '+r[1]+': '+String(r[2]).slice(0,70)+' ['+r[5]+']').join('\n'):
    'Активных поручений нет.');
}
function ownerInbox_(id) {
  const rows=rows_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']).slice(-11);
  const items=rows.filter(r=>r[1]).map(r=>'• '+r[1]+': '+String(r[5]||'['+r[4]+']').slice(0,100)+(r[7]?' — '+r[7]:''));
  send_(id,items.length?'Последние личные входящие:\n'+items.join('\n'):'Личных входящих пока нет.');
}
function ownerReplies_(id) {
  const rows=rows_('Ответы',CFG.replyHeaders).slice(-11);
  send_(id,rows.length?'Последние ответы:\n'+rows.filter(r=>r[1]).map(r=>'• '+r[1]+': '+String(r[5]||r[4]).slice(0,90)).join('\n'):
    'Ответов пока нет.');
}
function ownerBrief_(id) {
  const rows=rows_('Поручения',CFG.taskHeaders).slice(1);
  const review=rows.filter(r=>['Ответ получен','На проверке'].includes(String(r[5])));
  const today=dateKey_(new Date());
  const overdue=rows.filter(r=>{
    const due=parseDeadline_(r[4]);
    return due && dateKey_(due)<today && ['Отправлено','В работе','Доработка'].includes(String(r[5]));
  });
  send_(id,'Сводка\nНа проверке: '+review.length+'\nПросрочено: '+overdue.length+
    '\n\n'+review.slice(0,10).map(r=>'• '+r[1]+': '+r[2]).join('\n'));
}
function sendDailyBriefing() {
  const id=owner_();
  const steps=[['Сводка поручений',()=>ownerBrief_(id)],['Календарь',()=>ownerCalendar_(id)],['Личные задачи',()=>ownerPlan_(id)]];
  const failures=[];
  steps.forEach(step=>{ try { step[1](); } catch(e) { failures.push(step[0]+': '+String(e.message||e)); log_('Ошибка ежедневной сводки',step[0],e.stack||e.message||String(e)); } });
  if(failures.length) { try { send_(id,'Не удалось подготовить часть ежедневной сводки:\n'+failures.join('\n').slice(0,2500)); } catch(e) { log_('Ошибка уведомления о сводке','owner',e.message||String(e)); } }
}

// ---------------- Новые модули: общий реестр, расписание, консультации, справочник ----------------
function syncGeneralTask_(id,area,task,status,priority,due,context) {
  try {
    const book=SpreadsheetApp.openById(CFG.taskRegistrySpreadsheetId);
    const sh=book.getSheets()[0];
    const data=sh.getDataRange().getValues();
    const idCol=0;
    for(let i=1;i<data.length;i++) if(String(data[i][idCol])===String(id)) {
      sh.getRange(i+1,2,1,8).setValues([[area,task,status,priority,due,'',context,new Date()]]); return;
    }
    sh.appendRow([id,area,task,status,priority,due,'',context,new Date()]);
  } catch(e) { log_('Ошибка общего реестра',id,e.message||String(e)); }
}
function updateGeneralTaskStatus_(id,status) {
  try {
    const book=SpreadsheetApp.openById(CFG.taskRegistrySpreadsheetId), sh=book.getSheets()[0], data=sh.getDataRange().getValues();
    for(let i=1;i<data.length;i++) if(String(data[i][0])===String(id)) { sh.getRange(i+1,4).setValue(status); sh.getRange(i+1,9).setValue(new Date()); return; }
  } catch(e) { log_('Ошибка обновления общего реестра',id,e.message||String(e)); }
}
function timetableSheet_() { return tab_('Расписание НВГУ',CFG.timetableHeaders); }
function timetableState_() {
  const rows=timetableSheet_().getDataRange().getValues(), out={};
  rows.slice(1).forEach(r=>{ if(r[0]) out[String(r[0])]=r[1]; }); return out;
}
function saveTimetableState_(obj) {
  const sh=timetableSheet_(); sh.clearContents(); sh.getRange(1,1,1,CFG.timetableHeaders.length).setValues([CFG.timetableHeaders]); sh.setFrozenRows(1);
  const now=new Date(), rows=Object.keys(obj).map(k=>[k,obj[k],now]);
  if(rows.length) sh.getRange(2,1,rows.length,3).setValues(rows);
}
function stripHtml_(html) {
  return String(html||'').replace(/<script[\s\S]*?<\/script>/gi,' ').replace(/<style[\s\S]*?<\/style>/gi,' ')
    .replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/(p|div|tr|td|th|li|h[1-6]|table|section|article)>/gi,'\n')
    .replace(/<[^>]+>/g,' ').replace(/&nbsp;|&#160;/gi,' ').replace(/&amp;/gi,'&').replace(/&quot;/gi,'"')
    .replace(/&#39;|&apos;/gi,"'").replace(/&lt;/gi,'<').replace(/&gt;/gi,'>').replace(/[ \t\r]+/g,' ').replace(/\n\s*\n+/g,'\n').trim();
}
function extractWeekLinks_(html,baseUrl) {
  const links={prev:'',next:''};
  const re=/<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)<\/a>/gi; let m;
  while((m=re.exec(String(html||'')))!==null) {
    const label=stripHtml_(m[2]).replace(/\s+/g,' ').trim(), href=m[1].trim();
    if(!href || /^javascript:/i.test(href) || /^#/i.test(href)) continue;
    let absolute=href;
    if(/^\//.test(href)) absolute='https://tm.nvsu.ru'+href;
    else if(!/^https?:\/\//i.test(href)) { const base=baseUrl.match(/^(https?:\/\/[^/]+)(.*)$/i); absolute=base?base[1]+base[2].replace(/[^/]*$/,'')+href:href; }
    if(!/^https?:\/\/tm\.nvsu\.ru\//i.test(absolute)) continue;
    if(!links.prev && /(предыдущ|назад|\bprev\b|←|«|‹)/i.test(label)) links.prev=absolute;
    if(!links.next && /(следующ|впер[её]д|\bnext\b|→|»|›)/i.test(label)) links.next=absolute;
  }
  return links;
}
function fetchTimetable_(url) {
  url=url||CFG.timetableUrl;
  const response=UrlFetchApp.fetch(url,{muteHttpExceptions:true,followRedirects:true,headers:{'User-Agent':'Mozilla/5.0 (compatible; KulaginaAssistant/2.0)'}});
  const code=response.getResponseCode(), html=response.getContentText('UTF-8');
  if(code<200||code>=300) throw Error('Сайт расписания ответил HTTP '+code);
  const text=stripHtml_(html);
  if(!text || text.length<80) throw Error('Сайт вернул слишком короткую страницу');
  const normalized=text.replace(/Сегодня\s+\d{1,2}\s+[А-Яа-я]+\s+\d{4}[^.]{0,80}/gi,' ').replace(/Сегодня\s+\d{1,2}[.\/-]\d{1,2}[.\/-]\d{4}[^.]{0,80}/gi,' ').replace(/\s+/g,' ').trim();
  const noSchedule=/расписание\s+(?:на\s+[^.]{0,40}\s+)?отсутствует/i.test(normalized);
  // Store text snapshot even if the site changes markup; do not claim an empty schedule unless explicit wording exists.
  return {url:url,html:html,text:text,normalized:normalized,noSchedule:noSchedule,weekLinks:extractWeekLinks_(html,url),hash:Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,normalized).map(b=>(b+256).toString(16).slice(-2)).join('')};
}
function checkTimetable_(notify) {
  const old=timetableState_();
  try {
    const fresh=fetchTimetable_();
    const previousHash=String(old.HASH||'');
    const changed=previousHash && previousHash!==fresh.hash;
    saveTimetableState_({URL:CFG.timetableUrl,HASH:fresh.hash,STATUS:fresh.noSchedule?'расписание отсутствует':(changed?'изменилось':'получено'),CHECKED_AT:new Date().toISOString(),TEXT:fresh.text.slice(0,45000),HTML:fresh.html.slice(0,45000),LAST_SUCCESS_TEXT:fresh.text.slice(0,45000)});
    if(notify) {
      if(fresh.noSchedule) send_(owner_(),'Проверка расписания НВГУ: сайт сообщает «расписание отсутствует». Считаю, что занятий нет.');
      else if(changed) send_(owner_(),'В расписании НВГУ обнаружены изменения. Проверь сохранённый снимок в листе «Расписание НВГУ» и ссылку: '+CFG.timetableUrl);
      else send_(owner_(),'Расписание НВГУ проверено. '+(previousHash?'Изменений не обнаружено.':'Первый снимок сохранён; сравнение начнётся со следующей проверки.')+'\n'+CFG.timetableUrl);
    }
    return fresh;
  } catch(e) {
    log_('Ошибка проверки расписания НВГУ',CFG.timetableUrl,e.stack||e.message||String(e));
    if(notify) {
      const lastText=String(old.LAST_SUCCESS_TEXT||old.TEXT||'');
      send_(owner_(),'Не удалось обновить расписание НВГУ. '+(lastText?'Сохраняю последний успешный снимок; он может быть устаревшим.':'Успешного снимка пока нет.')+'\nПричина: '+String(e.message||e).slice(0,500)+'\n'+CFG.timetableUrl);
    }
    return {fallback:true,text:String(old.LAST_SUCCESS_TEXT||old.TEXT||''),status:String(old.STATUS||'нет сохранённого расписания')};
  }
}
function timetableKeyboard_(links) {
  const row=[];
  if(links && links.prev) { PropertiesService.getScriptProperties().setProperty('TIMETABLE_PREV_URL',links.prev); row.push({text:'← Предыдущая неделя',callback_data:'week:prev'}); }
  if(links && links.next) { PropertiesService.getScriptProperties().setProperty('TIMETABLE_NEXT_URL',links.next); row.push({text:'Следующая неделя →',callback_data:'week:next'}); }
  return row.length?{inline_keyboard:[row]}:null;
}
function sendTimetablePage_(chatId,url) {
  try {
    const page=fetchTimetable_(url||CFG.timetableUrl);
    const state=timetableState_();
    if(page.noSchedule) return send_(chatId,'На странице расписания указано «расписание отсутствует» — считаю, что занятий нет.\nИсточник: '+page.url);
    const lines=page.text.split(/\n/).map(x=>x.trim()).filter(Boolean);
    const today=Utilities.formatDate(new Date(),CFG.timezone,'dd.MM.yyyy');
    const relevant=lines.filter(x=>new RegExp(today.replace(/\./g,'[./-]')).test(x));
    const body=(relevant.length?relevant.join('\n'):page.text).slice(0,3000);
    const keyboard=timetableKeyboard_(page.weekLinks);
    send_(chatId,'Расписание НВГУ'+(state.CHECKED_AT?' (последняя автоматическая проверка: '+state.CHECKED_AT+')':'')+'\n'+body+'\n\nИсточник: '+page.url,keyboard?{reply_markup:keyboard}:{});
  } catch(e) {
    const state=timetableState_(), last=String(state.LAST_SUCCESS_TEXT||state.TEXT||'');
    send_(chatId,'Не удалось загрузить выбранную страницу расписания. '+(last?'Показываю последний сохранённый снимок.\n'+last.slice(0,2200):'Сохранённого снимка пока нет.')+'\n'+CFG.timetableUrl);
    log_('Ошибка показа расписания',url||CFG.timetableUrl,e.message||String(e));
  }
}
function sendTimetableTo_(chatId) {
  const state=timetableState_();
  if(String(state.STATUS||'').toLowerCase()==='расписание отсутствует') return send_(chatId,'В сохранённом расписании указано, что расписание отсутствует; считаю, что занятий нет. Источник: '+CFG.timetableUrl);
  if(!state.TEXT) return sendTimetablePage_(chatId,CFG.timetableUrl);
  const pageUrl=String(state.URL||CFG.timetableUrl);
  // Use the current official page to expose actual week-navigation links; fall back to saved snapshot on outage.
  sendTimetablePage_(chatId,pageUrl);
}
function handleWeekCallback_(chatId,data) {
  const key=data==='week:prev'?'TIMETABLE_PREV_URL':data==='week:next'?'TIMETABLE_NEXT_URL':'';
  if(!key) return false;
  const url=PropertiesService.getScriptProperties().getProperty(key)||'';
  if(!url || !(url.indexOf('https://tm.nvsu.ru/')===0 || url.indexOf('http://tm.nvsu.ru/')===0)) { send_(chatId,'Ссылка на выбранную неделю не найдена. Откройте /schedule заново.'); return true; }
  sendTimetablePage_(chatId,url); return true;
}

function parseDateTime_(dateText,timeText) {
  const d=String(dateText||'').trim(), t=String(timeText||'').trim();
  const dm=d.match(/^(\d{4})-(\d{2})-(\d{2})$/), tm=t.match(/^(\d{2}):(\d{2})$/);
  if(!dm||!tm) return null;
  const y=Number(dm[1]), mo=Number(dm[2]), day=Number(dm[3]), hh=Number(tm[1]), mm=Number(tm[2]);
  if(y<2000||y>2100||mo<1||mo>12||day<1||day>31||hh>23||mm>59) return null;
  try {
    const parsed=Utilities.parseDate(d+' '+t,CFG.timezone,'yyyy-MM-dd HH:mm');
    if(!parsed||isNaN(parsed.getTime())) return null;
    // Reject impossible dates instead of silently rolling them into another month.
    if(Utilities.formatDate(parsed,CFG.timezone,'yyyy-MM-dd HH:mm')!==d+' '+t) return null;
    return parsed;
  } catch(e) { return null; }
}
function ownerCreateEvent_(chatId,raw,messageId) {
  const m=raw.match(/^\/event\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(\d{1,3})\s+(.+)$/s);
  if(!m) return send_(chatId,'Формат: /event YYYY-MM-DD HH:MM минуты название. Пример: /event 2026-10-29 14:00 60 Консультация');
  const eventKey='EVENT_MESSAGE_'+String(chatId)+'_'+String(messageId||'');
  if(messageId && PropertiesService.getScriptProperties().getProperty(eventKey)) return send_(chatId,'Это событие уже создано: '+PropertiesService.getScriptProperties().getProperty(eventKey));
  const start=parseDateTime_(m[1],m[2]);
  const hm=m[2].split(':').map(Number), duration=Number(m[3]), title=m[4].trim();
  if(!start||hm[0]>23||hm[1]>59||duration<5||duration>720||!title) return send_(chatId,'Проверьте дату, время, длительность (5–720 минут) и название.');
  const end=new Date(start.getTime()+duration*60000);
  const cal=CalendarApp.getDefaultCalendar(); const conflicts=cal.getEvents(start,end);
  if(conflicts.length) return send_(chatId,'В это время есть пересечение с календарём: '+conflicts.slice(0,5).map(e=>e.getTitle()).join('; ')+'. Событие не создано.');
  const event=cal.createEvent(title,start,end,{description:'Создано через Telegram-бот @KulaginaLS_bot по поручению Любови Сергеевны.'});
  if(messageId) PropertiesService.getScriptProperties().setProperty(eventKey,event.getId());
  log_('Событие создано',event.getId(),title+'; '+start.toISOString());
  send_(chatId,'Добавила событие в Google Календарь: '+title+'\n'+Utilities.formatDate(start,CFG.timezone,'dd.MM.yyyy HH:mm')+'–'+Utilities.formatDate(end,CFG.timezone,'HH:mm'));
}
function studentRequestConsultation_(chatId,name,raw) {
  const m=raw.match(/^\/consult\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})(?:\s+(\d{1,3}))?\s+(.+)$/s);
  if(!m) return send_(chatId,'Формат: /consult YYYY-MM-DD HH:MM [минуты] тема. Пример: /consult 2026-10-29 14:00 30 Обсуждение статьи');
  const date=parseDateTime_(m[1],m[2]), hm=m[2].split(':').map(Number), duration=Number(m[3]||30), topic=m[4].trim();
  if(!date||hm[0]>23||hm[1]>59||duration<10||duration>180||!topic) return send_(chatId,'Проверь дату, время, длительность (10–180 минут) и тему.');
  const sh=tab_('Заявки на консультации',CFG.consultationHeaders);
  const id='C-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd-HHmmss')+'-'+Utilities.getUuid().slice(0,5);
  const student=findStudent_(chatId); const displayName=student?String(student.row[0]||name):name;
  sh.appendRow([id,new Date(),displayName,String(chatId),m[1],m[2],duration,topic,'Ожидает решения','','']);
  send_(chatId,'Заявка на консультацию зарегистрирована: '+id+'. Это пока не подтверждённая встреча. Любовь Сергеевна проверит время и сообщит решение.');
  send_(owner_(),'Новая заявка на консультацию\nID: '+id+'\nСтудент: '+displayName+'\nВремя: '+m[1]+' '+m[2]+' ('+duration+' мин)\nТема: '+topic+'\nПодтвердить: /approveconsult '+id+'\nОтклонить: /rejectconsult '+id+' причина');
}
function findConsultation_(id) {
  const sh=tab_('Заявки на консультации',CFG.consultationHeaders), rows=sh.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][0])===String(id)) return {sheet:sh,index:i+1,row:rows[i]};
  return null;
}
function ownerApproveConsultation_(chatId,raw) {
  const id=raw.replace(/^\/approveconsult\s*/,'').trim(), item=findConsultation_(id);
  if(!item) return send_(chatId,'Заявка не найдена: '+id);
  if(String(item.row[8])!=='Ожидает решения') return send_(chatId,'Заявка '+id+' уже обработана или требует сверки: '+item.row[8]);
  const start=parseDateTime_(String(item.row[4]),String(item.row[5])); if(!start) return send_(chatId,'В заявке некорректная дата. Исправь её в листе «Заявки на консультации».');
  const duration=Number(item.row[6]); const end=new Date(start.getTime()+duration*60000);
  const cal=CalendarApp.getDefaultCalendar(), conflicts=cal.getEvents(start,end);
  if(conflicts.length) return send_(chatId,'Нельзя подтвердить: время занято ('+conflicts.slice(0,5).map(e=>e.getTitle()).join('; ')+'). Предложи другое время.');
  item.sheet.getRange(item.index,9).setValue('Обработка — требуется сверка при сбое');
  const event=cal.createEvent('Консультация: '+item.row[2],start,end,{description:'Заявка '+id+'; тема: '+item.row[7]+'; создано после подтверждения Любовью Сергеевной.'});
  item.sheet.getRange(item.index,9).setValue('Подтверждена'); item.sheet.getRange(item.index,10).setValue('Подтверждена владельцем'); item.sheet.getRange(item.index,11).setValue(event.getId());
  send_(chatId,'Консультация подтверждена и добавлена в Google Календарь: '+id);
  try { send_(String(item.row[3]),'Любовь Сергеевна подтвердила консультацию.\nДата: '+String(item.row[4])+' '+String(item.row[5])+'\nТема: '+String(item.row[7])); } catch(e) { log_('Ошибка уведомления о консультации',id,e.message); }
}
function ownerRejectConsultation_(chatId,raw) {
  const m=raw.match(/^\/rejectconsult\s+(\S+)(?:\s+([\s\S]+))?$/); if(!m) return send_(chatId,'Формат: /rejectconsult ID причина');
  const item=findConsultation_(m[1]); if(!item) return send_(chatId,'Заявка не найдена: '+m[1]);
  if(String(item.row[8])!=='Ожидает решения') return send_(chatId,'Заявка уже обработана: '+item.row[8]);
  const reason=m[2]||'Предложите другое время'; item.sheet.getRange(item.index,9).setValue('Отклонена'); item.sheet.getRange(item.index,10).setValue(reason);
  try { send_(String(item.row[3]),'Заявка на консультацию '+m[1]+' не подтверждена. Причина: '+reason); } catch(e) { log_('Ошибка уведомления об отказе',m[1],e.message); }
  send_(chatId,'Заявка '+m[1]+' отклонена; студент уведомлён.');
}
function ownerConsultations_(chatId) {
  const rows=rows_('Заявки на консультации',CFG.consultationHeaders).slice(1).filter(r=>String(r[8])==='Ожидает решения');
  send_(chatId,rows.length?'Заявки, ожидающие решения:\n'+rows.slice(0,15).map(r=>'• '+r[0]+' — '+r[2]+'; '+r[4]+' '+r[5]+'; '+r[7]).join('\n'):'Заявок, ожидающих решения, нет.');
}
function ownerAssignTask_(chatId,raw) {
  const m=raw.match(/^\/assign\s+(.+?)\s+(\d{4}-\d{2}-\d{2})\s+([\s\S]+)$/);
  if(!m) return send_(chatId,'Формат: /assign Имя Фамилия YYYY-MM-DD текст задания');
  const name=m[1].trim(), due=parseDeadline_(m[2]), task=m[3].trim();
  if(!due||!task) return send_(chatId,'Проверь дату и текст задания.');
  const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>String(r[0]||'').trim().toLowerCase()===name.toLowerCase());
  if(students.length!==1) return send_(chatId,'Найдено адресатов с таким именем: '+students.length+'. Уточни точное имя в листе «Студенты».');
  const st=students[0]; if(!st[3]||!isApprovedNote_(st[5])) return send_(chatId,'Студент не подключён или не одобрен. Поручение не создано.');
  const sh=tab_('Поручения',CFG.taskHeaders), id='T-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd-HHmmss')+'-'+Utilities.getUuid().slice(0,5);
  sh.appendRow([id,st[0],task,new Date(),due,'Не отправлено','','','',String(st[3]),'']);
  syncGeneralTask_(id,'Студенты',task,'Не отправлено','Обычный',m[2],'Поручение студенту '+st[0]);
  send_(chatId,'Поручение создано: '+id+'\nАдресат: '+st[0]+'\nСрок: '+m[2]+'\nТекст: '+task+'\nОтправка выполнится автоматическим триггером.');
}
function ownerCreateRecurring_(chatId,raw) {
  // Require a visible delimiter between the student's full name and task text;
  // otherwise names and task words cannot be separated reliably.
  const m=raw.match(/^\/repeat\s+(daily|weekly)(?:\s+(ПН|ВТ|СР|ЧТ|ПТ|СБ|ВС))?\s+(.+?)\s+\|\s+([\s\S]+)$/i);
  if(!m) return send_(chatId,'Формат: /repeat daily Имя Фамилия | текст задания или /repeat weekly ПН Имя Фамилия | текст задания. Повтор включится сразу.');
  const cadence=m[1].toLowerCase(), weekday=(m[2]||'').toUpperCase(), rest=m[3].trim(), task=m[4].trim();
  if(cadence==='weekly'&&!weekday) return send_(chatId,'Для weekly укажи день недели: ПН, ВТ, СР, ЧТ, ПТ, СБ или ВС.');
  const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>String(r[0]||'').trim().toLowerCase()===rest.toLowerCase());
  if(students.length!==1) return send_(chatId,'Не удалось однозначно найти студента по имени. Правило не создано.');
  const st=students[0]; if(!st[3]||!isApprovedNote_(st[5])) return send_(chatId,'Студент не подключён или не одобрен. Правило не создано.');
  const sh=tab_('Повторяющиеся поручения',CFG.recurringHeaders), id='R-'+Utilities.getUuid().slice(0,8);
  sh.appendRow([id,'Да',cadence,weekday,st[0],task,1,'',new Date()]);
  send_(chatId,'Повторяющееся поручение создано: '+id+'\nСтудент: '+st[0]+'\nПериодичность: '+(cadence==='daily'?'ежедневно':'еженедельно, '+weekday)+'\nЗадание: '+task+'\nПервое поручение появится при следующем ежедневном запуске.');
}
function generateRecurringAssignments() {
  const sh=tab_('Повторяющиеся поручения',CFG.recurringHeaders), rows=sh.getDataRange().getValues();
  const now=new Date(), today=dateKey_(now), weekdayNames=['ВС','ПН','ВТ','СР','ЧТ','ПТ','СБ'], todayName=weekdayNames[Number(Utilities.formatDate(now,CFG.timezone,'u'))%7];
  const students=rows_('Студенты',CFG.studentHeaders).slice(1), tasks=tab_('Поручения',CFG.taskHeaders);
  for(let i=1;i<rows.length;i++) {
    const r=rows[i]; if(String(r[1]).toLowerCase()!=='да') continue;
    if(String(r[2])==='weekly'&&String(r[3]).toUpperCase()!==todayName) continue;
    if(r[7] && dateKey_(r[7] instanceof Date?r[7]:parseDeadline_(String(r[7])||'')||now)===today) continue;
    const matches=students.filter(s=>String(s[0])===String(r[4]));
    if(matches.length!==1||!matches[0][3]||!isApprovedNote_(matches[0][5])) { log_('Повторное поручение пропущено',r[0],'Студент не найден или не одобрен'); continue; }
    const due=new Date(now.getTime()+Math.max(0,Number(r[6]||1))*86400000), id='T-'+Utilities.formatDate(now,CFG.timezone,'yyyyMMdd')+'-'+String(r[0]);
    tasks.appendRow([id,r[4],r[5],now,due,'Не отправлено','','','',String(matches[0][3]),'']);
    syncGeneralTask_(id,'Студенты',String(r[5]),'Не отправлено','Обычный',dateKey_(due),'Повторяющееся правило '+r[0]);
    sh.getRange(i+1,8).setValue(now);
    log_('Создано повторное поручение',id,'Правило '+r[0]);
  }
}
function ownerPrepareBroadcast_(chatId,raw) {
  const text=raw.replace(/^\/broadcast(?:\s|$)/,'').trim();
  if(!text) return send_(chatId,'Напиши: /broadcast текст объявления. Бот сначала покажет черновик; отправки без отдельного подтверждения не будет.');
  const sh=tab_('Рассылки',CFG.broadcastHeaders), id='B-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd-HHmmss')+'-'+Utilities.getUuid().slice(0,5);
  sh.appendRow([id,new Date(),text,'Черновик',0,'','']);
  send_(chatId,'Черновик рассылки '+id+' создан.\n\n'+text+'\n\nДля отправки всем одобренным пользователям отдельно выполни /confirmbroadcast '+id+'. Пока никому ничего не отправлено.');
}
function ownerConfirmBroadcast_(chatId,raw) {
  const id=raw.replace(/^\/confirmbroadcast\s*/,'').trim(); if(!id) return send_(chatId,'Формат: /confirmbroadcast ID');
  const sh=tab_('Рассылки',CFG.broadcastHeaders), rows=sh.getDataRange().getValues(); let row=0, item=null;
  for(let i=1;i<rows.length;i++) if(String(rows[i][0])===id) { row=i+1; item=rows[i]; break; }
  if(!item) return send_(chatId,'Черновик рассылки не найден: '+id);
  if(String(item[3])!=='Черновик') return send_(chatId,'Рассылка уже обработана: '+item[3]);
  const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>r[3] && isApprovedNote_(r[5]));
  sh.getRange(row,4).setValue('Отправка'); sh.getRange(row,6).setValue(new Date());
  let sent=0, failed=0;
  students.forEach(st=>{ try { send_(String(st[3]),'Сообщение от Любови Сергеевны:\n\n'+String(item[2])); sent++; } catch(e) { failed++; log_('Ошибка рассылки',id,String(st[0])+': '+String(e.message||e)); } });
  sh.getRange(row,4).setValue(failed?'Отправлено частично':'Отправлено'); sh.getRange(row,5).setValue(sent); sh.getRange(row,7).setValue(new Date());
  send_(chatId,'Рассылка '+id+' завершена. Успешно: '+sent+'; ошибки: '+failed+'. Статус: '+(failed?'Отправлено частично':'Отправлено')+'.');
}
function sendFAQ_(chatId) {
  send_(chatId,'Справка по помощнику @KulaginaLS_bot\n\n/tasks — список поручений и выбор задания для ответа.\n/consult YYYY-MM-DD HH:MM [минуты] тема — заявка на консультацию; встреча не считается подтверждённой до решения Любови Сергеевны.\n/schedule — последний сохранённый снимок расписания НВГУ.\n/faq — эта справка.\n/surprise — маленькая пасхалка.\n\nЕсли функция недоступна, напишите Любови Сергеевне.');
}
function sendEasterEgg_(chatId) {
  const jokes=[
    'Экологический прогноз: вероятность того, что задача выполнится сама, статистически не отличается от нуля. Рекомендуется вмешательство исследователя.',
    'Напоминание от бота: дедлайн — это не природное явление. Его можно предотвратить планированием.',
    'Систематик обнаружил новый вид: Homo procrastinatus. Обитает в папке «Разобрать позже».',
    'Уровень антропогенной нагрузки на список задач превышен. Требуется срочное сокращение выбросов новых задач.'
  ];
  const n=Math.floor(Math.random()*jokes.length); send_(chatId,'🌿 '+jokes[n]);
}
function checkTimetableTrigger() { checkTimetable_(true); }

function setupAutomation() {
  initialize();
  owner_(); token_();
  tg_('deleteWebhook',{drop_pending_updates:false});
  const handlers=['pollTelegramUpdates','sendPendingTasks','remindDeadlines','sendDailyBriefing','checkTimetableTrigger','generateRecurringAssignments'];
  ScriptApp.getProjectTriggers().forEach(t=>{
    if(handlers.includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('pollTelegramUpdates').timeBased().everyMinutes(1).create();
  ScriptApp.newTrigger('sendPendingTasks').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('remindDeadlines').timeBased().everyDays(1).atHour(9).inTimezone(CFG.timezone).create();
  ScriptApp.newTrigger('sendDailyBriefing').timeBased().everyDays(1).atHour(7).inTimezone(CFG.timezone).create();
  ScriptApp.newTrigger('checkTimetableTrigger').timeBased().everyDays(1).atHour(CFG.timetableCheckHour).nearMinute(CFG.timetableCheckMinute).inTimezone(CFG.timezone).create();
  ScriptApp.newTrigger('generateRecurringAssignments').timeBased().everyDays(1).atHour(8).inTimezone(CFG.timezone).create();
  log_('Настройка','Автоматизация','Триггеры установлены; кандидат 2.0. Apps Script nearMinute запускает триггер приблизительно около 07:30; точная минута не гарантируется.');
}
