'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {fixture}=require('./helpers/apps-script.cjs');
const archive=fs.readFileSync('src/archive/telegram_assistant_v1_4_3_reference.gs','utf8');
let parent=archive.replace(/  \/\/ Callback confirmation is best-effort:[\s\S]*?(?=  if\(!isOwner_)/,"  tg_('answerCallbackQuery',{callback_query_id:q.id});\n");
for(const [file,fn] of [['prepare-legacy-candidate','patchMain'],['legacy-file-recovery','patchFileRecovery'],['legacy-update-queue','patchUpdateQueue'],['legacy-reply-recovery','patchReplyRecovery'],['legacy-task-binding','patchTaskBinding']])parent=require('../tools/clasp/'+file+'.cjs')[fn](parent);
const patch=require('../tools/clasp/legacy-sheet-literals.cjs').patchSheetLiterals;
for(const text of ['=1+1','=HYPERLINK("https://invalid.example","x")',"'=literal",'Обычный ответ'])test('reply writes literal text: '+text.slice(0,15),()=>{
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs');vm.runInContext(patch(parent).slice(parent.indexOf('function prop_(')),f.ctx);
 f.ctx.log_=()=>{};f.ctx.send_=()=>({message_id:1});f.ctx.tg_=()=>true;f.ctx.storeFile_=()=>({type:'Текст',description:text,link:''});
 f.sheet('Поручения').rows.push(['T-A','Synthetic','Task','','','Отправлено','','','','1001','']);
 const writes=[];f.setHook((e,n,v)=>{if(e==='append-before'&&n==='Ответы')writes.push(v[5]);if(e==='set-before'&&n==='Поручения'&&v[1]===8)writes.push(v[2]);});
 f.ctx.processMessage_(f.message(text));const expected=/^[=']/.test(text)?"'"+text:text;
 assert.deepEqual(writes,[expected,expected]);
});
test('patch refuses repeated installation and unrelated source drift',()=>{const out=patch(parent);assert.throws(()=>patch(out));assert.throws(()=>patch(parent.replace('stored.description,m.message_id','changed,m.message_id')));new vm.Script(out);});
test('partial reply recovery also writes a literal, using simulated Sheets apostrophe decoding',()=>{
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs');vm.runInContext(patch(parent).slice(parent.indexOf('function prop_(')),f.ctx);
 f.ctx.log_=()=>{};f.ctx.send_=()=>({message_id:1});f.ctx.tg_=()=>true;f.ctx.storeFile_=()=>({type:'Текст',description:'=1+1',link:''});
 f.sheet('Поручения').rows.push(['T-A','Synthetic','Task','','','Отправлено','','','','1001','']);
 let fail=true;const writes=[];f.setHook((e,n,v)=>{
  if(e==='append-before'&&n==='Ответы'){assert.equal(v[5],"'=1+1");v[5]=v[5].slice(1);}
  if(e==='set-before'&&n==='Поручения'&&v[1]===7&&fail){fail=false;throw Error('synthetic date failure');}
  if(e==='set-before'&&n==='Поручения'&&v[1]===8)writes.push(v[2]);
 });
 assert.throws(()=>f.ctx.processMessage_(f.message('=1+1')));f.ctx.processMessage_(f.message('=1+1'));
 assert.deepEqual(writes,["'=1+1"]);assert.equal(f.sheet('Ответы').rows.length,2);
});
