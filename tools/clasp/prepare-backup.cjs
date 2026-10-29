'use strict';
/** Local preparation only. Never logs in, invokes clasp, reads credentials or contacts Google. */
const systemFs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
function createPrivateDirectory({destination,platform=process.platform,run=spawnSync,fs=systemFs}) {
 if(typeof destination!=='string'||!path.isAbsolute(destination)||/[\r\n\0]/.test(destination))throw Error('Absolute private destination required');
 destination=path.resolve(destination);
 if(fs.existsSync(destination))throw Error('Destination already exists; use a fresh backup');
 const parent=path.dirname(destination);if(!fs.existsSync(parent)||!fs.statSync(parent).isDirectory())throw Error('Existing parent required');
 for(let p=parent;;p=path.dirname(p)){
  if(fs.lstatSync(p).isSymbolicLink()||fs.existsSync(path.join(p,'.git')))throw Error('Destination must be outside Git and symlink parents');
  if(path.dirname(p)===p)break;
 }
 fs.mkdirSync(destination,{mode:0o700});
 if(platform==='win32') {
  const user=run('whoami.exe',['/user','/fo','csv','/nh'],{encoding:'utf8',windowsHide:true,shell:false});
  const sid=user.status===0&&typeof user.stdout==='string'&&user.stdout.match(/\bS-1-5-21-\d+-\d+-\d+-\d+\b/);
  if(!sid)throw Error('Cannot establish Windows user ACL; no credentials created');
  const acl=run('icacls.exe',[destination,'/inheritance:r','/grant:r','*'+sid[0]+':(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],{encoding:'utf8',windowsHide:true,shell:false});
  if(acl.status!==0)throw Error('Private ACL setup failed; no credentials created');
 }else fs.chmodSync(destination,0o700);
 return destination;
}
function prepare({destination,scriptId,platform=process.platform,run=spawnSync,fs=systemFs}) {
 if(typeof scriptId!=='string'||!/^[A-Za-z0-9_-]{20,200}$/.test(scriptId))throw Error('Invalid explicit Script ID');
 destination=createPrivateDirectory({destination,platform,run,fs});
 for(const name of ['bootstrap','backup','credentials'])fs.mkdirSync(path.join(destination,name),{mode:0o700});
 const write=(name,value)=>fs.writeFileSync(path.join(destination,name),value,{mode:0o600,flag:'wx'});
 const project=JSON.stringify({scriptId:scriptId,rootDir:'.'},null,2)+'\n';
 write('bootstrap/.clasp.json',project);write('backup/.clasp.json',project);
 write('bootstrap/appsscript.json',JSON.stringify({timeZone:'Asia/Yekaterinburg',runtimeVersion:'V8',oauthScopes:['https://www.googleapis.com/auth/script.projects.readonly']},null,2)+'\n');
 const quote=s=>platform==='win32'?"'"+s.replace(/'/g,"''")+"'":"'"+s.replace(/'/g,"'\\''")+"'";
 const prefix=(platform==='win32'?'npx.cmd':'npx')+' --yes --package=@google/clasp@3.4.1 clasp -A '+quote(path.join(destination,'credentials','.clasprc.json'))+' -P ';
 const commands=[prefix+quote(path.join(destination,'bootstrap'))+' login --use-project-scopes',prefix+quote(path.join(destination,'backup'))+' pull'];
 write('COMMANDS.txt',commands.join('\n')+'\n');
 return {prepared:true,remote_access_performed:false,commands:commands};
}
module.exports={prepare,createPrivateDirectory};
if(require.main===module){
 try {
  const args=process.argv.slice(2);
  if(args.length!==4||args[0]!=='--destination'||args[2]!=='--script-id')throw Error('Usage: node prepare-backup.cjs --destination ABSOLUTE_NEW_FOLDER --script-id ID');
  const r=prepare({destination:args[1],scriptId:args[3]});
  console.log('Local setup prepared. No Google authorization or remote operations performed.');
  console.log('Run these commands locally, one at a time. Do not share credentials or callback URLs.');
  for(const command of r.commands)console.log(command);
 }catch(error){console.error('Preparation stopped: '+error.message);process.exitCode=1;}
}
