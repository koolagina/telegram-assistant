'use strict';
// Offline candidate only. Preserve literal strings at the reply projection sinks.
function patchSheetLiterals(source) {
 if(source.includes('function legacySheetLiteral_('))throw Error('Already patched');
 if(source.split('stored.type,stored.description,m.message_id').length!==3)throw Error('Reviewed reply sinks changed');
 const replacements=[
 ['stored.type,stored.description,m.message_id','stored.type,legacySheetLiteral_(stored.description),m.message_id'],
 [".setValue(stored.description||'['+stored.type+']')",".setValue(legacySheetLiteral_(stored.description||'['+stored.type+']'))"],
 [".setValue(content)",".setValue(legacySheetLiteral_(content))"],
 ];
 for(const [from,to] of replacements){if(!source.includes(from))throw Error('Reviewed sink missing');source=source.split(from).join(to);}
 return source+'\nfunction legacySheetLiteral_(value) {\n  return typeof value===\'string\'&&/^[=\']/.test(value)?"\'"+value:value;\n}\n';
}
module.exports={patchSheetLiterals};
