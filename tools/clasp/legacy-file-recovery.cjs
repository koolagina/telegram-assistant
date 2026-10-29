'use strict';
/** Offline, single-function patch recipe. No Google calls, credential reads or source output. */
const fs=require('node:fs'),path=require('node:path');
const archive=fs.readFileSync(path.join(__dirname,'../../src/archive/telegram_assistant_v1_4_3_reference.gs'),'utf8');
const start=archive.indexOf('function storeFile_('),end=archive.indexOf('function processMessage_(',start);
const original=archive.slice(start,end);
const marker=`  // pollTelegramUpdates serializes this path with its existing ScriptLock.
  // Keep durable receipts: a cache or a filename is not proof of file creation.
  const chatKey=String(message.chat.id), messageKey=String(message.message_id);
  if(!/^-?\\d+$/.test(chatKey)||!/^\\d+$/.test(messageKey)||chatKey.length>24||messageKey.length>24||typeof data.file_id!=='string'||!data.file_id||data.file_id.length>2048)
    throw Error('Некорректный идентификатор вложения');
  const fileKey='KULAGINA_LEGACY_FILE_V1_'+chatKey+'_'+messageKey;
  const props=PropertiesService.getScriptProperties();
  const prior=props.getProperty(fileKey);
  if(prior) {
    let receipt;
    try { receipt=JSON.parse(prior); } catch(error) { throw Error('Требуется проверка операции сохранения файла'); }
    if(receipt.version!==1||receipt.file_id!==data.file_id||receipt.type!==type)
      throw Error('Требуется проверка операции сохранения файла');
    if(receipt.status==='SAVED'&&typeof receipt.link==='string'&&/^https:\\/\\//.test(receipt.link))
      return {type,link:receipt.link,description:label};
    // An uncertain Drive outcome requires review, never a second createFile.
    throw Error('Сохранение файла требует проверки: повторное создание остановлено');
  }
  // Conservative local budget, not a promise about Google's remaining quota.
  // Reserve space for the future SAVED receipt before making an external file.
  const utf8Bytes=value=>encodeURIComponent(String(value)).replace(/%[A-F0-9]{2}/g,'x').length;
  const properties=props.getProperties();
  const used=Object.keys(properties).reduce((n,key)=>n+utf8Bytes(key)+utf8Bytes(properties[key]),0);
  const intent=JSON.stringify({version:1,status:'SENDING',file_id:data.file_id,type});
  if(used+utf8Bytes(fileKey)+8192>350000||utf8Bytes(intent)>6000)
    throw Error('Недостаточно безопасного запаса хранилища подтверждений файлов');
`;
let replacement=original.replace('  try {',marker+'  try {');
replacement=replacement.replace('    const file=folder.createFile(response.getBlob().setName(safeName));',`    const blob=response.getBlob().setName(safeName);
    props.setProperty(fileKey,JSON.stringify({version:1,status:'SENDING',file_id:data.file_id,type}));
    const file=folder.createFile(blob);
    const link=file.getUrl();
    if(typeof link!=='string'||utf8Bytes(link)>2048||!/^https:\\/\\//.test(link)) throw Error('Некорректный результат Drive');
    props.setProperty(fileKey,JSON.stringify({version:1,status:'SAVED',file_id:data.file_id,type,link}));`);
replacement=replacement.replace('return {type,link:file.getUrl(),description:label};','return {type,link,description:label};');
replacement=replacement.replace("    log_('Ошибка файла',message.message_id,e.message);\n    return {type,link:'',description:label+' [Не удалось сохранить файл]'};","    // Do not acknowledge an update whose attachment has not been saved safely.\n    throw Error('Не удалось подтвердить сохранение вложения; требуется проверка');");
function patchFileRecovery(source){
 if(typeof source!=='string'||source.split(original).length!==2||replacement===original)throw Error('Reviewed storeFile_ precondition mismatch');
 return source.replace(original,replacement);
}
module.exports={patchFileRecovery};
