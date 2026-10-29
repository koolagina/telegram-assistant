/** Standalone test adapter. NOT installed or authorized for execution by its presence.
 * A first run creates ONE separate test workbook; never opens the bot workbook.
 * No deletion, messages, Calendar, polling or triggers. Keep the test workbook for review.
 * Persist intent before create: an unknown create outcome requires manual review, not retry.
 */
function testKulaginaSheetLiteralRoundTrip() {
  const report={status:'not_started',test_only:true,created:false,round_trip_verified:false,
    formulas_absent:false,messages_sent:0,polling_started:false,cleanup_required:false};
  const key='KULAGINA_SHEET_LITERAL_PROBE_V1',title='TEST — Kulagina — Sheets literals';
  const values=['=1+1','=HYPERLINK("https://invalid.example","x")',"'=literal","''two",'Обычный ответ',''];
  const lock=LockService.getScriptLock();
  if(!lock.tryLock(1000)){report.status='busy';return report;}
  try {
    const props=PropertiesService.getScriptProperties();
    const saved=props.getProperty(key);
    let book;
    if(saved){
      report.cleanup_required=true;
      const receipt=JSON.parse(saved);
      if(receipt.version!==1||receipt.status!=='SAVED'||typeof receipt.id!=='string'||!receipt.id)
        throw Error('review');
      book=SpreadsheetApp.openById(receipt.id);
      if(book.getName()!==title)throw Error('review');
    }else{
      props.setProperty(key,JSON.stringify({version:1,status:'SENDING'}));
      report.cleanup_required=true;
      book=SpreadsheetApp.create(title,values.length,2);
      report.created=true;report.cleanup_required=true;
      const sheet=book.getSheets()[0];sheet.setName('Literal probe');
      // Match the candidate encoder. Do not change source fixtures or real data.
      const encode=value=>/^[=']/.test(value)?"'"+value:value;
      for(let i=0;i<values.length;i++){
        sheet.appendRow([encode(values[i]),'']);
        sheet.getRange(i+1,2).setValue(encode(values[i]));
      }
      SpreadsheetApp.flush();
      props.setProperty(key,JSON.stringify({version:1,status:'SAVED',id:book.getId()}));
    }
    report.cleanup_required=true;
    const sheets=book.getSheets();
    if(sheets.length!==1||sheets[0].getName()!=='Literal probe')throw Error('review');
    const range=sheets[0].getRange(1,1,values.length,2);
    const actual=range.getValues(),formulas=range.getFormulas();
    report.round_trip_verified=actual.length===values.length&&actual.every((row,i)=>row.length===2&&row.every(v=>v===values[i]));
    report.formulas_absent=formulas.length===values.length&&formulas.every(row=>row.length===2&&row.every(v=>v===''));
    report.status=report.round_trip_verified&&report.formulas_absent?'verified':'review_required';
  }catch(error){report.status='review_required';} // Never emit raw IDs, data or exceptions.
  finally{lock.releaseLock();}
  console.log(JSON.stringify(report));
  return report;
}
