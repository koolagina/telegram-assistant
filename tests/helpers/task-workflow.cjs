'use strict';
const vm=require('node:vm');
const {fixture}=require('./apps-script.cjs'),{currentSource}=require('./legacy-current-source.cjs');
function installedSource(){return require('../../tools/clasp/legacy-reply-notifications.cjs').patchReplyNotifications(currentSource());}
function workflow({source=installedSource()}={}){
 const f=fixture('src/telegram_assistant_v2_0_5_candidate.gs'),updates=[],api=[],events=[];
 let fault=()=>{},nextMessage=100;
 const folder=f.ctx.DriveApp.getFoldersByName('synthetic').next(),originalCreate=folder.createFile;
 folder.createFile=blob=>{const file=originalCreate(blob);file.getUrl=()=> 'https://drive.invalid/synthetic-'+f.creates;return file;};
 const properties=f.ctx.PropertiesService.getScriptProperties();properties.getProperties=()=>Object.fromEntries(f.properties);f.ctx.PropertiesService.getScriptProperties=()=>properties;
 const decode=v=>typeof v==='string'&&v.startsWith("'")?v.slice(1):v;
 f.setHook((event,name,value)=>{
  if(event==='append-before'&&Array.isArray(value))for(let i=0;i<value.length;i++)value[i]=decode(value[i]);
  if(event==='set-after'&&value&&typeof value[2]==='string')f.sheet(name).rows[value[0]-1][value[1]-1]=decode(value[2]);
  events.push({event,name});fault(event,name,value);
 });
 function restart(){
  vm.runInContext(source.slice(source.indexOf('function prop_(')),f.ctx);
  f.ctx.log_=()=>{};
  f.ctx.send_=(target,text,extra)=>{
   const call={target:String(target),text,extra};api.push(call);const outcome=fault('api-send',String(target),call);if(outcome!==undefined)return outcome;
   return {message_id:++nextMessage,chat:{id:String(target)}};
  };
  f.ctx.tg_=(method,p)=>{
   if(method==='getUpdates')return updates.filter(u=>u.update_id>=p.offset);
   if(method==='getFile')return {file_path:'synthetic.bin'};
   if(method==='answerCallbackQuery')return true;
   throw Error('Unexpected mock Telegram operation');
  };
 }
 restart();
 const task=f.sheet('Поручения');task.rows.push(['T-E2E','Иван Петров','Synthetic assignment','','','Не отправлено','','','','','']);
 function addReply({file=true,text='Synthetic answer',messageId=11,updateId=102}={}){
  const m=f.message(text,messageId);if(file){delete m.text;m.caption=text;m.document={file_id:'synthetic-file-'+messageId,file_name:'synthetic.txt',file_size:10};}
  updates.push({update_id:updateId,message:m});return m;
 }
 function selectTask(id='T-E2E',updateId=101){updates.push({update_id:updateId,callback_query:{id:'synthetic-callback',from:{id:1001},message:{chat:{id:1001,type:'private'}},data:'taskid:'+id}});}
 return {f,api,events,task,updates,restart,selectTask,addReply,setFault:fn=>fault=fn,sendTasks:()=>f.ctx.sendPendingTasks(),poll:()=>f.ctx.pollTelegramUpdates(),summary:()=>({task_status:task.rows[1][5],reply_rows:f.sheet('Ответы').rows.length-1,files_created:f.creates,api_calls:api.length,real_network_calls:0,live_verified:false})};
}
module.exports={workflow,installedSource};
