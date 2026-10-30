'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {installedSource,workflow}=require('./helpers/task-workflow.cjs');
const {buildWorkflowCandidate:build,composeWorkflowSource:compose,snapshotHash}=require('../tools/clasp/workflow-candidate.cjs');
function fixture(){const files=[{name:'Код',type:'SERVER_JS',source:installedSource()},{name:'appsscript',type:'JSON',source:'{"runtimeVersion":"V8"}'},...Array.from({length:6},(_,i)=>({name:'synthetic-helper-'+i,type:'SERVER_JS',source:'// synthetic helper'}))];return {files,expectedSnapshot:snapshotHash(files)};}
test('build is deterministic, preserves seven sources and does not mutate input',()=>{const f=fixture(),before=JSON.stringify(f.files),a=build(f.files,f),b=build(f.files,f);assert.deepEqual(a,b);assert.equal(a.review.changed_files,1);assert.equal(a.review.preserved_files,7);assert.equal(a.review.live_acceptance_verified,false);assert.equal(a.review.messages_sent,0);assert.equal(JSON.stringify(f.files),before);assert.deepEqual(a.files.slice(1),f.files.slice(1));});
test('default builder refuses a synthetic or changed target snapshot',()=>{const f=fixture();assert.throws(()=>build(f.files));f.files[2].source+=' changed';assert.throws(()=>build(f.files,f));});
test('malformed or duplicate source entries fail closed',()=>{const f=fixture();assert.throws(()=>build(f.files.slice(1),f));f.files[2]={...f.files[0]};assert.throws(()=>build(f.files,{expectedSnapshot:snapshotHash(f.files)}));});
test('helper name collision prevents a candidate from being built',()=>{const f=fixture();f.files[2].source='function dispatchLegacyTask_() {}';assert.throws(()=>build(f.files,{expectedSnapshot:snapshotHash(f.files)}),/collision/);});
test('package cannot be accidentally applied twice',()=>{const source=compose(installedSource());assert.throws(()=>compose(source));});
test('combined package keeps add and access commands safe while a workflow remains usable',()=>{
 const w=workflow({source:compose(installedSource())});
 const add=w.f.message('/add Synthetic personal task',21,true),approve=w.f.message('/approve 1001 Иван Петров',22,true);
 for(let i=0;i<2;i++){w.f.ctx.processMessage_(add);w.f.ctx.processMessage_(approve);}
 assert.equal(w.f.sheet('Личные задачи').rows.length,2);w.sendTasks();w.selectTask();w.addReply();w.poll();assert.equal(w.task.rows[1][5],'Ответ получен');assert.equal(w.f.creates,1);
});
test('demo produces only bounded mock facts without resource identifiers or message contents',()=>{
 const {execFileSync}=require('node:child_process'),output=execFileSync(process.execPath,['tools/task_workflow_demo.cjs'],{encoding:'utf8'}),r=JSON.parse(output);
 assert.equal(r.mode,'offline_mock_acceptance');assert.equal(r.writes_to_real_resources,0);assert.equal(r.scenarios.length,3);assert.ok(r.scenarios.every(x=>x.files_created===1&&x.reply_rows===1&&x.owner_notification_api_calls===1));
 assert.equal(r.scenarios.find(x=>x.scenario==='unknown_notification').queue_dead,1);for(const privateText of ['1001','9001','Иван','drive.invalid','Synthetic answer'])assert.ok(!output.includes(privateText));
});
