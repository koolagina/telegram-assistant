'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {workflow,installedSource}=require('../helpers/task-workflow.cjs');
function candidate(){return require('../../tools/clasp/workflow-candidate.cjs').composeWorkflowSource(installedSource());}
test('installed source completes assignment -> file answer -> projection -> two API acknowledgements on mocks',()=>{
 const w=workflow();w.sendTasks();assert.equal(w.task.rows[1][5],'Отправлено');w.selectTask();w.addReply();w.poll();
 assert.equal(w.task.rows[1][5],'Ответ получен');assert.equal(w.f.creates,1);assert.equal(w.f.sheet('Ответы').rows.length,2);assert.equal(w.api.length,4);
 assert.ok(w.f.sheet('Уведомления ответов').rows.slice(1).every(r=>r[2]==='API_CONFIRMED'));w.restart();w.sendTasks();w.poll();assert.equal(w.api.length,4);assert.equal(w.f.creates,1);
});
test('recipient binding failure is recovered before any task API call',()=>{
 const w=workflow({source:candidate()});let fail=true;w.setFault((e,n,v)=>{if(fail&&e==='set-before'&&n==='Поручения'&&v[1]===10){fail=false;throw Error('synthetic target write');}});
 w.sendTasks();assert.equal(w.api.length,0);w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][9],'1001');assert.equal(w.task.rows[1][5],'Отправлено');
 w.selectTask();w.addReply();w.poll();assert.equal(w.f.sheet('Ответы').rows[1][7],'T-E2E');assert.equal(w.f.creates,1);
});
test('accepted task send then date-column failure can resume after restart',()=>{
 const w=workflow({source:candidate()});let fail=true;w.setFault((e,n,v)=>{if(fail&&e==='set-before'&&n==='Поручения'&&v[1]===4){fail=false;throw Error('synthetic date write');}});
 w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправлено');assert.equal(w.task.rows[1][9],'1001');
});
for(const event of ['set-before','set-after'])test('confirmed dispatch resumes after final status failure: '+event,()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault((e,n,v)=>{if(once&&e===event&&n==='Поручения'&&v[1]===6&&v[2]==='Отправлено'){once=false;throw Error('synthetic final status');}});
 w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправлено');
});
test('unknown task API outcome is never automatically retried',()=>{
 const w=workflow({source:candidate()});w.setFault(e=>{if(e==='api-send')throw Error('synthetic unknown');});w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправляется');
});
test('acknowledgement persisted before an exception permits projection recovery only',()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault((e,n,v)=>{if(once&&e==='append-after'&&n==='Снимки операций'&&String(v[0]).startsWith('LEGACY-TASK-DISPATCH:')&&String(v[0]).endsWith(':ACK')){once=false;throw Error('synthetic accepted receipt');}});
 w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправлено');
});
test('accepted dispatch claim with an exception cannot be reset to force sending',()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault((e,n,v)=>{if(once&&e==='append-after'&&n==='Снимки операций'&&String(v[0]).endsWith(':CLAIM')){once=false;throw Error('synthetic uncertain claim');}});
 w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,0);assert.equal(w.task.rows[1][5],'Отправляется');
});
for(const col of [7,8,9])test('actual file guard and reply recovery compose after projection column '+col+' failure',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.selectTask();w.addReply();let once=true;
 w.setFault((e,n,v)=>{if(once&&e==='set-before'&&n==='Поручения'&&v[1]===col){once=false;throw Error('synthetic projection failure');}});
 w.poll();w.setFault(()=>{});w.restart();w.poll();w.poll();
 assert.equal(w.f.creates,1);assert.equal(w.f.sheet('Ответы').rows.length,2);assert.equal(w.task.rows[1][5],'Ответ получен');assert.equal(w.api.filter(x=>x.target==='9001').length,1);
});
test('Drive creation accepted then interrupted produces one file and a retained DEAD update',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.selectTask();w.addReply();let once=true;
 w.setFault(e=>{if(once&&e==='create-after'){once=false;throw Error('synthetic ambiguous Drive result');}});
 w.poll();w.setFault(()=>{});w.restart();for(let i=0;i<4;i++)w.poll();
 assert.equal(w.f.creates,1);assert.equal(w.f.sheet('Ответы').rows.length,1);assert.equal(w.f.sheet('Очередь updates').rows.find(r=>r[0]==='U-102')[1],'DEAD');
 assert.equal(w.api.filter(x=>x.target==='9001').length,0);
});
test('unknown answer notification does not repeat upload or either notification after restart',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.selectTask();w.addReply();let once=true;
 w.setFault((e,n,v)=>{if(once&&e==='api-send'&&n==='1001'&&v.text.startsWith('Ответ сохранён')){once=false;throw Error('synthetic unknown notification');}});
 w.poll();w.setFault(()=>{});w.restart();for(let i=0;i<4;i++)w.poll();
 assert.equal(w.f.creates,1);assert.equal(w.f.sheet('Ответы').rows.length,2);assert.equal(w.api.filter(x=>x.text.startsWith('Ответ сохранён')).length,1);assert.equal(w.api.filter(x=>x.target==='9001').length,1);
});
test('task row reorder after button issuance keeps the intended task binding',()=>{
 const w=workflow({source:candidate()});w.task.rows.push(['T-OTHER','Иван Петров','Other synthetic task','','','Не отправлено','','','','','']);w.sendTasks();w.selectTask('T-E2E');
 [w.task.rows[1],w.task.rows[2]]=[w.task.rows[2],w.task.rows[1]];w.addReply();w.poll();
 assert.equal(w.f.sheet('Ответы').rows[1][7],'T-E2E');assert.equal(w.task.rows.find(r=>r[0]==='T-E2E')[5],'Ответ получен');assert.equal(w.task.rows.find(r=>r[0]==='T-OTHER')[5],'Отправлено');
});
test('denied student cannot receive a new assignment or create an answer file',()=>{
 const w=workflow({source:candidate()});w.f.sheet('Студенты').rows[1][5]='Не одобрен';w.sendTasks();assert.equal(w.api.length,0);w.addReply({updateId:101});w.poll();assert.equal(w.f.creates,0);assert.equal(w.f.sheet('Ответы').rows.length,1);
});
test('literal answer caption remains text through real candidate writers in the Sheets model',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.selectTask();w.addReply({text:'=1+1'});w.poll();assert.equal(w.f.sheet('Ответы').rows[1][5],'=1+1');assert.equal(w.task.rows[1][7],'=1+1');assert.equal(w.f.creates,1);
});
for(const mode of ['duplicate_task','duplicate_student','old_uncertain'])test('dispatch refuses unsafe identity or legacy outcome: '+mode,()=>{
 const w=workflow({source:candidate()});
 if(mode==='duplicate_task')w.task.rows.push(w.task.rows[1].slice());
 if(mode==='duplicate_student')w.f.sheet('Студенты').rows.push(w.f.sheet('Студенты').rows[1].slice());
 if(mode==='old_uncertain')w.task.rows[1][5]='Ошибка отправки';
 w.sendTasks();assert.equal(w.api.length,0);
});
test('blank task ID is assigned once and remains compatible with student callback',()=>{
 const w=workflow({source:candidate()});w.task.rows[1][0]='';w.sendTasks();const id=w.task.rows[1][0];assert.match(id,/^T-/);w.restart();w.sendTasks();assert.equal(w.task.rows[1][0],id);assert.equal(w.api.length,1);w.selectTask(id);w.addReply();w.poll();assert.equal(w.f.sheet('Ответы').rows[1][7],id);
});
test('freshly edited recipient after accepted API blocks recovery rather than reassigning the task',()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault((e,n,v)=>{if(once&&e==='set-before'&&n==='Поручения'&&v[1]===4){once=false;throw Error('synthetic date failure');}});
 w.sendTasks();w.setFault(()=>{});w.task.rows[1][9]='1002';w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][9],'1002');assert.notEqual(w.task.rows[1][5],'Отправлено');
});
test('task API response without an authenticated-looking message receipt remains uncertain',()=>{
 const w=workflow({source:candidate()});w.setFault(e=>e==='api-send'?{}:undefined);w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправляется');
});
test('row reorder during task API call does not project the receipt onto another assignment',()=>{
 const w=workflow({source:candidate()});w.task.rows.push(['T-OTHER','Иван Петров','Other assignment','','','Не отправлено','','','','','']);let once=true;
 w.setFault(e=>{if(once&&e==='api-send'){once=false;[w.task.rows[1],w.task.rows[2]]=[w.task.rows[2],w.task.rows[1]];}});w.sendTasks();
 assert.equal(w.task.rows.find(r=>r[0]==='T-E2E')[5],'Отправлено');assert.equal(w.task.rows.find(r=>r[0]==='T-OTHER')[5],'Отправлено');assert.equal(w.api.length,2);
});
test('ID collision introduced after task API acknowledgement stops projection without a second send',()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault(e=>{if(once&&e==='api-send'){once=false;w.task.rows.push(w.task.rows[1].slice());}});w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,1);assert.ok(w.task.rows.slice(1).every(r=>r[5]==='Отправляется'));
});
test('manual sent-date conflict is preserved instead of overwritten during recovery',()=>{
 const w=workflow({source:candidate()});let once=true;w.setFault((e,n,v)=>{if(once&&e==='set-before'&&n==='Поручения'&&v[1]===4){once=false;throw Error('synthetic date failure');}});w.sendTasks();w.setFault(()=>{});const manual=new Date('2026-10-25T00:00:00Z');w.task.rows[1][3]=manual;w.sendTasks();assert.equal(w.task.rows[1][3],manual);assert.equal(w.api.length,1);assert.equal(w.task.rows[1][5],'Отправляется');
});
test('one uncertain task send does not block the next independent task',()=>{
 const w=workflow({source:candidate()});w.task.rows.push(['T-OTHER','Иван Петров','Other assignment','','','Не отправлено','','','','','']);let once=true;w.setFault(e=>{if(once&&e==='api-send'){once=false;throw Error('synthetic uncertain send');}});w.sendTasks();w.setFault(()=>{});w.restart();w.sendTasks();assert.equal(w.api.length,2);assert.equal(w.task.rows.find(r=>r[0]==='T-OTHER')[5],'Отправлено');assert.equal(w.task.rows.find(r=>r[0]==='T-E2E')[5],'Отправляется');
});
test('revocation before student reply blocks file creation even for a previously sent task',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.f.sheet('Студенты').rows[1][5]='Доступ отключён';w.selectTask();w.addReply();w.poll();assert.equal(w.f.creates,0);assert.equal(w.f.sheet('Ответы').rows.length,1);assert.equal(w.api.filter(x=>x.target==='9001').length,0);
});
test('text-only answer follows the same durable path without a Drive operation',()=>{
 const w=workflow({source:candidate()});w.sendTasks();w.selectTask();w.addReply({file:false});w.poll();w.restart();w.poll();assert.equal(w.f.creates,0);assert.equal(w.f.sheet('Ответы').rows.length,2);assert.equal(w.task.rows[1][5],'Ответ получен');assert.equal(w.api.filter(x=>x.target==='9001').length,1);
});
