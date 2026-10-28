// Tests for 2.0.5. Historical 30-minute/after-approval assumptions are replaced
// by the consultation-policy suite; all unchanged behaviors run against 2.0.5.
const {spawnSync}=require('node:child_process');
const path=require('node:path');
const cwd=path.resolve(__dirname,'..');
const current='src/telegram_assistant_v2_0_5_candidate.gs';
const retained='file:|recurrence:|regression:|lock:|idempotency:|schema:|config:|command retry:|reply recovery|queue:|delivery:|repeat:|broadcast:|timetable:|registry:|compatibility:|static:|navigation:|callback authorization:|calendar: /event|calendar: external';
for(const [label,args] of [
 ['Existing behavior against 2.0.5',['--test','--test-name-pattern='+retained,'tests/regression.cjs']],
 ['Consultation workflow against 2.0.5',['--test','tests/consultations.cjs']]
]) {
 console.log(label);
 const result=spawnSync(process.execPath,args,{cwd,env:{...process.env,RUN_CANDIDATE:current,CONSULT_CANDIDATE:current},stdio:'inherit'});
 if(result.error)throw result.error;
 if(result.status!==0)process.exit(result.status||1);
}
