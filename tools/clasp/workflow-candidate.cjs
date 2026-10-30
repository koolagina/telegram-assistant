'use strict';
/** Offline reproducible workflow package. No Google requests, deployment or sends. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),vm=require('node:vm');
const {patchOwnerAdd}=require('./legacy-owner-add.cjs'),{patchAccessCommands}=require('./legacy-access-commands.cjs'),{patchTaskDispatch}=require('./legacy-task-dispatch.cjs');
const INSTALLED_SNAPSHOT='98244de564c6951b388da0c120047c09dc56cc09dd2def9b55e48ad340a52d56';
function snapshotHash(files){return crypto.createHash('sha256').update(JSON.stringify(files.slice().sort((a,b)=>(a.name+'\0'+a.type)<(b.name+'\0'+b.type)?-1:1))).digest('hex');}
function composeWorkflowSource(source){
 const health=fs.readFileSync(path.join(__dirname,'../../src/tools/legacy_sheet_health.gs'),'utf8');
 if(source.includes('function probeKulaginaLegacySheetsReadOnly('))throw Error('Health probe already present');
 return patchTaskDispatch(patchAccessCommands(patchOwnerAdd(source)))+'\n'+health;
}
function buildWorkflowCandidate(files,{expectedSnapshot=INSTALLED_SNAPSHOT}={}){
 if(!Array.isArray(files)||files.length!==8||typeof expectedSnapshot!=='string'||!/^[a-f0-9]{64}$/.test(expectedSnapshot))throw Error('Verified eight-file source required');
 const seen=new Set();
 for(const f of files){if(!f||Object.keys(f).sort().join('|')!=='name|source|type'||typeof f.name!=='string'||typeof f.source!=='string'||!['JSON','SERVER_JS'].includes(f.type)||seen.has(f.name+'\0'+f.type))throw Error('Invalid source snapshot');seen.add(f.name+'\0'+f.type);}
 if(snapshotHash(files)!==expectedSnapshot)throw Error('Source changed; obtain a fresh authorized review');
 if(files.filter(f=>f.name==='Код'&&f.type==='SERVER_JS').length!==1)throw Error('Main source not found');
 const candidate=files.map(f=>f.name==='Код'&&f.type==='SERVER_JS'?{...f,source:composeWorkflowSource(f.source)}:{...f});
 const code=candidate.filter(f=>f.type==='SERVER_JS').map(f=>f.source).join('\n');new vm.Script(code);
 const globals=[...code.matchAll(/^function\s+(\w+)\(/gm)].map(m=>m[1]);if(new Set(globals).size!==globals.length)throw Error('Global function collision');
 const changed=candidate.filter((f,i)=>f.source!==files[i].source).length;if(changed!==1)throw Error('Scope changed');
 return {files:candidate,review:{format_version:1,package:'task-workflow-1',base_snapshot_sha256:expectedSnapshot,candidate_snapshot_sha256:snapshotHash(candidate),changed_files:1,preserved_files:7,global_functions:globals.length,syntax:'PASS',local_only:true,live_acceptance_verified:false,writes:0,messages_sent:0}};
}
module.exports={buildWorkflowCandidate,composeWorkflowSource,snapshotHash,INSTALLED_SNAPSHOT};
