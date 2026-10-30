'use strict';
/** Offline acceptance demonstration. All services are synthetic in-memory mocks. */
const assert=require('node:assert/strict');
const {workflow,installedSource}=require('../tests/helpers/task-workflow.cjs');
const {composeWorkflowSource}=require('./clasp/workflow-candidate.cjs');
const source=composeWorkflowSource(installedSource());
function runScenario(mode){
 const w=workflow({source});w.sendTasks();w.selectTask();w.addReply();let once=true;
 if(mode==='projection_recovery')w.setFault((e,n,v)=>{if(once&&e==='set-before'&&n==='Поручения'&&v[1]===8){once=false;throw Error('Synthetic failure');}});
 if(mode==='unknown_notification')w.setFault((e,n,v)=>{if(once&&e==='api-send'&&n==='1001'&&v.text.startsWith('Ответ сохранён')){once=false;throw Error('Synthetic unknown');}});
 w.poll();w.setFault(()=>{});w.restart();for(let i=0;i<4;i++)w.poll();w.sendTasks();
 const result=w.summary();assert.equal(result.reply_rows,1);assert.equal(result.files_created,1);assert.equal(result.task_status,'Ответ получен');
 return {scenario:mode,...result,owner_notification_api_calls:w.api.filter(x=>x.target==='9001').length,queue_dead:w.f.sheet('Очередь updates').rows.slice(1).filter(r=>r[1]==='DEAD').length,delivery_verified:false};
}
const report={mode:'offline_mock_acceptance',package:'task-workflow-1',scenarios:['happy','projection_recovery','unknown_notification'].map(runScenario),writes_to_real_resources:0,messages_to_real_users:0};
console.log(JSON.stringify(report,null,2));
