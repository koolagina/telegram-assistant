'use strict';
/** Pure offline inspection of explicitly filtered notification receipt metadata.
 * No payload text, credentials, network, repair, status reset or automatic replay.
 */
const crypto=require('node:crypto');
function reviewNotificationReceipts(records){
 if(!Array.isArray(records)||records.length>1000)throw Error('Bounded filtered notification receipts required');
 const counts={prepared:0,unknown:0,api_confirmed:0,invalid:0},operations=[],seen=new Set();
 for(const record of records){
  if(!record||typeof record!=='object'||Object.keys(record).sort().join('|')!=='api_message_id|key|status'||typeof record.key!=='string'||!/^REPLY-NOTIFY:[1-9][0-9]{0,23}:[0-9]{1,24}:(student|owner|inbox)$/.test(record.key)||seen.has(record.key))throw Error('Invalid or duplicate filtered notification metadata');
  seen.add(record.key);
  const id=record.api_message_id,empty=id==='',valid=(typeof id==='number'&&Number.isSafeInteger(id)&&id>0)||(typeof id==='string'&&/^[1-9][0-9]*$/.test(id)&&Number.isSafeInteger(Number(id)));
  let state='invalid',action='manual_receipt_review_no_resend';
  if(record.status==='PREPARED'&&empty){state='prepared';action='verify_source_and_complete_plan_before_dispatch';}
  if(['UNKNOWN','SENDING'].includes(record.status)&&(empty||valid)){state='unknown';action='manual_api_and_source_review_no_resend';}
  if(record.status==='API_CONFIRMED'&&valid){state='api_confirmed';action='no_automatic_send';}
  counts[state]++;operations.push({operation_sha256:crypto.createHash('sha256').update(record.key).digest('hex'),state,action});
 }
 return {format_version:1,mode:'offline_filtered_notification_review',counts,operations,source_verified:false,delivery_verified:false,ready_for_apply:false,writes:0,messages_sent:0};
}
module.exports={reviewNotificationReceipts};
