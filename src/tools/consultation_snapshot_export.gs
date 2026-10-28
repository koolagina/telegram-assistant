/** Read-only export helper CANDIDATE. Not installed or invoked on real Sheets.
 * No initialize/tab_/rows_/log_, no triggers/web endpoint, no Calendar or sends.
 * Result contains PRIVATE student data: never log/publish/commit it. Calling on
 * real data requires separate authorization. Caller transfers privately over an
 * authenticated channel; a JSON object alone does not prove its authenticity.
 */
function exportConsultationSnapshotReadOnly(spreadsheetId) {
  try {
    if(typeof spreadsheetId!=='string'||!spreadsheetId.trim()) throw Error('Explicit resource required');
    const observedAt=new Date().toISOString(); // Before reads, not time of UI click.
    const book=SpreadsheetApp.openById(spreadsheetId),zone=book.getSpreadsheetTimeZone();
    if(zone!=='Asia/Yekaterinburg') throw Error('Unknown timezone');
    const name='Заявки на консультации',sheet=book.getSheetByName(name);
    if(!sheet) throw Error('Missing sheet');
    const headers=['ID заявки','Дата создания','Студент','Telegram chat ID','Желаемая дата','Желаемое время','Длительность, мин','Тема','Статус','Решение / причина','ID события календаря'];
    const values=sheet.getDataRange().getValues(); // One complete range read.
    if(!Array.isArray(values)||values.length<1||values.length>10001||!Array.isArray(values[0])||values[0].length!==headers.length||values[0].some((v,i)=>v!==headers[i])) throw Error('Schema mismatch');
    const rows=[];
    for(let index=1;index<values.length;index++) {
      const source=values[index];
      if(!Array.isArray(source)||source.length!==11) throw Error('Incomplete row');
      if(source.every(value=>value==='')) continue; // Empty padding, not a partial row.
      const row=source.map((value,column)=>{
        if(value instanceof Date) {
          if(!Number.isFinite(value.getTime())) throw Error('Invalid date');
          if(column===1) return value.toISOString();
          if(column===4) return Utilities.formatDate(value,zone,'yyyy-MM-dd');
          if(column===5) {
            if(Utilities.formatDate(value,zone,'ss')!=='00'||value.getUTCMilliseconds()!==0) throw Error('Subminute time');
            return Utilities.formatDate(value,zone,'HH:mm');
          }
          throw Error('Unexpected date column');
        }
        if(typeof value==='string'||(typeof value==='number'&&Number.isFinite(value))) return value;
        throw Error('Unsupported cell type');
      });
      rows.push(row);
    }
    return {format_version:1,spreadsheet_id:spreadsheetId,sheet_name:name,headers:headers,rows:rows,observed_at:observedAt,complete:true,timezone:zone};
  } catch(error) { throw Error('Snapshot unavailable; verify source'); }
}
