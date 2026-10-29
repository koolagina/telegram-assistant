'use strict';
/** Fixed-operation Google relay. No arbitrary URLs, scripts, functions or deployments. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {EXPECTED,REPLACEMENTS,patchMain}=require('./clasp/prepare-legacy-candidate.cjs');
const {patchFileRecovery,restoreFileRecovery}=require('./clasp/legacy-file-recovery.cjs');
const {patchUpdateQueue,restoreUpdateQueue}=require('./clasp/legacy-update-queue.cjs');
const {patchReplyRecovery,restoreReplyRecovery}=require('./clasp/legacy-reply-recovery.cjs');
const {patchTaskBinding,restoreTaskBinding}=require('./clasp/legacy-task-binding.cjs');
const {patchSheetLiterals,restoreSheetLiterals}=require('./clasp/legacy-sheet-literals.cjs');
const REPO='koolagina/telegram-assistant',ENVIRONMENT='google-assistant-production';
const RO='https://www.googleapis.com/auth/script.projects.readonly',RW='https://www.googleapis.com/auth/script.projects';
const MODES=['verify','review_legacy_patch','review_legacy_file_queue','prepare_write','apply_write','prepare_file_queue','apply_file_queue','review_legacy_reply_recovery','prepare_reply_recovery','apply_reply_recovery','review_legacy_task_binding','prepare_task_binding','apply_task_binding','review_legacy_sheet_literals','prepare_sheet_literals','apply_sheet_literals'];
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
class Stopped extends Error{constructor(status){super('Stopped');this.status=status;}}
const stop=status=>{throw new Stopped(status);};
function context(env){if(env.GITHUB_REPOSITORY!==REPO||env.GITHUB_REF!=='refs/heads/main'||!['push','workflow_dispatch'].includes(env.GITHUB_EVENT_NAME))stop('context_blocked');}
function validRecipient(value){
 try{if(typeof value!=='string'||value.length>1000||Buffer.from(value,'base64').toString('base64')!==value)stop('recipient_invalid');const key=crypto.createPublicKey({key:Buffer.from(value,'base64'),format:'der',type:'spki'});if(key.asymmetricKeyType!=='rsa'||key.asymmetricKeyDetails.modulusLength<2048||key.asymmetricKeyDetails.modulusLength>4096)stop('recipient_invalid');return key;}catch{stop('recipient_invalid');}
}
function sourceEnvelope(value,recipient){
 const key=crypto.randomBytes(32),nonce=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',key,nonce);c.setAAD(Buffer.from('kulagina-source-export-v1'));const ciphertext=Buffer.concat([c.update(JSON.stringify(value),'utf8'),c.final()]);
 return {version:1,algorithm:'RSA-OAEP-256+AES-256-GCM',wrapped_key:crypto.publicEncrypt({key:validRecipient(recipient),padding:crypto.constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},key).toString('base64'),nonce:nonce.toString('base64'),tag:c.getAuthTag().toString('base64'),ciphertext:ciphertext.toString('base64')};
}
function openSourceEnvelope(value,privateKey,runId){
 try{if(value.version!==1||value.algorithm!=='RSA-OAEP-256+AES-256-GCM'||typeof value.ciphertext!=='string'||value.ciphertext.length>8000000)stop('source_export_invalid');if(Buffer.from(value.tag,'base64').length!==16||Buffer.from(value.nonce,'base64').length!==12||typeof value.wrapped_key!=='string'||value.wrapped_key.length>1000)stop('source_export_invalid');const key=crypto.privateDecrypt({key:privateKey,padding:crypto.constants.RSA_PKCS1_OAEP_PADDING,oaepHash:'sha256'},Buffer.from(value.wrapped_key,'base64')),d=crypto.createDecipheriv('aes-256-gcm',key,Buffer.from(value.nonce,'base64'),{authTagLength:16});d.setAAD(Buffer.from('kulagina-source-export-v1'));d.setAuthTag(Buffer.from(value.tag,'base64'));const out=JSON.parse(Buffer.concat([d.update(Buffer.from(value.ciphertext,'base64')),d.final()]).toString('utf8'));if(out.version!==1||out.repository!==REPO||out.github_run_id!==runId||fingerprint(out.files)!==out.snapshot_sha256)stop('source_export_invalid');return out;}catch{stop('source_export_invalid');}
}
function requestedOperation(env,document,now=Date.now()){
 context(env);const allowed=['verify','review_legacy_patch','apply_legacy_patch','review_legacy_file_queue','apply_legacy_file_queue','review_legacy_reply_recovery','apply_legacy_reply_recovery','review_legacy_task_binding','apply_legacy_task_binding','review_legacy_sheet_literals','apply_legacy_sheet_literals'];
 if(env.GITHUB_EVENT_NAME==='workflow_dispatch'){if(!allowed.includes(env.GOOGLE_BRIDGE_OPERATION))stop('request_blocked');return env.GOOGLE_BRIDGE_OPERATION;}
 if(!document||Object.keys(document).some(k=>!['issued_at','operation','request_id','version','recipient_public_key'].includes(k))||!['issued_at','operation','request_id','version'].every(k=>Object.hasOwn(document,k))||document.version!==1||!allowed.includes(document.operation)||typeof document.request_id!=='string'||!/^[0-9a-f-]{36}$/.test(document.request_id))stop('request_blocked');
 if(document.recipient_public_key)validRecipient(document.recipient_public_key);
 const t=Date.parse(document.issued_at);if(!Number.isFinite(t)||now-t>24*3600000||t-now>60000)stop('request_expired');return document.operation;
}
function packet(raw){
 if(typeof raw!=='string'||!raw)stop('connection_not_configured');if(raw.length>24000)stop('invalid_connection');
 let p;try{p=JSON.parse(raw);}catch{stop('invalid_connection');}
 if(!p||p.version!==1||typeof p.script_id!=='string'||!/^[A-Za-z0-9_-]{20,200}$/.test(p.script_id)||!p.oauth||Object.keys(p.oauth).sort().join('|')!=='client_id|client_secret|refresh_token')stop('invalid_connection');
 for(const k of ['client_id','client_secret','refresh_token'])if(typeof p.oauth[k]!=='string'||p.oauth[k].length<8||p.oauth[k].length>8192||/[\s\x00-\x1f\x7f]/.test(p.oauth[k]))stop('invalid_connection');
 if(!/^[A-Za-z0-9._-]+\.apps\.googleusercontent\.com$/.test(p.oauth.client_id)||typeof p.backup_key!=='string'||Buffer.from(p.backup_key,'base64').length!==32||Buffer.from(p.backup_key,'base64').toString('base64')!==p.backup_key)stop('invalid_connection');return p;
}
function normalized(body,id){
 if(!body||body.scriptId!==id||!Array.isArray(body.files)||body.files.length>2000)stop('unverified_project');
 const seen=new Set();return body.files.map(f=>{if(!f||typeof f.name!=='string'||!f.name||f.name.length>255||!['SERVER_JS','JSON','HTML'].includes(f.type)||typeof f.source!=='string'||f.source.length>2000000||seen.has(f.name+'\0'+f.type))stop('unverified_project');seen.add(f.name+'\0'+f.type);return {name:f.name,type:f.type,source:f.source};});
}
const filename=f=>f.name+(f.type==='JSON'?'.json':f.type==='SERVER_JS'?'.js':'.html');
const fingerprint=files=>hash(JSON.stringify(files.slice().sort((a,b)=>(a.name+'\0'+a.type)<(b.name+'\0'+b.type)?-1:1)));
function originalMain(source){let out=source;for(const [old,replacement] of REPLACEMENTS.slice().reverse()){if(out.split(replacement).length!==2)return null;out=out.replace(replacement,old);}return out;}
function candidate(files,pins){
 if(files.length!==8||Object.keys(pins).length!==8)stop('source_changed');let already=false;
 for(const f of files){const name=filename(f);if(!pins[name])stop('source_changed');if(hash(f.source)===pins[name])continue;
  if(name==='Код.js'){const old=originalMain(f.source);if(old!==null&&hash(old)===pins[name]){already=true;continue;}}stop('source_changed');
 }
 if(already)return null;
 return files.map(f=>filename(f)==='Код.js'?{...f,source:patchMain(f.source)}:f);
}
function fileQueueCandidate(files,pins){
 if(files.length!==8||Object.keys(pins).length!==8)stop('source_changed');
 let main=null;
 for(const f of files){const name=filename(f);if(!pins[name])stop('source_changed');if(name==='Код.js'){main=f;continue;}if(hash(f.source)!==pins[name])stop('source_changed');}
 if(!main)stop('source_changed');
 const base=originalMain(main.source);
 if(base!==null&&hash(base)===pins['Код.js']){
  let next;
  try{next=patchUpdateQueue(patchFileRecovery(main.source));}catch{stop('source_changed');}
  return files.map(f=>f===main?{...f,source:next}:f);
 }
 try{
  const before=restoreFileRecovery(restoreUpdateQueue(main.source)),old=originalMain(before);
  if(old!==null&&hash(old)===pins['Код.js']&&patchUpdateQueue(patchFileRecovery(before))===main.source)return null;
 }catch{}
 stop('source_changed');
}
function replyRecoveryCandidate(files,pins){
 try{
  const parent=fileQueueCandidate(files,pins);
  if(parent===null)return files.map(f=>filename(f)==='Код.js'?{...f,source:patchReplyRecovery(f.source)}:f);
 }catch{}
 try{
  const before=files.map(f=>filename(f)==='Код.js'?{...f,source:restoreReplyRecovery(f.source)}:f);
  if(fileQueueCandidate(before,pins)===null&&fingerprint(before.map(f=>filename(f)==='Код.js'?{...f,source:patchReplyRecovery(f.source)}:f))===fingerprint(files))return null;
 }catch{}
 stop('source_changed');
}
function taskBindingCandidate(files,pins){
 try{
  const parent=replyRecoveryCandidate(files,pins);
  if(parent===null)return files.map(f=>filename(f)==='Код.js'?{...f,source:patchTaskBinding(f.source)}:f);
 }catch{}
 try{
  const before=files.map(f=>filename(f)==='Код.js'?{...f,source:restoreTaskBinding(f.source)}:f);
  if(replyRecoveryCandidate(before,pins)===null&&fingerprint(before.map(f=>filename(f)==='Код.js'?{...f,source:patchTaskBinding(f.source)}:f))===fingerprint(files))return null;
 }catch{}
 stop('source_changed');
}
function sheetLiteralsCandidate(files,pins){
 try{
  if(taskBindingCandidate(files,pins)===null)return files.map(f=>filename(f)==='Код.js'?{...f,source:patchSheetLiterals(f.source)}:f);
 }catch{}
 try{
  const before=files.map(f=>filename(f)==='Код.js'?{...f,source:restoreSheetLiterals(f.source)}:f);
  if(taskBindingCandidate(before,pins)===null&&fingerprint(before.map(f=>filename(f)==='Код.js'?{...f,source:patchSheetLiterals(f.source)}:f))===fingerprint(files))return null;
 }catch{}
 stop('source_changed');
}
function seal(value,key){const nonce=crypto.randomBytes(12),c=crypto.createCipheriv('aes-256-gcm',Buffer.from(key,'base64'),nonce);c.setAAD(Buffer.from('kulagina-google-bridge-backup-v1'));const data=Buffer.concat([c.update(JSON.stringify(value),'utf8'),c.final()]);return {version:1,nonce:nonce.toString('base64'),tag:c.getAuthTag().toString('base64'),ciphertext:data.toString('base64')};}
function unseal(v,key){try{if(v.version!==1||typeof v.ciphertext!=='string'||v.ciphertext.length>8000000)stop('backup_invalid');if(Buffer.from(v.tag,'base64').length!==16||Buffer.from(v.nonce,'base64').length!==12)stop('backup_invalid');const d=crypto.createDecipheriv('aes-256-gcm',Buffer.from(key,'base64'),Buffer.from(v.nonce,'base64'),{authTagLength:16});d.setAAD(Buffer.from('kulagina-google-bridge-backup-v1'));d.setAuthTag(Buffer.from(v.tag,'base64'));return JSON.parse(Buffer.concat([d.update(Buffer.from(v.ciphertext,'base64')),d.final()]).toString('utf8'));}catch{stop('backup_invalid');}}
async function runBridge(operation,{env=process.env,fetch=globalThis.fetch,pins=EXPECTED,stateDir=path.join(env.RUNNER_TEMP||require('node:os').tmpdir(),'google-bridge-state'),recipientKey=env.GOOGLE_BRIDGE_RECIPIENT_PUBLIC_KEY,now=()=>Date.now()}={}){
 const r={status:'not_started',operation,google_gets:0,google_writes:0,google_write_api_accepted:false,google_write_verified:false,messages_sent:0,source_exposed:false};let writing=false;
 try{
  context(env);if(recipientKey)validRecipient(recipientKey);if(!MODES.includes(operation))stop('operation_blocked');const write=['prepare_write','apply_write','prepare_file_queue','apply_file_queue','prepare_reply_recovery','apply_reply_recovery','prepare_task_binding','apply_task_binding','prepare_sheet_literals','apply_sheet_literals'].includes(operation),applying=['apply_write','apply_file_queue','apply_reply_recovery','apply_task_binding','apply_sheet_literals'].includes(operation),fileQueue=['prepare_file_queue','apply_file_queue','review_legacy_file_queue'].includes(operation),replyRecovery=['prepare_reply_recovery','apply_reply_recovery','review_legacy_reply_recovery'].includes(operation),taskBinding=['prepare_task_binding','apply_task_binding','review_legacy_task_binding'].includes(operation),sheetLiterals=['review_legacy_sheet_literals','prepare_sheet_literals','apply_sheet_literals'].includes(operation),patchOperation=sheetLiterals?'legacy_sheet_literals_v1':taskBinding?'legacy_task_binding_v1':replyRecovery?'legacy_reply_recovery_v1':fileQueue?'legacy_file_queue_v1':'legacy_access_ack_v1',buildCandidate=sheetLiterals?sheetLiteralsCandidate:taskBinding?taskBindingCandidate:replyRecovery?replyRecoveryCandidate:fileQueue?fileQueueCandidate:candidate;
  async function request(url,args,fail){let response,text;try{response=await fetch(url,{...args,redirect:'manual',signal:AbortSignal.timeout(20000)});text=await response.text();}catch{stop(fail);}if(response.status!==200){if(Number.isInteger(response.status)&&response.status>=100&&response.status<=599){r.http_failure_status=response.status;r.http_failure_stage=fail;}if(url.startsWith('https://script.googleapis.com/')&&typeof text==='string'&&text.length<=4000000){r.google_error_reason='unclassified';try{const e=JSON.parse(text).error;const allowed=['ACCESS_TOKEN_SCOPE_INSUFFICIENT','SERVICE_DISABLED','API_KEY_SERVICE_BLOCKED','ACCESS_DENIED','IAM_PERMISSION_DENIED','CONSUMER_INVALID','ORG_RESTRICTION_VIOLATION','RATE_LIMIT_EXCEEDED','forbidden','insufficientPermissions','accessNotConfigured','domainPolicy'];const reasons=[...(Array.isArray(e?.details)?e.details.filter(x=>x&&x['@type']==='type.googleapis.com/google.rpc.ErrorInfo'&&x.domain==='googleapis.com').map(x=>x.reason):[]),...(Array.isArray(e?.errors)?e.errors.map(x=>x?.reason):[])];r.google_error_reason=reasons.find(x=>allowed.includes(x))||'unclassified';}catch{}}stop(fail);}if(typeof text!=='string'||text.length>4000000)stop(fail);try{return JSON.parse(text);}catch{stop(fail);}}
  if(write){
   if(!env.GITHUB_TOKEN)stop('protection_unverified');
   const base='https://api.github.com/repos/'+REPO+'/environments/'+ENVIRONMENT,args={method:'GET',headers:{Authorization:'Bearer '+env.GITHUB_TOKEN,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}};
   const e=await request(base,args,'protection_unverified'),b=await request(base+'/deployment-branch-policies',args,'protection_unverified');
   if(e.name!==ENVIRONMENT||!Array.isArray(e.protection_rules)||!e.protection_rules.some(x=>x.type==='required_reviewers'&&Array.isArray(x.reviewers)&&x.reviewers.length)||!e.deployment_branch_policy||e.deployment_branch_policy.custom_branch_policies!==true||!b||!Array.isArray(b.branch_policies)||b.branch_policies.length!==1||b.branch_policies[0].name!=='main'||b.branch_policies[0].type!=='branch')stop('protection_unverified');
  }
  if(applying&&env.KULAGINA_BACKUP_UPLOADED!=='true')stop('backup_not_confirmed');
  const p=packet(env[write?'KULAGINA_GOOGLE_WRITE_CONNECTION_V1':'KULAGINA_GOOGLE_READ_CONNECTION_V1']);
  const token=await request('https://oauth2.googleapis.com/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({...p.oauth,grant_type:'refresh_token'}).toString()},'authorization_failed');
  if(typeof token.access_token!=='string'||!token.access_token||token.access_token.length>16384||/[\s\x00-\x1f\x7f]/.test(token.access_token))stop('authorization_failed');
  const info=typeof token.scope==='string'?token:await request('https://oauth2.googleapis.com/tokeninfo',{method:'POST',headers:{Authorization:'Bearer '+token.access_token,'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'}},'scope_unverified');
  const scopes=typeof info.scope==='string'?info.scope.split(/\s+/).filter(Boolean):[];
  const identity=['openid','email','profile','https://www.googleapis.com/auth/userinfo.email','https://www.googleapis.com/auth/userinfo.profile'];
  if(!scopes.includes(write?RW:RO)||scopes.some(x=>![...identity,RO,...(write?[RW]:[])].includes(x)))stop('scope_policy_blocked');r.scope_verified=true;
  const url='https://script.googleapis.com/v1/projects/'+encodeURIComponent(p.script_id)+'/content',headers={Authorization:'Bearer '+token.access_token,'Content-Type':'application/json'};
  async function read(){r.google_gets++;return normalized(await request(url,{method:'GET',headers},'project_unavailable'),p.script_id);}
  const files=await read(),baseHash=fingerprint(files);r.project_files=files.length;r.project_snapshot_sha256=baseHash;
  const manifest=files.find(f=>f.name==='appsscript'&&f.type==='JSON');let m=null;try{m=manifest&&JSON.parse(manifest.source);}catch{}
  r.manifest_valid=!!m;r.timezone_matches=!!m&&m.timeZone==='Asia/Yekaterinburg';r.runtime_v8=!!m&&m.runtimeVersion==='V8';r.server_js_files=files.filter(f=>f.type==='SERVER_JS').length;
  if(recipientKey&&!write){
   if(!path.isAbsolute(stateDir)||fs.existsSync(stateDir)&&fs.lstatSync(stateDir).isSymbolicLink())stop('state_blocked');fs.mkdirSync(stateDir,{recursive:true,mode:0o700});fs.chmodSync(stateDir,0o700);
   const encrypted=sourceEnvelope({version:1,repository:REPO,github_run_id:env.GITHUB_RUN_ID,script_id:p.script_id,read_at:now(),snapshot_sha256:baseHash,files},recipientKey);
   fs.writeFileSync(path.join(stateDir,'source.enc.json'),JSON.stringify(encrypted),{mode:0o600,flag:'wx'});r.source_exported=true;
  }
  if(operation==='verify'){r.status='connected_readonly';return r;}
  if(applying){
   const file=path.join(stateDir,'backup.enc.json');let x;try{x=unseal(JSON.parse(fs.readFileSync(file,'utf8')),p.backup_key);}catch{stop('backup_invalid');}
   if(x.version!==1||x.operation!==patchOperation||x.github_run_id!==env.GITHUB_RUN_ID||x.script_id!==p.script_id||typeof x.created_at!=='number'||now()-x.created_at>300000||x.created_at-now()>60000||!Array.isArray(x.original)||!Array.isArray(x.candidate))stop('backup_invalid');
   if(fingerprint(x.original)!==x.base_hash||fingerprint(x.candidate)!==x.next_hash)stop('backup_invalid');
   const reviewed=buildCandidate(x.original,pins);if(!reviewed||fingerprint(reviewed)!==x.next_hash)stop('backup_invalid');
   if(baseHash===x.next_hash){r.status='already_applied';return r;}if(baseHash!==x.base_hash)stop('source_changed');
   // The encrypted original/intent must have been uploaded in an earlier step.
   // No retry: a network failure after PUT has an unknown remote outcome.
   writing=true;r.google_writes++;
   await request(url,{method:'PUT',headers,body:JSON.stringify({files:x.candidate})},'write_outcome_unknown');r.google_write_api_accepted=true;
   if(fingerprint(await read())!==x.next_hash)stop('write_outcome_unknown');r.changed_files=1;r.google_write_verified=true;r.status='applied';return r;
  }
  const next=buildCandidate(files,pins);if(!next){r.status='already_applied';r.change_required=false;return r;}
  if(!path.isAbsolute(stateDir)||fs.existsSync(stateDir)&&fs.lstatSync(stateDir).isSymbolicLink())stop('state_blocked');fs.mkdirSync(stateDir,{recursive:true,mode:0o700});fs.chmodSync(stateDir,0o700);
  const sealed=seal({version:1,operation:patchOperation,github_run_id:env.GITHUB_RUN_ID,script_id:p.script_id,created_at:now(),base_hash:baseHash,next_hash:fingerprint(next),original:files,candidate:next},p.backup_key);
  fs.writeFileSync(path.join(stateDir,'backup.enc.json'),JSON.stringify(sealed),{mode:0o600,flag:'wx'});
  r.changed_files=1;r.change_required=true;r.candidate_snapshot_sha256=fingerprint(next);r.status=write?'prepared':'review_ready';return r;
 }catch(e){r.status=writing?'write_outcome_unknown':e instanceof Stopped?e.status:'operation_failed';return r;}
}
module.exports={runBridge,requestedOperation,openSourceEnvelope};
if(require.main===module){(async()=>{try{const mode=process.argv[2];if(process.argv.length!==3)stop('operation_blocked');if(mode==='plan'){
 let document=null;if(process.env.GITHUB_EVENT_NAME==='push'){const p='.github/google-bridge/request.json';if(fs.statSync(p).size>4096)stop('request_blocked');document=JSON.parse(fs.readFileSync(p,'utf8'));}
 const operation=requestedOperation(process.env,document);const recipient=document?document.recipient_public_key||'':process.env.GOOGLE_BRIDGE_RECIPIENT_PUBLIC_KEY||'';if(recipient)validRecipient(recipient);if(process.env.GITHUB_OUTPUT)fs.appendFileSync(process.env.GITHUB_OUTPUT,'operation='+operation+'\nrecipient_key='+recipient+'\n');console.log(JSON.stringify({status:'request_validated',operation}));return;
 }
 const r=await runBridge(mode);if(process.env.GITHUB_OUTPUT&&r.source_exported)fs.appendFileSync(process.env.GITHUB_OUTPUT,'source_exported=true\n');if(process.env.GITHUB_OUTPUT&&['prepared','review_ready','already_applied'].includes(r.status))fs.appendFileSync(process.env.GITHUB_OUTPUT,'change_required='+(r.change_required===true?'true':'false')+'\n');console.log(JSON.stringify(r));if(!['connected_readonly','review_ready','prepared','already_applied','applied'].includes(r.status))process.exitCode=1;
 }catch{console.log(JSON.stringify({status:'request_blocked',google_writes:0,source_exposed:false}));process.exitCode=1;}})();}
