'use strict';
/** Explicit local credential transfer to a GitHub encrypted-secret form, never chat.
 * No network calls or automatic clipboard writes. Does not modify existing auth.
 */
const systemFs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {createPrivateDirectory}=require('./prepare-backup.cjs');
function exportConnection({backupRoot,destination,account='default',authFile,platform=process.platform,run,fs=systemFs}){
 if(typeof backupRoot!=='string'||!path.isAbsolute(backupRoot)||/[\r\n\0]/.test(backupRoot))throw Error('Absolute private backup root required');
 if(typeof account!=='string'||!/^[A-Za-z0-9_-]{1,100}$/.test(account))throw Error('Explicit named account required');
 const config=path.join(backupRoot,'backup','.clasp.json'),auth=authFile||path.join(backupRoot,'credentials','.clasprc.json');
 for(const f of [config,auth]){
  if(!path.isAbsolute(f))throw Error('Absolute auth path required');
  for(let p=f;;p=path.dirname(p)){if(fs.lstatSync(p).isSymbolicLink())throw Error('Symlink input forbidden');if(path.dirname(p)===p)break;}
  const st=fs.statSync(f);if(!st.isFile()||st.size>65536)throw Error('Invalid local input');
 }
 const target=JSON.parse(fs.readFileSync(config,'utf8').replace(/^\uFEFF/,'')),store=JSON.parse(fs.readFileSync(auth,'utf8').replace(/^\uFEFF/,''));
 const selected=store.tokens&&store.tokens[account];
 if(typeof target.scriptId!=='string'||!/^[A-Za-z0-9_-]{20,200}$/.test(target.scriptId)||!selected)throw Error('Expected clasp3 target and selected account');
 const oauth={};for(const k of ['client_id','client_secret','refresh_token']){const v=selected[k];if(typeof v!=='string'||v.length<8||v.length>8192||/[\s\x00-\x1f\x7f]/.test(v))throw Error('Offline credentials incomplete');oauth[k]=v;}
 if(!/^[A-Za-z0-9._-]+\.apps\.googleusercontent\.com$/.test(oauth.client_id))throw Error('Unexpected OAuth client');
 destination=createPrivateDirectory({destination,platform,run,fs});
 const file=path.join(destination,'connection.json');
 fs.writeFileSync(file,JSON.stringify({version:1,script_id:target.scriptId,oauth,backup_key:crypto.randomBytes(32).toString('base64')},null,2)+'\n',{mode:0o600,flag:'wx'});
 return {prepared:true,file,network_calls:0,credential_values_printed:false};
}
module.exports={exportConnection};
if(require.main===module){try{const a=process.argv.slice(2);if(a.length!==4||a[0]!=='--backup-root'||a[2]!=='--destination')throw Error('Invalid arguments');const r=exportConnection({backupRoot:a[1],destination:a[3]});console.log('Connection file prepared. No network request or credential value printed.');console.log(r.file);console.log('Copy its contents only into the named GitHub encrypted-secret form, never into chat.');}catch{console.error('Connection export stopped. Check the private backup root, selected offline credentials and fresh output folder. Do not paste credentials or full file contents into chat.');process.exitCode=1;}}
