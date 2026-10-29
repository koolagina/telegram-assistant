'use strict';
/** Offline candidate only. No clasp/OAuth/Google/Telegram invocations. */
const systemFs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),crypto=require('node:crypto');
const {createPrivateDirectory}=require('./prepare-backup.cjs');
// Public integrity digests of the reviewed eight-file upload; not credentials.
const EXPECTED=Object.freeze({
 'Код.js':'8ac32d007bab7f7eacccbc68b5c5c97bf62d2866bac6a9e4a6086f4cd9c6db44',
 'appsscript.json':'3c53d11d77bd4158a29f7fe2247a8c83a4957ffb07b1cf4d03d902958511c3df',
 'ТестСообщения.js':'79163eecf481134e0c135319e1869521353f47aff522d7001a978887a19f399f',
 'ТестКалендаря.js':'0417c9601ab2621029198c539987be0a0a5665dd270a788eb20d01ea100a1961',
 'СверкаРасписания.js':'a83a9dbd8438d9c5fe5e40a5e2e8e13127f893d1ec0c7612560ae32a192ee7af',
 'ПроверкаКалендаря.js':'5959528494f20cf9e664b14e50f42567175183672e0505bf6f7143df37b11867',
 'ПроверкаЗащитыРасписания.js':'8f8b4cea58583ffa20bd891e2e2cc6b88dafd855e41ab915ed6d2e7c207eca55',
 'ПроверкаПодключения.js':'0211b4a84bae55f206212f024a25000a20ca7625df3cd8bc8d75b477a8b8f8f1'
});
const REPLACEMENTS=Object.freeze([
  ["if(note.includes('одобрен')) return 'approved';","if(note.trim()==='одобрен') return 'approved';"],
  ["  tg_('answerCallbackQuery',{callback_query_id:q.id});", "  // An expired ACK must not block this or subsequent Telegram updates.\n  try { tg_('answerCallbackQuery',{callback_query_id:q.id}); }\n  catch(e) { log_('Устаревший callback',q.id,'Подтверждение кнопки недоступно'); }"]
 ].map(Object.freeze));
function patchMain(source) {
 for(const [old] of REPLACEMENTS)if(source.split(old).length!==2)throw Error('Source patch precondition mismatch; review required');
 for(const [old,replacement] of REPLACEMENTS)source=source.replace(old,replacement);
 return source;
}
function prepareCandidate({backup,destination,expected=EXPECTED,platform=process.platform,run,fs=systemFs}) {
 if(typeof backup!=='string'||!path.isAbsolute(backup))throw Error('Absolute backup required');
 backup=path.resolve(backup);
 // Read only explicit source files; do not read auth or target config values.
 for(let p=backup;;p=path.dirname(p)){
  if(fs.lstatSync(p).isSymbolicLink())throw Error('Symlink source forbidden');
  if(path.dirname(p)===p)break;
 }
 const names=Object.keys(expected),entries=fs.readdirSync(backup);
 if(names.length!==8||!names.includes('Код.js')||!names.includes('appsscript.json'))throw Error('Reviewed eight-file set required');
 if(entries.some(n=>!names.includes(n)&&n!=='.clasp.json'))throw Error('Unreviewed source files; stop for comparison');
 const contents={};
 for(const n of names){
  if(path.basename(n)!==n)throw Error('Invalid reviewed filename');
  const p=path.join(backup,n),stat=fs.lstatSync(p);
  if(!stat.isFile()||stat.isSymbolicLink()||stat.size>2*1024*1024)throw Error('Invalid source file');
  const bytes=fs.readFileSync(p);
  if(crypto.createHash('sha256').update(bytes).digest('hex')!==expected[n])throw Error('Backup differs from reviewed snapshot; do not overwrite or retry blindly');
  contents[n]=bytes;
 }
 if(entries.includes('.clasp.json')&&!fs.lstatSync(path.join(backup,'.clasp.json')).isFile())throw Error('Invalid local project config');
 JSON.parse(contents['appsscript.json'].toString('utf8'));
 contents['Код.js']=Buffer.from(patchMain(contents['Код.js'].toString('utf8')));
 const scripts=names.filter(n=>n.endsWith('.js')).map(n=>contents[n].toString('utf8'));
 const code=scripts.join('\n'),functions=[...code.matchAll(/^function\s+(\w+)\s*\(/gm)].map(m=>m[1]);
 if(new Set(functions).size!==functions.length)throw Error('Global function collision');
 try{new vm.Script(code);}catch{throw Error('Candidate syntax failed; no source output created');}
 // Private directory/ACL is established before writing any working source.
 destination=createPrivateDirectory({destination,platform,run,fs});
 for(const n of names)fs.writeFileSync(path.join(destination,n),contents[n],{mode:0o600,flag:'wx'});
 return {prepared:true,files:names.length,changed_files:1,patches:2,global_functions:functions.length,remote_access_performed:false,ready_for_push:false};
}
module.exports={EXPECTED,REPLACEMENTS,patchMain,prepareCandidate};
if(require.main===module){try{const args=process.argv.slice(2);if(args.length!==4||args[0]!=='--backup'||args[2]!=='--destination')throw Error('Usage: node prepare-legacy-candidate.cjs --backup ABSOLUTE_BACKUP --destination ABSOLUTE_NEW_CANDIDATE');console.log(JSON.stringify(prepareCandidate({backup:args[1],destination:args[3]})));}catch{console.error('Candidate preparation stopped. Verify the original reviewed backup, fresh private destination and local permissions. No remote operation performed; do not use partial output.');process.exitCode=1;}}
