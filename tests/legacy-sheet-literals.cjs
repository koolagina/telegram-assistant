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
// This is an explicit model of Sheets input-prefix handling, not an integration test.
function literalFixture(text,owner=false) {
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs');
 vm.runInContext(patch(parent).slice(parent.indexOf('function prop_(')),f.ctx);
 f.ctx.log_=()=>{};f.ctx.send_=()=>({message_id:1});f.ctx.tg_=()=>true;
 let stores=0;
 f.ctx.storeFile_=()=>{stores++;return {type:'Текст',description:text,link:''};};
 if(!owner)f.sheet('Поручения').rows.push(['T-A','Synthetic','Task','','','Отправлено','','','','1001','']);
 const writes=[];let inject=()=>{};
 const decode=value=>typeof value==='string'&&value.startsWith("'")?value.slice(1):value;
 f.setHook((event,name,value)=>{
  if(event==='append-before'&&['Ответы','Входящие'].includes(name)){
   writes.push(value[5]);value[5]=decode(value[5]);
  }
  if(event==='set-before'&&name==='Поручения'&&value[1]===8)writes.push(value[2]);
  if(event==='set-after'&&name==='Поручения'&&value[1]===8)f.sheet(name).rows[value[0]-1][7]=decode(value[2]);
  inject(event,name,value);
 });
 return {f,writes,get stores(){return stores;},failWith(fn){inject=fn;},message:()=>f.message(text,11,owner)};
}
for(const text of ['=1+1',"'=literal","''two",'обычный ответ']) {
 for(const column of [7,8,9])test('retry preserves original text and does not re-escape after column '+column+' failure: '+text,()=>{
  const x=literalFixture(text);let once=true;
  x.failWith((e,n,v)=>{if(once&&e==='set-before'&&n==='Поручения'&&v[1]===column){once=false;throw Error('synthetic failure');}});
  // Column 9 is only used for attachments; provide a synthetic saved link.
  if(column===9){const original=x.f.ctx.storeFile_;x.f.ctx.storeFile_=()=>({...original(),type:'Документ',link:'https://drive.invalid/synthetic'});}
  assert.throws(()=>x.f.ctx.processMessage_(x.message()));x.failWith(()=>{});
  x.f.ctx.processMessage_(x.message());x.f.ctx.processMessage_(x.message());
  assert.equal(x.f.sheet('Ответы').rows.length,2);
  assert.equal(x.f.sheet('Ответы').rows[1][5],text);
  assert.equal(x.f.sheet('Поручения').rows[1][7],text);
  assert.equal(x.f.sheet('Поручения').rows[1][5],'Ответ получен');
  assert.equal(x.stores,1);
  assert.ok(x.writes.every(value=>value===(/^[=']/.test(text)?"'"+text:text)));
 });
 test('owner inbox replay keeps literal text without another upload: '+text,()=>{
  const x=literalFixture(text,true);x.f.ctx.processMessage_(x.message());x.f.ctx.processMessage_(x.message());
  assert.equal(x.f.sheet('Входящие').rows.length,2);assert.equal(x.f.sheet('Входящие').rows[1][5],text);
  assert.equal(x.stores,1);assert.equal(x.writes.length,1);
 });
}
