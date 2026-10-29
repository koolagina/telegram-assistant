'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm');
const {fixture}=require('./helpers/apps-script.cjs'),{currentSource}=require('./helpers/legacy-current-source.cjs');
const patch=require('../tools/clasp/legacy-reply-notifications.cjs').patchReplyNotifications;
function make(){
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs');vm.runInContext(patch(currentSource()).slice(currentSource().indexOf('function prop_(')),f.ctx);
 f.ctx.log_=()=>{};let stores=0;f.ctx.storeFile_=()=>{stores++;return {type:'Текст',description:'Synthetic answer',link:''};};
 f.sheet('Поручения').rows.push(['T-A','Synthetic','Task','','','Отправлено','','','','1001','']);
 return {f,get stores(){return stores;}};
}
test('student API failure cannot silently suppress owner notification on replay',()=>{
 const x=make(),{f}=x,calls=[];f.ctx.send_=(id)=>{calls.push(String(id));if(String(id)==='1001')throw Error('synthetic unknown result');return {message_id:91};};
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));
 try{f.ctx.processMessage_(f.message('Synthetic answer'));}catch{}
 assert.equal(calls.filter(x=>x==='9001').length,1);assert.equal(calls.filter(x=>x==='1001').length,1);
 assert.equal(f.sheet('Ответы').rows.length,2);assert.equal(x.stores,1);
});
test('reply projection failure before notifications resumes the planned sends exactly once locally',()=>{
 const x=make(),{f}=x,calls=[];f.ctx.send_=(id)=>{calls.push(String(id));return {message_id:90+calls.length};};let fail=true;
 f.setHook((e,n,v)=>{if(fail&&e==='set-before'&&n==='Поручения'&&v[1]===7){fail=false;throw Error('synthetic partial write');}});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));f.setHook(()=>{});
 f.ctx.processMessage_(f.message('Synthetic answer'));f.ctx.processMessage_(f.message('Synthetic answer'));
 assert.deepEqual(calls,['1001','9001']);assert.equal(x.stores,1);assert.equal(f.sheet('Ответы').rows.length,2);
});
test('API confirmations are retained and repeated update sends nothing',()=>{
 const {f}=make();let calls=0;f.ctx.send_=()=>({message_id:++calls});f.ctx.processMessage_(f.message('Synthetic answer'));f.ctx.processMessage_(f.message('Synthetic answer'));
 assert.equal(calls,2);const rows=f.sheet('Уведомления ответов').rows.slice(1);assert.ok(rows.every(r=>r[2]==='API_CONFIRMED'));assert.ok(rows.every(r=>Number(r[3])>0));
});
test('accepted send with failed receipt never automatically sends the message again',()=>{
 const {f}=make();const calls=[];f.ctx.send_=id=>{calls.push(String(id));return {message_id:90+calls.length};};let fail=true;
 f.setHook((e,n,v)=>{if(fail&&e==='set-before'&&n==='Уведомления ответов'&&v[0]>1&&v[1]===4){fail=false;throw Error('synthetic receipt failure');}});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));f.setHook(()=>{});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.deepEqual(calls,['1001','9001']);
 assert.equal(f.sheet('Уведомления ответов').rows[1][2],'UNKNOWN');
});
test('claim accepted then throws prevents an uncertain second send and still handles owner',()=>{
 const {f}=make(),calls=[];f.ctx.send_=id=>{calls.push(String(id));return {message_id:20};};let fail=true;
 f.setHook((e,n,v)=>{if(fail&&e==='set-after'&&n==='Уведомления ответов'&&v[1]===3&&v[2]==='SENDING'){fail=false;throw Error('synthetic claim failure');}});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));f.setHook(()=>{});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.deepEqual(calls,['9001']);
});
for(const mode of ['duplicate','missing','corrupt','target','source','schema'])test('damaged plan fails closed before sending: '+mode,()=>{
 const {f}=make();let calls=0;f.ctx.send_=()=>({message_id:++calls});let fail=true;
 f.setHook((e,n,v)=>{if(fail&&e==='set-before'&&n==='Поручения'&&v[1]===7){fail=false;throw Error('synthetic date failure');}});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));f.setHook(()=>{});
 const sh=f.sheet('Уведомления ответов');
 if(mode==='duplicate')sh.rows.push(sh.rows[1].slice());
 if(mode==='missing')sh.rows.splice(2,1);
 if(mode==='corrupt')sh.rows[2][1]='not JSON';
 if(mode==='target')f.properties.set('OWNER_CHAT_ID','9002');
 if(mode==='source')f.sheet('Ответы').rows[1][1]='Manually changed name';
 if(mode==='schema')sh.rows[0][0]='Changed header';
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.equal(calls,0);
});
for(const result of [true,{}, {message_id:0},{message_id:9,chat:{id:999}}])test('unverified API response remains UNKNOWN: '+JSON.stringify(result),()=>{
 const {f}=make();let calls=0;f.ctx.send_=()=>{calls++;return result;};assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.equal(calls,2);assert.ok(f.sheet('Уведомления ответов').rows.slice(1).every(r=>r[2]==='UNKNOWN'));
});
test('owner inbox acknowledgement is durable and not treated as a student reply',()=>{
 const x=make(),{f}=x;let calls=0;f.ctx.send_=id=>{assert.equal(String(id),'9001');return {message_id:++calls};};f.ctx.processMessage_(f.message('Synthetic answer',11,true));f.ctx.processMessage_(f.message('Synthetic answer',11,true));assert.equal(calls,1);assert.equal(f.sheet('Входящие').rows.length,2);assert.equal(f.sheet('Ответы').rows.length,1);assert.equal(x.stores,1);
});
test('historical reply without a prepared plan never invents a retrospective notification',()=>{
 const {f}=make();f.sheet('Ответы').rows.push([new Date(),'Synthetic','','1001','Текст','Synthetic answer',11,'','']);let calls=0;f.ctx.send_=()=>{calls++;};f.ctx.processMessage_(f.message('Synthetic answer'));assert.equal(calls,0);
});
test('patch is narrow, parses, and refuses second installation or drift',()=>{const source=currentSource(),next=patch(source);new vm.Script(next);assert.throws(()=>patch(next));assert.throws(()=>patch(source.replace('  replies.appendRow(','  changed.appendRow(')));});
test('unknown notification becomes DEAD without repeat sends while the next update can finish',()=>{
 const x=make(),{f}=x;let student=0,owner=0;
 f.ctx.send_=id=>{if(String(id)==='1001'){student++;if(student===1)throw Error('synthetic unknown');}else owner++;return {message_id:100+student+owner};};
 const updates=[{update_id:101,message:f.message('Synthetic answer',11)},{update_id:102,message:f.message('Synthetic answer',12)}];
 f.ctx.tg_=(method,p)=>{assert.equal(method,'getUpdates');return updates.filter(u=>u.update_id>=p.offset);};
 for(let i=0;i<5;i++)f.ctx.pollTelegramUpdates();
 const rows=f.sheet('Очередь updates').rows.slice(1);assert.equal(rows.find(r=>String(r[0])==='U-101')[1],'DEAD');assert.equal(rows.find(r=>String(r[0])==='U-102')[1],'DONE');
 assert.equal(student,2);assert.equal(owner,2);assert.equal(f.sheet('Ответы').rows.length,3);assert.equal(x.stores,2);
});
test('accepted plan append before failure is reused before the single saved reply',()=>{
 const x=make(),{f}=x;let calls=0,once=true;f.ctx.send_=()=>({message_id:++calls});
 f.setHook((e,n)=>{if(once&&e==='append-after'&&n==='Уведомления ответов'){once=false;throw Error('synthetic plan append');}});
 assert.throws(()=>f.ctx.processMessage_(f.message('Synthetic answer')));assert.equal(f.sheet('Ответы').rows.length,1);assert.equal(calls,0);
 f.setHook(()=>{});f.ctx.processMessage_(f.message('Synthetic answer'));assert.equal(f.sheet('Уведомления ответов').rows.length,3);assert.equal(f.sheet('Ответы').rows.length,2);assert.equal(calls,2);
 // This fixture intentionally replaces the real persistent file guard; repeat storage here is not a Drive integration assertion.
});
test('denied access never prepares or sends reply notifications',()=>{
 const {f}=make();f.sheet('Студенты').rows[1][5]='Не одобрен';f.ctx.send_=()=>({message_id:1});f.ctx.processMessage_(f.message('Synthetic answer'));
 assert.equal(f.ctx.ss_().getSheetByName('Уведомления ответов'),null);assert.equal(f.sheet('Ответы').rows.length,1);
});
test('setup only creates or verifies six technical columns, with no sends or business rows',()=>{
 const {f}=make();f.ctx.console={log(){}};f.ctx.send_=()=>{throw Error('unexpected send');};const before=JSON.stringify(f.sheet('Ответы').rows);
 const first=f.ctx.prepareKulaginaReplyNotifications();assert.equal(first.status,'reply_notifications_ready');assert.equal(first.created,true);assert.equal(first.columns,6);assert.equal(first.business_writes,0);assert.equal(first.messages_sent,0);assert.equal(first.polling_started,false);
 assert.equal(f.ctx.prepareKulaginaReplyNotifications().created,false);assert.equal(JSON.stringify(f.sheet('Ответы').rows),before);
 const source=currentSource(),out=patch(source),restore=require('../tools/clasp/legacy-reply-notifications.cjs').restoreReplyNotifications;
 assert.equal(restore(out),source);assert.throws(()=>restore(out+'// drift'));
 f.sheet('Уведомления ответов').rows[0][0]='Wrong header';assert.throws(()=>f.ctx.prepareKulaginaReplyNotifications());
});
