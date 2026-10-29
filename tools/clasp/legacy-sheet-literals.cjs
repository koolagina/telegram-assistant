'use strict';
// Offline candidate only. Preserve literal strings at the reply projection sinks.
 const replacements=[
 ['new Date(),name,m.from.username', 'new Date(),legacySheetLiteral_(name),m.from.username'],
 ["sheet.appendRow([name,'',username,id", "sheet.appendRow([legacySheetLiteral_(name),'',username,id"],
 [".setValue(name)",".setValue(legacySheetLiteral_(name))"],
 ["sheet.appendRow([key,'Личное',text,", "sheet.appendRow([key,'Личное',legacySheetLiteral_(text),"],
 ["new Date(),type,String(object||''),String(details||'').slice(0,2000)", "new Date(),legacySheetLiteral_(type),legacySheetLiteral_(String(object||'')),legacySheetLiteral_(String(details||'').slice(0,2000))"],
 ['stored.type,stored.description,m.message_id','stored.type,legacySheetLiteral_(stored.description),m.message_id'],
 [".setValue(stored.description||'['+stored.type+']')",".setValue(legacySheetLiteral_(stored.description||'['+stored.type+']'))"],
 [".setValue(content)",".setValue(legacySheetLiteral_(content))"],
 ];
function patchSheetLiterals(source) {
 if(source.includes('function legacySheetLiteral_('))throw Error('Already patched');
 if(source.split('stored.type,stored.description,m.message_id').length!==3)throw Error('Reviewed reply sinks changed');

 for(const [from,to] of replacements){if(!source.includes(from))throw Error('Reviewed sink missing');source=source.split(from).join(to);}
 return source+'\nfunction legacySheetLiteral_(value) {\n  return typeof value===\'string\'&&/^[=\']/.test(value)?"\'"+value:value;\n}\n';
}
function restoreSheetLiterals(source){
 const marker='\nfunction legacySheetLiteral_(value) {';
 const index=source.indexOf(marker);
 if(index<0)throw Error('Exact literal patch required');
 let before=source.slice(0,index);
 for(const [old,value] of replacements.slice().reverse()){
  if(!before.includes(value))throw Error('Exact literal patch required');
  before=before.split(value).join(old);
 }
 if(patchSheetLiterals(before)!==source)throw Error('Exact literal patch required');
 return before;
}
module.exports={patchSheetLiterals,restoreSheetLiterals};
