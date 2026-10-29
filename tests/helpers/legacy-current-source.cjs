'use strict';
const fs=require('node:fs');
function currentSource(){
 let source=fs.readFileSync('src/archive/telegram_assistant_v1_4_3_reference.gs','utf8').replace(/  \/\/ Callback confirmation is best-effort:[\s\S]*?(?=  if\(!isOwner_)/,"  tg_('answerCallbackQuery',{callback_query_id:q.id});\n");
 for(const [file,fn] of [['prepare-legacy-candidate','patchMain'],['legacy-file-recovery','patchFileRecovery'],['legacy-update-queue','patchUpdateQueue'],['legacy-reply-recovery','patchReplyRecovery'],['legacy-task-binding','patchTaskBinding'],['legacy-sheet-literals','patchSheetLiterals']])source=require('../../tools/clasp/'+file+'.cjs')[fn](source);
 return source;
}
module.exports={currentSource};
