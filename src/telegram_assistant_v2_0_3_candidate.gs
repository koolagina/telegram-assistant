/**
 * Личный помощник Кулагиной Л. С. — Google Apps Script
 * Кандидат версии 2.0.3 (локальные регрессионные проверки; не развёрнут). Новые модули расписания, консультаций, справки и общего реестра; уточнён парсинг повторяющихся поручений и даты-времени.
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
// Locks are reentrant only within this execution; never release a caller's lock.
function withScriptLock_(action) {
  const lock=LockService.getScriptLock(), owned=!lock.hasLock();
  if(owned && !lock.tryLock(1000)) throw Error('Не удалось получить блокировку');
  try { return action(); } finally { if(owned) lock.releaseLock(); }
}
function requiredProperty_(key) {
  const value=prop_(key); if(!value) throw Error('Не задано свойство '+key); return value;
}
function digestKey_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,String(text))
    .map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');
}
function messageKey_(prefix,chatId,messageId) {
  if(!/^[0-9]+$/.test(String(messageId||''))) throw Error('Требуется Telegram message ID');
  return prefix+'-TG-'+digestKey_(String(chatId)+':'+String(messageId)).slice(0,32);
}
function appendOnce_(sheet,row) {
  return withScriptLock_(()=>{
    const matches=sheet.getDataRange().getValues().slice(1).filter(r=>String(r[0])===String(row[0]));
    if(matches.length>1) throw Error('Неоднозначный ID: требуется сверка');
    if(matches.length) return matches[0];
    sheet.appendRow(row); SpreadsheetApp.flush(); return row;
  });
}
function attachmentFolder_() {
  const folder=DriveApp.getFolderById(requiredProperty_('ASSISTANT_DRIVE_FOLDER_ID'));
  if(folder.getSharingAccess()!==DriveApp.Access.PRIVATE) throw Error('Папка вложений должна быть закрытой');
  return folder;
}
function ss_() { return SpreadsheetApp.openById(requiredProperty_('ASSISTANT_SPREADSHEET_ID')); }
function tab_(name, headers) {
  const book=ss_(); let s=book.getSheetByName(name);
  if(!s) s=book.insertSheet(name);
  if(s.getLastRow()===0) { s.getRange(1,1,1,headers.length).setValues([headers]); s.setFrozenRows(1); }
  else {
    const existing=s.getRange(1,1,1,Math.max(headers.length,s.getLastColumn())).getValues()[0];
    if(headers.some((h,i)=>String(existing[i])!==h)) throw Error('Несовместимая схема листа '+name+'; требуется отдельная миграция');
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
  attachmentFolder_(); // Existing explicit sandbox folder; never create or change sharing here.
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
  const description=message.caption||'';
  return withScriptLock_(()=>{
    const key=messageKey_('FILE',message.chat.id,message.message_id)+'-'+digestKey_(data.file_unique_id||data.file_id);
    const name='ta-'+digestKey_(key), folder=attachmentFolder_();
    const existing=folder.getFilesByName(name);
    if(existing.hasNext()) {
      const file=existing.next();
      if(existing.hasNext()) throw Error('Дубликаты вложения: требуется сверка');
      return {type,link:file.getUrl(),description};
    }
    const props=PropertiesService.getScriptProperties();
    // A previous create may have succeeded even when its response was lost.
    // If Drive lookup has not found it yet, stop rather than create another file.
    if(props.getProperty(key)) throw Error('Неопределённый результат сохранения файла: требуется сверка');
    if(data.file_size && data.file_size>CFG.maxFileBytes) throw Error('Файл слишком велик');
    let response;
    try {
      const meta=tg_('getFile',{file_id:data.file_id});
      response=UrlFetchApp.fetch('https://api.telegram.org/file/bot'+token_()+'/'+meta.file_path,{muteHttpExceptions:true});
    } catch(e) { throw Error('Не удалось загрузить вложение Telegram'); } // Do not leak token-bearing URL.
    if(response.getResponseCode()<200||response.getResponseCode()>=300) throw Error('Ошибка HTTP при загрузке вложения');
    const blob=response.getBlob();
    if(blob.getBytes().length>CFG.maxFileBytes) throw Error('Файл слишком велик');
    props.setProperty(key,'CREATING');
    let file;
    try { file=folder.createFile(blob.setName(name)); }
    catch(e) { throw Error('Неопределённый результат сохранения файла: требуется сверка'); }
    // Keep the marker even on success: deletion/move must never silently create another copy.
    return {type,link:file.getUrl(),description};
  });
}
function processMessage_(m) { return withScriptLock_(()=>processMessageLocked_(m)); }
function processMessageLocked_(m) {
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
      ? '/plan — личные задачи\n/add текст — добавить задачу\n/done ID — выполнить задачу\n/calendar — события сегодня\n/event YYYY-MM-DD HH:MM минуты название — добавить событие\n/schedule — расписание НВГУ\n/consultations — заявки на консультацию\n/approveconsult ID — подтвердить консультацию\n/rejectconsult ID причина — отклонить заявку\n/faq — справочник\n/surprise — сюрприз\n/assign Имя Фамилия YYYY-MM-DD задание — поручение студенту\n/repeat daily Имя Фамилия | задание — черновик ежедневного поручения\n/repeat weekly ПН Имя Фамилия | задание — черновик еженедельного поручения\n/confirmrepeat ID — включить правило\n/broadcast текст — подготовить рассылку\n/confirmbroadcast ID — подтвердить отправку рассылки\n/inbox — личные входящие\n/tasks — поручения\n/replies — ответы\n/brief — сводка\n/approve CHAT_ID Имя Фамилия — разрешить доступ\n/revoke CHAT_ID — отключить доступ'
      : '/tasks — выбрать поручение\nОтправьте текст или файл после выбора поручения.');
    return;
  }
  if(isOwner_(chatId)) {
    if(/^\/schedule(?:\s|$)/.test(raw)) return sendTimetableTo_(chatId);
    if(/^\/consultations(?:\s|$)/.test(raw)) return ownerConsultations_(chatId);
    if(/^\/approveconsult(?:\s|$)/.test(raw)) return ownerApproveConsultation_(chatId,raw);
    if(/^\/rejectconsult(?:\s|$)/.test(raw)) return ownerRejectConsultation_(chatId,raw);
    if(/^\/event(?:\s|$)/.test(raw)) return ownerCreateEvent_(chatId,raw,m.message_id);
    if(/^\/assign(?:\s|$)/.test(raw)) return ownerAssignTask_(chatId,raw,m.message_id);
    if(/^\/confirmrepeat(?:\s|$)/.test(raw)) return ownerConfirmRecurring_(chatId,raw);
    if(/^\/repeat(?:\s|$)/.test(raw)) return ownerCreateRecurring_(chatId,raw,m.message_id);
    if(/^\/broadcast(?:\s|$)/.test(raw)) return ownerPrepareBroadcast_(chatId,raw,m.message_id);
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
  else if(/^\/consult(?:\s|$)/.test(raw)) return studentRequestConsultation_(chatId,name,raw,m.message_id);
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
    // Repair each missing field, even when the first status write already succeeded.
    const linkedId=String(existingReply[7]||'');
    if(linkedId) {
      const taskSheet=tab_('Поручения',CFG.taskHeaders), taskRows=taskSheet.getDataRange().getValues();
      const matches=taskRows.slice(1).map((r,i)=>({row:r,index:i+2})).filter(t=>String(t.row[0])===linkedId && String(t.row[9])===chatId);
      if(matches.length>1) throw Error('Неоднозначный ID поручения');
      if(matches.length) {
        const item=matches[0], r=item.row, status=String(r[5]);
        if(['Отправлено','В работе','Доработка','Ответ получен'].includes(status)) {
          if(!r[6]) taskSheet.getRange(item.index,7).setValue(existingReply[0]);
          if(!r[7]) taskSheet.getRange(item.index,8).setValue(existingReply[5]||'['+existingReply[4]+']');
          if(!r[8] && existingReply[8]) taskSheet.getRange(item.index,9).setValue(existingReply[8]);
          if(status!=='Ответ получен') taskSheet.getRange(item.index,6).setValue('Ответ получен');
          updateGeneralTaskStatus_(linkedId,'Ответ получен');
        }
        if(prop_('SELECTED_TASK_'+chatId)===linkedId) PropertiesService.getScriptProperties().deleteProperty('SELECTED_TASK_'+chatId);
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
// Additive technical sheet only; existing business columns remain unchanged.
function updateInbox_() {
  return tab_('Очередь updates',['Ключ','Статус','Попытки','Payload JSON','Обновлено','Ошибка']);
}
function inboxItem_(sheet,key) {
  const rows=sheet.getDataRange().getValues();
  const matches=rows.slice(1).map((row,i)=>({row,index:i+2})).filter(x=>String(x.row[0])===key);
  if(matches.length!==1) throw Error('Неоднозначная запись очереди'); return matches[0];
}
function processInboxItem_(sheet,item) {
  if(['DONE','DEAD'].includes(String(item.row[1]))) return true;
  const attempts=Number(item.row[2]);
  if(!Number.isInteger(attempts)||attempts<0) throw Error('Некорректный счётчик очереди');
  // PROCESSING counts even if the previous execution was killed without a catch.
  if(attempts>=CFG.maxUpdateRetries) {
    sheet.getRange(item.index,2).setValue('DEAD'); SpreadsheetApp.flush(); return true;
  }
  const update=JSON.parse(String(item.row[3]));
  sheet.getRange(item.index,3).setValue(attempts+1);
  sheet.getRange(item.index,2).setValue('PROCESSING');
  sheet.getRange(item.index,5).setValue(new Date()); SpreadsheetApp.flush();
  let failed=false;
  try {
    if(update.message) processMessage_(update.message);
    else if(update.callback_query) processCallback_(update.callback_query);
  } catch(e) { failed=true; }
  // Persistence errors escape: never acknowledge an unrecorded outcome.
  sheet.getRange(item.index,6).setValue(failed?'Ошибка обработчика; требуется сверка по payload':'');
  const terminal=failed && attempts+1>=CFG.maxUpdateRetries;
  sheet.getRange(item.index,2).setValue(failed?(terminal?'DEAD':'RETRY'):'DONE');
  sheet.getRange(item.index,5).setValue(new Date()); SpreadsheetApp.flush();
  return !failed||terminal;
}
function pollTelegramUpdates() {
  const lock=LockService.getScriptLock(); if(!lock.tryLock(1000)) return;
  try {
    const props=PropertiesService.getScriptProperties();
    let offset=Number(props.getProperty('TELEGRAM_UPDATE_OFFSET')||'0');
    if(!Number.isSafeInteger(offset)||offset<0) throw Error('Некорректный offset');
    const updates=tg_('getUpdates',{offset,timeout:0,limit:CFG.pollLimit,allowed_updates:['message','callback_query']});
    const sheet=updateInbox_();
    for(const update of updates) {
      if(!Number.isSafeInteger(update.update_id)||update.update_id<0) throw Error('Некорректный update ID');
      if(update.update_id<offset) continue;
      const payload=JSON.stringify(update);
      if(payload.length>45000) throw Error('Payload превышает лимит записи очереди; offset сохранён');
      const key='U-'+update.update_id;
      appendOnce_(sheet,[key,'PENDING',0,payload,new Date(),'']);
      if(!processInboxItem_(sheet,inboxItem_(sheet,key))) break;
      offset=update.update_id+1;
      props.setProperty('TELEGRAM_UPDATE_OFFSET',String(offset));
    }
  } finally { lock.releaseLock(); }
}
// Operator-only Apps Script helper, deliberately not exposed as a Telegram command.
// Inspect partial side effects and the payload before explicitly replaying a DEAD item.
function replayDeadUpdate_(updateId) {
  return withScriptLock_(()=>{
    if(!/^[0-9]+$/.test(String(updateId))) throw Error('Некорректный update ID');
    const sheet=updateInbox_(), item=inboxItem_(sheet,'U-'+updateId);
    if(item.row[1]!=='DEAD') throw Error('Повтор разрешён только для DEAD');
    const update=JSON.parse(String(item.row[3]));
    if(String(update.update_id)!==String(updateId)) throw Error('Payload не соответствует ID');
    sheet.getRange(item.index,3).setValue(0);
    sheet.getRange(item.index,2).setValue('PENDING'); SpreadsheetApp.flush();
    return processInboxItem_(sheet,inboxItem_(sheet,'U-'+updateId));
  });
}
function deliverySheet_() {
  return tab_('Исходящие операции',['Ключ','Telegram chat ID','Payload JSON','Статус','Telegram message ID','Обновлено']);
}
function deliveryItem_(key) {
  const sheet=deliverySheet_(), rows=sheet.getDataRange().getValues();
  const matches=rows.slice(1).map((row,i)=>({sheet,row,index:i+2})).filter(x=>String(x.row[0])===key);
  if(matches.length>1) throw Error('Неоднозначная исходящая операция'); return matches[0]||null;
}
function sendOnce_(key,chatId,text) {
  return withScriptLock_(()=>{
    if(String(text).length>4000) throw Error('Сообщение длиннее 4000 символов');
    const sheet=deliverySheet_();
    appendOnce_(sheet,[key,String(chatId),JSON.stringify({text:String(text)}),'READY','',new Date()]);
    const item=deliveryItem_(key);
    if(String(item.row[1])!==String(chatId)) throw Error('Изменился адресат исходящей операции');
    if(item.row[3]==='SENT'||(item.row[3]==='SENDING'&&item.row[4])) {
      if(item.row[3]!=='SENT') { sheet.getRange(item.index,4).setValue('SENT'); SpreadsheetApp.flush(); }
      return {message_id:item.row[4]};
    }
    if(item.row[3]!=='READY') throw Error('Неопределённый результат отправки: требуется сверка');
    sheet.getRange(item.index,4).setValue('SENDING'); SpreadsheetApp.flush();
    let sent;
    try { sent=send_(chatId,JSON.parse(item.row[2]).text); }
    catch(e) {
      sheet.getRange(item.index,4).setValue('UNKNOWN'); SpreadsheetApp.flush();
      throw Error('Неопределённый результат отправки: требуется сверка');
    }
    if(!sent||sent.message_id===undefined) throw Error('Нет подтверждения отправки');
    sheet.getRange(item.index,5).setValue(String(sent.message_id));
    sheet.getRange(item.index,6).setValue(new Date());
    sheet.getRange(item.index,4).setValue('SENT'); SpreadsheetApp.flush();
    return sent;
  });
}
function finishTaskDelivery_(sheet,index,chatId,id) {
  sheet.getRange(index,4).setValue(new Date());
  sheet.getRange(index,10).setValue(String(chatId));
  sheet.getRange(index,6).setValue('Отправлено'); SpreadsheetApp.flush();
  updateGeneralTaskStatus_(id,'Отправлено');
}
function sendPendingTasks() {
  const lock=LockService.getScriptLock(); if(!lock.tryLock(1000)) return;
  try {
    const sheet=tab_('Поручения',CFG.taskHeaders), tasks=sheet.getDataRange().getValues();
    const students=rows_('Студенты',CFG.studentHeaders);
    for(let i=1;i<tasks.length;i++) {
      const r=tasks[i],status=String(r[5]||'');
      if(status==='Отправляется') {
        const delivery=deliveryItem_('TASK:'+String(r[0]));
        if(delivery && (delivery.row[3]==='SENT'||(delivery.row[3]==='SENDING'&&delivery.row[4]))) {
          sendOnce_('TASK:'+String(r[0]),delivery.row[1],JSON.parse(delivery.row[2]).text);
          finishTaskDelivery_(sheet,i+1,delivery.row[1],r[0]);
        }
        else log_('Требуется сверка отправки',r[0]||i+1,'Неопределённый результат; автоматический повтор запрещён');
        continue;
      }
      if(status!=='Не отправлено'||!r[1]||!r[2]) continue;
      const matches=students.slice(1).filter(st=>String(st[0]||'').trim().toLowerCase()===String(r[1]).trim().toLowerCase());
      if(matches.length!==1||!matches[0][3]) { log_('Не найден адресат',i+1,'Проверьте справочник'); continue; }
      let id=String(r[0]||'').trim();
      if(!id) { id='T-'+Utilities.getUuid(); sheet.getRange(i+1,1).setValue(id); }
      if(tasks.slice(1).filter(t=>String(t[0])===id).length>1) throw Error('Неоднозначный ID поручения');
      const chatId=String(matches[0][3]);
      if(r[9] && String(r[9])!==chatId) { log_('Адресат изменился',id,'Требуется сверка'); continue; }
      if(!isOwner_(chatId)&&accessStatus_(chatId)!=='approved') continue;
      const deadline=r[4]?(r[4] instanceof Date?Utilities.formatDate(r[4],CFG.timezone,'dd.MM.yyyy'):String(r[4])):'не указан';
      const text='Новое поручение № '+id+'\n\n'+r[2]+'\n\nСрок: '+deadline+'\n\nДля ответа нажмите /tasks.';
      if(text.length>4000) { log_('Поручение слишком длинное',id,'Сократите текст; отправка не выполнена'); continue; }
      try {
        sheet.getRange(i+1,6).setValue('Отправляется'); SpreadsheetApp.flush();
        sendOnce_('TASK:'+id,chatId,text);
        finishTaskDelivery_(sheet,i+1,chatId,id);
      } catch(e) {
        // Never turn a possibly accepted send into a retryable definitive failure.
        log_('Требуется сверка отправки',id,'Проверьте исходящую операцию и Telegram');
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
    const events=calendar_().getEvents(start,end);
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
function registrySheet_() {
  // Order is the existing nine-field positional contract; names must be reviewed explicitly.
  const name=requiredProperty_('ASSISTANT_REGISTRY_SHEET_NAME');
  const headers=JSON.parse(requiredProperty_('ASSISTANT_REGISTRY_HEADERS_JSON'));
  if(!Array.isArray(headers)||headers.length!==9||headers.some(h=>typeof h!=='string'||!h.trim())||new Set(headers).size!==9) throw Error('Требуется контракт из девяти заголовков реестра');
  const book=SpreadsheetApp.openById(requiredProperty_('ASSISTANT_REGISTRY_SPREADSHEET_ID'));
  const sheet=book.getSheetByName(name); if(!sheet) throw Error('Лист реестра не найден');
  const actual=sheet.getRange(1,1,1,9).getValues()[0];
  if(headers.some((h,i)=>actual[i]!==h)) throw Error('Несовместимая схема реестра'); return sheet;
}
function syncGeneralTask_(id,area,task,status,priority,due,context) {
  try {
    withScriptLock_(()=>{
      const sh=registrySheet_(),data=sh.getDataRange().getValues();
      const matches=data.slice(1).map((r,i)=>({row:r,index:i+2})).filter(x=>String(x.row[0])===String(id));
      if(matches.length>1) throw Error('Неоднозначный ID реестра');
      if(matches.length) {
        const index=matches[0].index;
        sh.getRange(index,2,1,5).setValues([[area,task,status,priority,due]]);
        // Column 7 (manual next step) belongs to the owner, never erase it on sync.
        sh.getRange(index,8,1,2).setValues([[context,new Date()]]);
      } else appendOnce_(sh,[id,area,task,status,priority,due,'',context,new Date()]);
      SpreadsheetApp.flush();
    });
  } catch(e) { log_('Ошибка общего реестра',id,'Проверьте конфигурацию, схему и доступ к реестру'); }
}
function updateGeneralTaskStatus_(id,status) {
  try {
    withScriptLock_(()=>{
      const sh=registrySheet_(),data=sh.getDataRange().getValues();
      const matches=data.slice(1).map((r,i)=>({row:r,index:i+2})).filter(x=>String(x.row[0])===String(id));
      if(matches.length!==1) throw Error('ID реестра не найден или неоднозначен');
      sh.getRange(matches[0].index,4).setValue(status);
      sh.getRange(matches[0].index,9).setValue(new Date()); SpreadsheetApp.flush();
    });
  } catch(e) { log_('Ошибка обновления общего реестра',id,'Требуется сверка реестра'); }
}
function timetableSheet_() { return tab_('Расписание НВГУ',CFG.timetableHeaders); }
function timetableSnapshots_() {
  return tab_('Снимки расписания',['ID снимка','URL','HASH','STATUS','CHECKED_AT','TEXT','HTML']);
}
function timetableState_() {
  const snapshots=timetableSnapshots_().getDataRange().getValues();
  if(snapshots.length>1) {
    const r=snapshots[snapshots.length-1];
    return {URL:r[1],HASH:r[2],STATUS:r[3],CHECKED_AT:r[4],TEXT:r[5],HTML:r[6],LAST_SUCCESS_TEXT:r[5]};
  }
  const rows=timetableSheet_().getDataRange().getValues(),out={};
  rows.slice(1).forEach(r=>{if(r[0]) out[String(r[0])]=r[1];}); return out;
}
function saveTimetableState_(obj) {
  return withScriptLock_(()=>{
    // Append complete version first. Never clear a successful previous snapshot.
    timetableSnapshots_().appendRow(['S-'+Utilities.getUuid(),obj.URL||'',obj.HASH||'',obj.STATUS||'',obj.CHECKED_AT||'',String(obj.TEXT||'').slice(0,45000),String(obj.HTML||'').slice(0,45000)]);
    SpreadsheetApp.flush();
  });
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
    saveTimetableState_({URL:CFG.timetableUrl,HASH:fresh.hash,STATUS:'непроверенный снимок страницы',CHECKED_AT:new Date().toISOString(),TEXT:fresh.text.slice(0,45000),HTML:fresh.html.slice(0,45000),LAST_SUCCESS_TEXT:fresh.text.slice(0,45000)});
    if(notify) {
      if(fresh.noSchedule) send_(owner_(),'Получен текст «расписание отсутствует». Неделя и полнота данных не проверены; отсутствие занятий не подтверждено.');
      else if(changed) send_(owner_(),'В расписании НВГУ обнаружены изменения. Проверь сохранённый снимок в листе «Расписание НВГУ» и ссылку: '+CFG.timetableUrl);
      else send_(owner_(),'Текст страницы НВГУ загружен; занятия и неделя не проверены. '+(previousHash?'Изменений не обнаружено.':'Первый снимок сохранён; сравнение начнётся со следующей проверки.')+'\n'+CFG.timetableUrl);
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
    const keyboard=timetableKeyboard_(page.weekLinks);
    send_(chatId,'Непроверенный текст страницы НВГУ (полнота занятий и выбранная неделя не подтверждены).\nПолучено: '+new Date().toISOString()+'\n'+page.text.slice(0,2600)+'\nИсточник: '+page.url,keyboard?{reply_markup:keyboard}:{});
  } catch(e) {
    const state=timetableState_(),last=String(state.LAST_SUCCESS_TEXT||state.TEXT||'');
    send_(chatId,'Не удалось обновить страницу. Снимок может быть устаревшим; выбранная неделя и полнота не подтверждены.\nПоследняя успешная загрузка: '+String(state.CHECKED_AT||'неизвестна')+'\n'+(last?last.slice(0,2200):'Снимка нет.')+'\nИсточник снимка: '+String(state.URL||CFG.timetableUrl));
    log_('Ошибка показа расписания','НВГУ','Не удалось загрузить страницу');
  }
}
function sendTimetableTo_(chatId) {
  // A cached no-schedule phrase is never evidence that there are no classes today.
  return sendTimetablePage_(chatId,CFG.timetableUrl);
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
function calendar_() {
  const cal=CalendarApp.getCalendarById(requiredProperty_('ASSISTANT_CALENDAR_ID'));
  if(!cal) throw Error('Тестовый календарь недоступен'); return cal;
}
function createCalendarEventOnce_(key,title,start,end,description) {
  return withScriptLock_(()=>{
    const cal=calendar_(), sheet=tab_('Операции календаря',['Ключ','Payload JSON','Статус','Event ID','Обновлено']);
    appendOnce_(sheet,[key,JSON.stringify({title,start:start.toISOString(),end:end.toISOString(),description}),'READY','',new Date()]);
    const item=inboxItem_(sheet,key), saved=JSON.parse(String(item.row[1]));
    start=new Date(saved.start); end=new Date(saved.end); title=saved.title;
    if(item.row[3]) {
      const recorded=cal.getEventById(String(item.row[3]));
      if(!recorded) throw Error('Записанное событие не найдено; требуется сверка'); return recorded;
    }
    const marker='[assistant:'+key+']';
    const events=cal.getEvents(start,end);
    const own=events.filter(e=>String(e.getDescription()||'').includes(marker));
    if(own.length>1) throw Error('Найдены дубликаты события; требуется сверка');
    let event=own[0];
    if(!event) {
      if(item.row[2]!=='READY') throw Error('Неопределённый результат создания события: требуется сверка');
      if(events.length) return null;
      // Check again immediately before creation; external calendar editors can still race.
      if(cal.getEvents(start,end).length) return null;
      sheet.getRange(item.index,3).setValue('CREATING'); SpreadsheetApp.flush();
      try { event=cal.createEvent(title,start,end,{description:saved.description+'\n'+marker}); }
      catch(e) { throw Error('Неопределённый результат создания события: требуется сверка'); }
    }
    sheet.getRange(item.index,4).setValue(event.getId());
    sheet.getRange(item.index,3).setValue('CREATED');
    sheet.getRange(item.index,5).setValue(new Date()); SpreadsheetApp.flush(); return event;
  });
}
function ownerCreateEvent_(chatId,raw,messageId) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  const m=raw.match(/^\/event\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(\d{1,3})\s+(.+)$/s);
  if(!m) return send_(chatId,'Формат: /event YYYY-MM-DD HH:MM минуты название');
  const start=parseDateTime_(m[1],m[2]), duration=Number(m[3]),title=m[4].trim();
  if(!start||duration<5||duration>720||!title||start.getTime()<=Date.now()) return send_(chatId,'Проверьте будущую дату, время и длительность (5–720 минут).');
  const key=messageKey_('EVENT',chatId,messageId),end=new Date(start.getTime()+duration*60000);
  const event=createCalendarEventOnce_(key,title,start,end,'Создано по явной команде владельца');
  if(!event) return send_(chatId,'В это время есть пересечение с календарём. Событие не создано.');
  sendOnce_('NOTICE:'+key,chatId,'Добавила событие в Google Календарь: '+title+'\n'+m[1]+' '+m[2]);
}
function studentRequestConsultation_(chatId,name,raw,messageId) {
  const m=raw.match(/^\/consult\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})(?:\s+(\d{1,3}))?\s+(.+)$/s);
  if(!m) return send_(chatId,'Формат: /consult YYYY-MM-DD HH:MM [минуты] тема. Пример: /consult 2026-10-29 14:00 30 Обсуждение статьи');
  const date=parseDateTime_(m[1],m[2]), hm=m[2].split(':').map(Number), duration=Number(m[3]||30), topic=m[4].trim();
  if(!date||hm[0]>23||hm[1]>59||duration<10||duration>180||!topic) return send_(chatId,'Проверь дату, время, длительность (10–180 минут) и тему.');
  const sh=tab_('Заявки на консультации',CFG.consultationHeaders);
  const id=messageKey_('C',chatId,messageId);
  const student=findStudent_(chatId); const displayName=student?String(student.row[0]||name):name;
  appendOnce_(sh,[id,new Date(),displayName,String(chatId),m[1],m[2],duration,topic,'Ожидает решения','','']);
  send_(chatId,'Заявка на консультацию зарегистрирована: '+id+'. Это пока не подтверждённая встреча. Любовь Сергеевна проверит время и сообщит решение.');
  send_(owner_(),'Новая заявка на консультацию\nID: '+id+'\nСтудент: '+displayName+'\nВремя: '+m[1]+' '+m[2]+' ('+duration+' мин)\nТема: '+topic+'\nПодтвердить: /approveconsult '+id+'\nОтклонить: /rejectconsult '+id+' причина');
}
function findConsultation_(id) {
  const sh=tab_('Заявки на консультации',CFG.consultationHeaders), rows=sh.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][0])===String(id)) return {sheet:sh,index:i+1,row:rows[i]};
  return null;
}
function ownerApproveConsultation_(chatId,raw) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  return withScriptLock_(()=>{
    const id=raw.replace(/^\/approveconsult\s*/,'').trim(),item=findConsultation_(id);
    if(!item) return send_(chatId,'Заявка не найдена');
    if(!['Ожидает решения','Обработка — требуется сверка при сбое','Подтверждена'].includes(String(item.row[8]))) return send_(chatId,'Заявка уже обработана: '+item.row[8]);
    if(accessStatus_(String(item.row[3]))!=='approved') return send_(chatId,'Доступ студента не подтверждён; создание запрещено.');
    const start=parseDateTime_(String(item.row[4]),String(item.row[5])),duration=Number(item.row[6]);
    if(!start||!Number.isInteger(duration)||duration<10||duration>180) return send_(chatId,'Некорректная дата или длительность заявки');
    if(start.getTime()<=Date.now()&&!item.row[10]) return send_(chatId,'Время заявки уже прошло; требуется сверка');
    const event=createCalendarEventOnce_('CONSULT:'+id,'Консультация: '+item.row[2],start,new Date(start.getTime()+duration*60000),'Заявка '+id+'; тема: '+item.row[7]+'; подтверждено владельцем');
    if(!event) return send_(chatId,'Нельзя подтвердить: время занято. Предложите другое время.');
    item.sheet.getRange(item.index,11).setValue(event.getId());
    item.sheet.getRange(item.index,10).setValue('Подтверждена владельцем');
    item.sheet.getRange(item.index,9).setValue('Подтверждена'); SpreadsheetApp.flush();
    sendOnce_('CONSULT:'+id+':STUDENT',String(item.row[3]),'Любовь Сергеевна подтвердила консультацию.\nДата: '+String(item.row[4])+' '+String(item.row[5])+'\nТема: '+String(item.row[7]));
    sendOnce_('CONSULT:'+id+':OWNER',chatId,'Консультация подтверждена и добавлена в Google Календарь: '+id);
  });
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
function ownerAssignTask_(chatId,raw,messageId) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  const m=raw.match(/^\/assign\s+(.+?)\s+(\d{4}-\d{2}-\d{2})\s+([\s\S]+)$/);
  if(!m) return send_(chatId,'Формат: /assign Имя Фамилия YYYY-MM-DD текст задания');
  const name=m[1].trim(), due=parseDeadline_(m[2]), task=m[3].trim();
  if(!due||!task) return send_(chatId,'Проверь дату и текст задания.');
  const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>String(r[0]||'').trim().toLowerCase()===name.toLowerCase());
  if(students.length!==1) return send_(chatId,'Найдено адресатов с таким именем: '+students.length+'. Уточни точное имя в листе «Студенты».');
  const st=students[0]; if(!st[3]||!isApprovedNote_(st[5])) return send_(chatId,'Студент не подключён или не одобрен. Поручение не создано.');
  const sh=tab_('Поручения',CFG.taskHeaders), id=messageKey_('T',chatId,messageId);
  appendOnce_(sh,[id,st[0],task,new Date(),due,'Не отправлено','','','',String(st[3]),'']);
  syncGeneralTask_(id,'Студенты',task,'Не отправлено','Обычный',m[2],'Поручение студенту '+st[0]);
  send_(chatId,'Поручение создано: '+id+'\nАдресат: '+st[0]+'\nСрок: '+m[2]+'\nТекст: '+task+'\nОтправка выполнится автоматическим триггером.');
}
function ownerCreateRecurring_(chatId,raw,messageId) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  // Require a visible delimiter between the student's full name and task text;
  // otherwise names and task words cannot be separated reliably.
  const m=raw.match(/^\/repeat\s+(daily|weekly)(?:\s+(ПН|ВТ|СР|ЧТ|ПТ|СБ|ВС))?\s+(.+?)\s+\|\s+([\s\S]+)$/i);
  if(!m) return send_(chatId,'Формат: /repeat daily Имя Фамилия | текст задания или /repeat weekly ПН Имя Фамилия | текст задания. Повтор включится только после /confirmrepeat ID.');
  const cadence=m[1].toLowerCase(), weekday=(m[2]||'').toUpperCase(), rest=m[3].trim(), task=m[4].trim();
  if(cadence==='weekly'&&!weekday) return send_(chatId,'Для weekly укажи день недели: ПН, ВТ, СР, ЧТ, ПТ, СБ или ВС.');
  const students=rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>String(r[0]||'').trim().toLowerCase()===rest.toLowerCase());
  if(students.length!==1) return send_(chatId,'Не удалось однозначно найти студента по имени. Правило не создано.');
  const st=students[0]; if(!st[3]||!isApprovedNote_(st[5])) return send_(chatId,'Студент не подключён или не одобрен. Правило не создано.');
  const sh=tab_('Повторяющиеся поручения',CFG.recurringHeaders), id=messageKey_('R',chatId,messageId);
  appendOnce_(sh,[id,'Черновик',cadence,weekday,st[0],task,1,'',new Date()]);
  send_(chatId,'Повторяющееся поручение создано: '+id+'\nСтудент: '+st[0]+'\nПериодичность: '+(cadence==='daily'?'ежедневно':'еженедельно, '+weekday)+'\nЗадание: '+task+'\nДля включения: /confirmrepeat '+id+'. Без подтверждения черновик не запускается.');
}
function ownerConfirmRecurring_(chatId,raw) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  return withScriptLock_(()=>{
    const id=raw.replace(/^\/confirmrepeat\s*/,'').trim();
    const sh=tab_('Повторяющиеся поручения',CFG.recurringHeaders), item=inboxItem_(sh,id);
    if(item.row[1]==='Да') return send_(chatId,'Правило уже включено: '+id);
    if(item.row[1]!=='Черновик') return send_(chatId,'Правило не является черновиком: '+id);
    sh.getRange(item.index,2).setValue('Да'); SpreadsheetApp.flush();
    send_(chatId,'Правило включено: '+id);
  });
}
function generateRecurringAssignments() { return withScriptLock_(()=>generateRecurringAssignmentsLocked_()); }
function generateRecurringAssignmentsLocked_() {
  const sh=tab_('Повторяющиеся поручения',CFG.recurringHeaders), rows=sh.getDataRange().getValues();
  const now=new Date(), today=dateKey_(now), weekdayNames=['ВС','ПН','ВТ','СР','ЧТ','ПТ','СБ'], todayName=weekdayNames[Number(Utilities.formatDate(now,CFG.timezone,'u'))%7];
  const students=rows_('Студенты',CFG.studentHeaders).slice(1), tasks=tab_('Поручения',CFG.taskHeaders);
  for(let i=1;i<rows.length;i++) {
    const r=rows[i]; if(String(r[1]).toLowerCase()!=='да') continue;
    if(!['daily','weekly'].includes(String(r[2]))) { log_('Некорректное правило',r[0],'Неизвестная периодичность'); continue; }
    if(String(r[2])==='weekly'&&String(r[3]).toUpperCase()!==todayName) continue;
    if(r[7] && dateKey_(r[7] instanceof Date?r[7]:parseDeadline_(String(r[7])||'')||now)===today) continue;
    const matches=students.filter(s=>String(s[0])===String(r[4]));
    if(matches.length!==1||!matches[0][3]||!isApprovedNote_(matches[0][5])) { log_('Повторное поручение пропущено',r[0],'Студент не найден или не одобрен'); continue; }
    const due=new Date(now.getTime()+Math.max(0,Number(r[6]||1))*86400000), id='T-'+Utilities.formatDate(now,CFG.timezone,'yyyyMMdd')+'-'+String(r[0]);
    appendOnce_(tasks,[id,r[4],r[5],now,due,'Не отправлено','','','',String(matches[0][3]),'']);
    syncGeneralTask_(id,'Студенты',String(r[5]),'Не отправлено','Обычный',dateKey_(due),'Повторяющееся правило '+r[0]);
    sh.getRange(i+1,8).setValue(now);
    log_('Создано повторное поручение',id,'Правило '+r[0]);
  }
}
function operationSnapshot_(key,value) {
  const sh=tab_('Снимки операций',['Ключ','Payload JSON','Создано']);
  if(value!==undefined) {
    const json=JSON.stringify(value);
    if(json.length>45000) throw Error('Снимок слишком велик; разделите операцию');
    appendOnce_(sh,[key,json,new Date()]);
  }
  return JSON.parse(String(inboxItem_(sh,key).row[1]));
}
function ownerPrepareBroadcast_(chatId,raw,messageId) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  const text=raw.replace(/^\/broadcast(?:\s|$)/,'').trim();
  if(!text||text.length>3000) return send_(chatId,'Напишите /broadcast и текст до 3000 символов. Сначала будет показан черновик.');
  const id=messageKey_('B',chatId,messageId);
  const recipients=[...new Set(rows_('Студенты',CFG.studentHeaders).slice(1).filter(r=>r[3]&&isApprovedNote_(r[5])).map(r=>String(r[3])))];
  const snapshot=operationSnapshot_('BROADCAST:'+id,{text,recipients});
  appendOnce_(tab_('Рассылки',CFG.broadcastHeaders),[id,new Date(),snapshot.text,'Черновик',snapshot.recipients.length,'','']);
  send_(chatId,'Черновик рассылки '+id+'; адресатов: '+snapshot.recipients.length+'\n\n'+snapshot.text+'\n\nДля отправки: /confirmbroadcast '+id+'. Пока никому ничего не отправлено.');
}
function ownerConfirmBroadcast_(chatId,raw) {
  if(!isOwner_(chatId)) throw Error('Требуются права владельца');
  return withScriptLock_(()=>{
    const id=raw.replace(/^\/confirmbroadcast\s*/,'').trim();
    const sh=tab_('Рассылки',CFG.broadcastHeaders), item=inboxItem_(sh,id);
    if(!['Черновик','Отправка','Отправлено частично'].includes(String(item.row[3]))) return send_(chatId,'Рассылка уже обработана: '+item.row[3]);
    // Legacy drafts without a reviewed recipient snapshot must be recreated, never guessed.
    const snapshot=operationSnapshot_('BROADCAST:'+id);
    sh.getRange(item.index,4).setValue('Отправка');
    if(!item.row[5]) sh.getRange(item.index,6).setValue(new Date()); SpreadsheetApp.flush();
    let sent=0, failed=0;
    for(const target of snapshot.recipients) {
      const key='BROADCAST:'+id+':'+target;
      const previous=deliveryItem_(key);
      if(previous && previous.row[3]==='SENT') { sent++; continue; }
      if(previous && previous.row[3]==='SKIPPED') { failed++; continue; }
      if(accessStatus_(target)!=='approved'&&!isOwner_(target)) {
        if(!previous) appendOnce_(deliverySheet_(),[key,target,JSON.stringify({reason:'Доступ отозван до отправки'}),'SKIPPED','',new Date()]);
        failed++; continue;
      }
      try { sendOnce_(key,target,'Сообщение от Любови Сергеевны:\n\n'+snapshot.text); sent++; }
      catch(e) { failed++; }
    }
    sh.getRange(item.index,5).setValue(snapshot.recipients.length);
    sh.getRange(item.index,7).setValue(new Date());
    sh.getRange(item.index,4).setValue(failed?'Отправлено частично':'Отправлено'); SpreadsheetApp.flush();
    send_(chatId,'Рассылка '+id+': успешно '+sent+', не завершено '+failed+'. Результаты по адресатам — в листе «Исходящие операции»; UNKNOWN/SENDING требуют сверки, повторной отправки нет.');
  });
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
