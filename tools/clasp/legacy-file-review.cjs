'use strict';
/** Local, read-only review of an explicitly filtered receipt list. No network or repair actions. */
const crypto=require('node:crypto');
const KEY=/^KULAGINA_LEGACY_FILE_V1_-?\d{1,24}_\d{1,24}$/;
function reviewReceipts(records){
 if(!Array.isArray(records)||records.length>1000)throw Error('Bounded filtered receipt list required');
 const seen=new Set(),counts={saved:0,unknown:0,invalid:0},operations=[];
 for(const record of records){
  if(!record||typeof record.key!=='string'||!KEY.test(record.key)||typeof record.value!=='string'||seen.has(record.key))throw Error('Invalid or duplicate filtered receipt record');
  seen.add(record.key);let r=null;
  if(Buffer.byteLength(record.value,'utf8')<=8192)try{r=JSON.parse(record.value);}catch{}
  const base=r&&typeof r==='object'&&!Array.isArray(r)&&r.version===1&&typeof r.file_id==='string'&&r.file_id.length>0&&r.file_id.length<=2048&&['Документ','Видео','Аудио','Голосовое','Фото'].includes(r.type);
  let state='invalid',action='manual_receipt_review';
  if(base&&r.status==='SENDING'&&Object.keys(r).sort().join('|')==='file_id|status|type|version'){state='unknown';action='manual_drive_and_source_review';}
  if(base&&r.status==='SAVED'&&typeof r.link==='string'&&/^https:\/\//.test(r.link)&&Buffer.byteLength(r.link,'utf8')<=2048&&Object.keys(r).sort().join('|')==='file_id|link|status|type|version'){state='saved';action='verify_file_and_sheet_before_replay';}
  counts[state]++;operations.push({operation_sha256:crypto.createHash('sha256').update(record.key).digest('hex'),state,action});
 }
 return {format_version:1,mode:'offline_filtered_receipt_review',counts,operations,drive_verified:false,sheet_verified:false,ready_for_apply:false,writes:0};
}
module.exports={reviewReceipts};
if(require.main===module){try{const fs=require('node:fs'),path=require('node:path'),args=process.argv.slice(2);if(args.length!==1||!path.isAbsolute(args[0]))throw Error('Explicit absolute receipt file required');const st=fs.lstatSync(args[0]);if(!st.isFile()||st.isSymbolicLink()||st.size>2000000)throw Error('Invalid input file');console.log(JSON.stringify(reviewReceipts(JSON.parse(fs.readFileSync(args[0],'utf8')))));}catch{console.error('Receipt review stopped. Use only an explicitly filtered local receipt list; do not share properties or credentials.');process.exitCode=1;}}
