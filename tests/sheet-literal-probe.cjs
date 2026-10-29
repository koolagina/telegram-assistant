'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/tools/sheet_literal_probe.gs','utf8');
function fixture(mode='normal'){
 const props=new Map(),rows=[],logs=[];let creates=0,sets=0,opens=0,name='',sheetName='';
 const sheet={appendRow(row){sets++;if(mode==='write_failure')throw Error('PRIVATE');rows.push(row.map(v=>v.startsWith("'")?v.slice(1):v));},setName:n=>sheetName=n,getName:()=>sheetName,getRange(r,c,n=1,m=1){return {
  setValue(v){sets++;if(mode==='write_failure')throw Error('PRIVATE');rows[r-1]??=[];rows[r-1][c-1]=v.startsWith("'")?v.slice(1):v;},
  getValues:()=>Array.from({length:n},(_,i)=>Array.from({length:m},(_,j)=>rows[r+i-1]?.[c+j-1]??'')),
  getFormulas:()=>Array.from({length:n},()=>Array(m).fill(mode==='formula'?'=1+1':''))};}};
 const book={getName:()=>name,getSheets:()=>[sheet],getId:()=> 'synthetic-private-id'};
 const ctx=vm.createContext({console:{log:x=>logs.push(x)},PropertiesService:{getScriptProperties:()=>({getProperty:k=>props.get(k),setProperty:(k,v)=>props.set(k,v)})},LockService:{getScriptLock:()=>({tryLock:()=>mode!=='busy',releaseLock(){}})},SpreadsheetApp:{create(n){creates++;if(mode==='unknown_create')throw Error('PRIVATE');name=n;return book;},openById(){opens++;return book;},flush(){}}});
 vm.runInContext(source,ctx);return {run:()=>ctx.testKulaginaSheetLiteralRoundTrip(),props,logs,get creates(){return creates;},get sets(){return sets;},get opens(){return opens;}};
}
test('separate workbook round trip and subsequent read-only verification',()=>{const f=fixture();assert.equal(f.run().status,'verified');assert.equal(f.creates,1);assert.equal(f.sets,12);assert.equal(f.run().status,'verified');assert.equal(f.creates,1);assert.equal(f.sets,12);assert.equal(f.opens,1);assert.ok(!f.logs.join('').includes('synthetic-private-id'));});
for(const mode of ['unknown_create','write_failure'])test('unknown outcome never creates a second workbook: '+mode,()=>{const f=fixture(mode);const r=f.run();assert.equal(r.status,'review_required');assert.equal(r.cleanup_required,true);assert.equal(f.run().status,'review_required');assert.equal(f.creates,1);assert.ok(!f.logs.join('').includes('PRIVATE'));});
test('formula evidence fails the acceptance check',()=>{const f=fixture('formula');assert.equal(f.run().status,'review_required');});
test('lock contention performs no workbook operations',()=>{const f=fixture('busy');assert.equal(f.run().status,'busy');assert.equal(f.creates,0);assert.equal(f.opens,0);});
