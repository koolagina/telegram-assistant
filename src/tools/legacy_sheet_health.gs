/** Read-only metadata probe for the installed legacy bot, NOT a poller or setup.
 * Read only expected header cells. Never use tab_ (it can create/repair sheets).
 * No user rows, tokens, file operations, writes, triggers or Telegram calls.
 */
function probeKulaginaLegacySheetsReadOnly() {
  const report={format_version:1,mode:'read_only_sheet_headers',status:'not_configured',
    access_verified:false,schemas_verified:false,sheets:{},writes:0,messages_sent:0,polling_started:false};
  if(typeof CFG==='undefined'||typeof CFG.spreadsheetId!=='string'||!CFG.spreadsheetId)return report;
  const expected={students:['Студенты',CFG.studentHeaders],tasks:['Поручения',CFG.taskHeaders],replies:['Ответы',CFG.replyHeaders],
    incoming:['Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']],
    updates:['Очередь updates',['Ключ','Статус','Попытки','Payload JSON','Обновлено','Ошибка']],
    snapshots:['Снимки операций',['Ключ','Payload JSON','Создано']],
    notifications:['Уведомления ответов',['Ключ','Payload JSON','Статус','Telegram message ID','Обновлено','Ошибка']]};
  if(Object.keys(expected).some(k=>!Array.isArray(expected[k][1])||!expected[k][1].length))return report;
  let book;
  try{book=SpreadsheetApp.openById(CFG.spreadsheetId);report.access_verified=true;}
  catch(error){report.status='access_or_resource_unavailable';return report;}
  for(const key of Object.keys(expected)){
    const [name,headers]=expected[key];
    try{
      const sh=book.getSheetByName(name);
      if(!sh){report.sheets[key]='missing';continue;}
      const actual=sh.getRange(1,1,1,headers.length).getValues();
      report.sheets[key]=Array.isArray(actual)&&actual.length===1&&Array.isArray(actual[0])&&actual[0].length===headers.length&&headers.every((v,i)=>String(actual[0][i])===v)?'compatible':'schema_mismatch';
    }catch(error){report.sheets[key]='unavailable';}
  }
  report.schemas_verified=Object.keys(expected).every(k=>report.sheets[k]==='compatible');
  report.status=report.schemas_verified?'verified':'review_required';
  return report;
}
function showKulaginaLegacySheetHealth() {
  console.log(JSON.stringify(probeKulaginaLegacySheetsReadOnly()));
}
