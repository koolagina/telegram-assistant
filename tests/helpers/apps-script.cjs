const fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
function fixture(candidate='src/telegram_assistant_v2_0_4_candidate.gs') {
 const code=fs.readFileSync(path.join(root,candidate),'utf8');
 const tables=new Map(), files=[], sent=[], properties=new Map([['OWNER_CHAT_ID','9001'],['TELEGRAM_BOT_TOKEN','test-only'],['ASSISTANT_SPREADSHEET_ID','sandbox-book'],['ASSISTANT_DRIVE_FOLDER_ID','sandbox-folder']]);
 let hook=()=>{}, held=false, busy=false, creates=0, downloads=0;
 const clone=x=>x.map(r=>r.slice());
 function sheet(name,headers=[]) {
  if(tables.has(name))return tables.get(name);
  const rows=[headers.slice()];
  const s={rows,getDataRange:()=>({getValues:()=>clone(rows)}),getLastRow:()=>rows.some(r=>r.some(v=>v!==''))?rows.length:0,getLastColumn:()=>Math.max(0,...rows.map(r=>r.length)),setFrozenRows(){},clearContents(){rows.splice(0,rows.length,[]);},appendRow(r){hook('append-before',name,r);rows.push(r.slice());hook('append-after',name,r);return s;},getRange(row,col,n=1,m=1){return {getValues:()=>Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>rows[row+i-1]?.[col+j-1]??'')),setValue(v){hook('set-before',name,[row,col,v]);while(rows.length<row)rows.push([]);rows[row-1][col-1]=v;hook('set-after',name,[row,col,v]);},setValues(values){for(let i=0;i<n;i++)for(let j=0;j<m;j++)thisSet(row+i,col+j,values[i][j]);},setDataValidation(){}};}};
  function thisSet(r,c,v){s.getRange(r,c).setValue(v);}
  tables.set(name,s);return s;
 }
 const iterator=items=>{let i=0;return {hasNext:()=>i<items.length,next:()=>items[i++]};};
 const folder={getSharingAccess:()=> 'PRIVATE',getFilesByName:n=>iterator(files.filter(f=>f.name===n)),createFile(blob){hook('create-before');creates++;const f={name:blob.name,getUrl:()=> 'mock://file/'+creates,getSize:()=>10};files.push(f);hook('create-after');return f;}};
 const book={getSheetByName:n=>tables.get(n)||null,insertSheet:n=>sheet(n),getSheets:()=>[...tables.values()]};
 const lock={hasLock:()=>held,tryLock:()=>{if(busy)return false;held=true;return true;},releaseLock:()=>{held=false;}};
 const util={DigestAlgorithm:{SHA_256:'sha256'},getUuid:()=>crypto.randomUUID(),computeDigest:(_,s)=>[...crypto.createHash('sha256').update(s).digest()],newBlob:s=>({getBytes:()=>[...Buffer.from(s)]}),parseDate:(s,tz,fmt)=>new Date(s.replace(' ','T')+(fmt.includes('HH')?':00+05:00':'T00:00:00+05:00')),formatDate(d,tz,fmt){const x=new Date(d.getTime()+18000000),z=n=>String(n).padStart(2,'0'), y=x.getUTCFullYear(),m=z(x.getUTCMonth()+1),day=z(x.getUTCDate()),h=z(x.getUTCHours()),min=z(x.getUTCMinutes()),sec=z(x.getUTCSeconds());return {'yyyy-MM-dd':`${y}-${m}-${day}`,'yyyyMMdd':`${y}${m}${day}`,'yyyyMMdd-HHmmss':`${y}${m}${day}-${h}${min}${sec}`,'yyyy-MM-dd HH:mm':`${y}-${m}-${day} ${h}:${min}`,'u':String(x.getUTCDay()||7)}[fmt]||`${day}.${m}.${y}`;}};
 const NativeDate=Date;
 class ClockDate extends NativeDate { constructor(...args){super(...(args.length?args:['2026-10-26T07:00:00Z']));} static now(){return NativeDate.parse('2026-10-26T07:00:00Z');} static [Symbol.hasInstance](value){return value instanceof NativeDate;} }
 const ctx=vm.createContext({Date:ClockDate,console,Utilities:util,LockService:{getScriptLock:()=>lock},PropertiesService:{getScriptProperties:()=>({getProperty:k=>properties.get(k)||null,getKeys:()=>[...properties.keys()],setProperty(k,v){hook('property-before',k,v);properties.set(k,v);},deleteProperty:k=>properties.delete(k)})},CacheService:{getScriptCache:()=>({get:()=>null,put(){}})},SpreadsheetApp:{openById:id=>{hook('open',id);return book;},flush:()=>hook('flush')},DriveApp:{Access:{PRIVATE:'PRIVATE'},getFolderById:()=>folder,getFoldersByName:()=>iterator([folder])},UrlFetchApp:{fetch(){downloads++;hook('download');return {getResponseCode:()=>200,getBlob:()=>({name:'',getBytes:()=>Array(10).fill(0),setName(n){this.name=n;return this;}})};}}});
 vm.runInContext(code,ctx,{filename:candidate});
 const cfg=vm.runInContext('CFG',ctx);
 for(const [name,key] of [['Студенты','studentHeaders'],['Поручения','taskHeaders'],['Ответы','replyHeaders'],['Личные задачи','personalHeaders'],['Заявки на консультации','consultationHeaders'],['Повторяющиеся поручения','recurringHeaders'],['Рассылки','broadcastHeaders']]) sheet(name,Array.from(cfg[key]));
 sheet('Входящие',['Дата и время','Имя','Telegram username','Telegram chat ID','Тип сообщения','Текст / подпись','Telegram message ID','Ссылка на файл']);
 sheet('Студенты').rows.push(['Иван Петров','','','1001','','Одобрен'],['Владелец теста','','','9001','','Одобрен']);
 const registry={sync:ctx.syncGeneralTask_,update:ctx.updateGeneralTaskStatus_};
 ctx.log_=()=>{};ctx.syncGeneralTask_=()=>{};ctx.updateGeneralTaskStatus_=()=>{};
 ctx.send_=(id,text,extra)=>{hook('send',String(id),text);sent.push(extra===undefined?[String(id),text]:[String(id),text,extra]);return {message_id:sent.length};};ctx.tg_=(method)=>{if(method==='getFile')return {file_path:'fixture.bin'};throw Error('Unexpected Telegram '+method);};
 const message=(text,id=11,owner=false)=>({chat:{id:owner?'9001':'1001',type:'private'},from:{id:owner?'9001':'1001'},message_id:id,text});
 return {ctx,cfg,sheet,files,sent,properties,message,lock,registry,setHook:f=>hook=f,setBusy:v=>busy=v,get creates(){return creates;},get downloads(){return downloads;}};
}
module.exports={fixture};
