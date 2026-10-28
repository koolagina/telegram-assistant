/**
 * Личный помощник Кулагиной Л. С. — Google Apps Script
 * Версия 1.4.3. Без внешнего ИИ и платных сервисов.
 * Google Sheet: существующая таблица «Поручения студентам».
 *
 * В Script Properties сохранить:
 * TELEGRAM_BOT_TOKEN = токен от BotFather
 * OWNER_CHAT_ID = Telegram chat ID владелицы
 *
 * Новые Telegram-пользователи ожидают одобрения; /approve CHAT_ID Имя Фамилия разрешает доступ.
 * /revoke CHAT_ID отключает доступ. Личные сообщения владельца без выбранного задания записываются на лист «Входящие».
 * Важно: при отправке в Telegram статус «Отправлено» означает
 * принятие сообщения сервером Telegram, а не прочтение человеком.
 */
const CFG = {
  spreadsheetId: '1UHFiOKoqX6ISD39X1B8ka-t8WYvPDYfxAweEvi2_Eeg',
  timezone: 'Asia/Yekaterinburg',
  pollLimit: 50,
  reminderDays: 1,
  maxFileBytes: 18 * 1024 * 1024,
  studentHeaders: ['Студент','Направление / проект','Telegram username','Telegram chat ID','Дата подключения','Примечания'],
  taskHeaders: ['ID поручения','Студент','Задание','Дата выдачи','Срок','Статус','Дата ответа','Ответ / комментарий','Ссылка на файл','Telegram chat ID','Последнее напоминание'],
  replyHeaders: ['Дата и время','Студент','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','ID поручения','Ссылка на файл'],
  personalHeaders: ['ID','Категория','Задача','Срок','Статус','Приоритет','Примечания','Создано'],
  logHeaders: ['Дата','Тип','Объект','Детали']
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
function accessStatus_(chatId) {
  if(isOwner_(chatId)) return 'owner';
  const found=findStudent_(chatId);
  if(!found) return 'unknown';
  const note=String(found.row[5]||'').toLowerCase();
  if(note.includes('доступ отключён')) return 'disabled';
  if(note.includes('одобрен')) return 'approved';
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
  return active.slice(0,20).map(t=>[{text:String(t.row[0]||('Задание '+t.index)).slice(0,40),callback_data:'task:'+t.index}]);
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
    const response=UrlFetchApp.fetch('https://api.telegram.org/file/bot'+token_()+'/'+meta.file_path);
    const folder=DriveApp.getFoldersByName('Файлы Telegram-помощника').next();
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
      : 'Здравствуйте! Здесь вы получаете поручения и отправляете ответы. Для ответа используйте /tasks.');
    return;
  }
  if(/^\/help/.test(raw)) {
    send_(chatId,isOwner_(chatId)
      ? '/plan — личные задачи\n/add текст — добавить задачу\n/done ID — выполнить задачу\n/calendar — события сегодня\n/inbox — личные входящие\n/tasks — поручения\n/replies — ответы\n/brief — сводка\n/approve CHAT_ID Имя Фамилия — разрешить доступ\n/revoke CHAT_ID — отключить доступ'
      : '/tasks — выбрать поручение\nОтправьте текст или файл после выбора поручения.');
    return;
  }
  if(isOwner_(chatId)) {
    if(/^\/approve(?:\s|$)/.test(raw)) return ownerApprove_(chatId,raw);
    if(/^\/revoke(?:\s|$)/.test(raw)) return ownerRevoke_(chatId,raw);
    if(/^\/add(?:\s|$)/.test(raw)) return ownerAdd_(chatId,raw);
    if(/^\/done(?:\s|$)/.test(raw)) return ownerDone_(chatId,raw);
    if(/^\/calendar/.test(raw)) return ownerCalendar_(chatId);
    if(/^\/plan/.test(raw)) return ownerPlan_(chatId);
    if(/^\/brief/.test(raw)) return ownerBrief_(chatId);
    if(/^\/inbox/.test(raw)) return ownerInbox_(chatId);
    if(/^\/replies/.test(raw)) return ownerReplies_(chatId);
    if(/^\/tasks/.test(raw)) return ownerTasks_(chatId);
  } else if(/^\/tasks/.test(raw)) return chooseTask_(chatId);
  if(/^\/\w+/.test(raw)) return send_(chatId,'Неизвестная команда. Напишите /help.');
  // Idempotency check across both response and personal-inbox sheets.
  // This prevents duplicates if Telegram retries an update after a partial failure.
  const messageId=String(m.message_id);
  const alreadyInReplies=rows_('Ответы',CFG.replyHeaders).slice(1)
    .some(r=>String(r[3])===chatId && String(r[6])===messageId);
  const alreadyInInbox=rows_('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']).slice(1)
    .some(r=>String(r[3])===chatId && String(r[6])===messageId);
  if(alreadyInReplies || alreadyInInbox) return;
  const replies=tab_('Ответы',CFG.replyHeaders);
  const stored=storeFile_(m);
  const chosen=prop_('SELECTED_TASK_'+chatId);
  const candidates=activeTasks_(chatId).filter(t=>['Отправлено','В работе','Доработка'].includes(String(t.row[5])));
  let task=candidates.find(t=>String(t.index)===String(chosen))||null;
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
    PropertiesService.getScriptProperties().deleteProperty('SELECTED_TASK_'+chatId);
  }
  send_(chatId,task?'Ответ сохранён по поручению '+taskId+'. Ожидайте проверки.':
    'Сообщение сохранено. Чтобы связать ответ с заданием, используйте /tasks.');
  if(!isOwner_(chatId)) send_(owner_(),'Новый ответ от '+name+(task?' по '+taskId:' (без привязки к заданию)')+
    ': '+(stored.description||'['+stored.type+']').slice(0,400)+(stored.link?'\nФайл: '+stored.link:''));
}
function processCallback_(q) {
  if(!q||!q.message||!q.from) return;
  const id=String(q.message.chat.id), data=String(q.data||'');
  // Callback confirmation is best-effort: Telegram expires callback queries quickly.
  // An expired callback must not block processing or pin the polling offset forever.
  try {
    tg_('answerCallbackQuery',{callback_query_id:q.id});
  } catch(e) {
    log_('Устаревший callback',q.id,e.message||String(e));
  }
  if(!isOwner_(id) && accessStatus_(id)!=='approved') { send_(id,'Доступ к поручениям не разрешён.'); return; }
  if(!data.startsWith('task:')) return;
  const rowIndex=Number(data.split(':')[1]);
  const s=tab_('Поручения',CFG.taskHeaders);
  if(!Number.isInteger(rowIndex)||rowIndex<2||rowIndex>s.getLastRow()) return;
  const r=s.getRange(rowIndex,1,1,11).getValues()[0];
  if(String(r[9])!==id || !['Отправлено','В работе','Доработка'].includes(String(r[5]))) {
    send_(id,'Это поручение сейчас недоступно для ответа.'); return;
  }
  PropertiesService.getScriptProperties().setProperty('SELECTED_TASK_'+id,String(rowIndex));
  send_(id,'Выбрано поручение '+taskId_(r,rowIndex)+'. Теперь отправьте ответ или файл.');
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
        log_('Ошибка входящего',u.update_id,e.stack||e.message);
        // Do not advance the offset past a failed update: retry on next poll.
        // Processing is idempotent for ordinary messages via chat/message ID.
        try { send_(owner_(),'Ошибка обработки сообщения Telegram (update '+u.update_id+'): '+String(e.message||e).slice(0,500)); } catch(_) {}
        break;
      }
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
      } catch(e) {
        sheet.getRange(i+1,6).setValue('Ошибка отправки');
        log_('Ошибка отправки',id,e.message);
      }
    }
  } finally { lock.releaseLock(); }
}
function dateKey_(d) { return Utilities.formatDate(d,CFG.timezone,'yyyy-MM-dd'); }
function remindDeadlines() {
  const sheet=tab_('Поручения',CFG.taskHeaders);
  const rows=sheet.getDataRange().getValues(), now=new Date(), today=dateKey_(now);
  for(let i=1;i<rows.length;i++) {
    const r=rows[i],status=String(r[5]||''),chatId=String(r[9]||'');
    if(!chatId||(!isOwner_(chatId) && accessStatus_(chatId)!=='approved')||!['Отправлено','В работе','Доработка'].includes(status)) continue;
    let dueDate=null;
    if(r[4] instanceof Date) dueDate=r[4];
    else if(typeof r[4]==='string' && r[4].trim()) {
      const m=r[4].trim().match(/^(\d{1,2})[.\/-](\d{1,2})[.\/-](\d{4})$/);
      if(m) dueDate=new Date(Number(m[3]),Number(m[2])-1,Number(m[1]));
    }
    if(!dueDate || isNaN(dueDate.getTime()) || dueDate.getFullYear()<2000) continue;
    const due=dateKey_(dueDate), days=Math.round((Date.parse(due+'T12:00:00Z')-Date.parse(today+'T12:00:00Z'))/86400000);
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
function ownerAdd_(id,raw) {
  const text=raw.replace(/^\/add(?:\s+|$)/,'').trim();
  if(!text) return send_(id,'Напишите: /add Купить корм Уле');
  const sheet=tab_('Личные задачи',CFG.personalHeaders);
  const key='L-'+Utilities.formatDate(new Date(),CFG.timezone,'yyyyMMdd-HHmmss')+
    '-'+Math.floor(Math.random()*1000);
  sheet.appendRow([key,'Личное',text,'','Открыто','Обычный','',new Date()]);
  send_(id,'Добавила задачу '+key+': '+text);
}
function ownerDone_(id,raw) {
  const key=raw.replace(/^\/done(?:\s+|$)/,'').trim();
  if(!key) return send_(id,'Укажите ID задачи из /plan: /done L-...');
  const sheet=tab_('Личные задачи',CFG.personalHeaders);
  const rows=sheet.getDataRange().getValues();
  for(let i=1;i<rows.length;i++) if(String(rows[i][0])===key) {
    sheet.getRange(i+1,5).setValue('Выполнено');
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
  const overdue=rows.filter(r=>r[4] instanceof Date&&dateKey_(r[4])<dateKey_(new Date())&&
    ['Отправлено','В работе','Доработка'].includes(String(r[5])));
  send_(id,'Сводка\nНа проверке: '+review.length+'\nПросрочено: '+overdue.length+
    '\n\n'+review.slice(0,10).map(r=>'• '+r[1]+': '+r[2]).join('\n'));
}
function sendDailyBriefing() {
  ownerBrief_(owner_());
  ownerCalendar_(owner_());
  ownerPlan_(owner_());
}
function setupAutomation() {
  initialize();
  owner_(); token_();
  tg_('deleteWebhook',{drop_pending_updates:false});
  const handlers=['pollTelegramUpdates','sendPendingTasks','remindDeadlines','sendDailyBriefing'];
  ScriptApp.getProjectTriggers().forEach(t=>{
    if(handlers.includes(t.getHandlerFunction())) ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('pollTelegramUpdates').timeBased().everyMinutes(1).create();
  ScriptApp.newTrigger('sendPendingTasks').timeBased().everyMinutes(5).create();
  ScriptApp.newTrigger('remindDeadlines').timeBased().everyDays(1).atHour(9).inTimezone(CFG.timezone).create();
  ScriptApp.newTrigger('sendDailyBriefing').timeBased().everyDays(1).atHour(7).inTimezone(CFG.timezone).create();
  log_('Настройка','Автоматизация','Триггеры установлены');
}
