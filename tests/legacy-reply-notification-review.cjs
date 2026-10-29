'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {reviewNotificationReceipts:review}=require('../tools/clasp/legacy-reply-notification-review.cjs');
const item=(status,api_message_id='')=>({key:'REPLY-NOTIFY:1001:11:student',status,api_message_id});
test('unknown and sending require manual review and never permit a resend',()=>{
 for(const status of ['UNKNOWN','SENDING']){const r=review([item(status)]);assert.equal(r.counts.unknown,1);assert.equal(r.operations[0].action,'manual_api_and_source_review_no_resend');assert.equal(r.ready_for_apply,false);assert.equal(r.writes,0);}
});
test('API confirmation is not delivery evidence',()=>{const r=review([item('API_CONFIRMED',91)]);assert.equal(r.counts.api_confirmed,1);assert.equal(r.delivery_verified,false);assert.equal(r.operations[0].action,'no_automatic_send');});
test('prepared receipt alone never authorizes a send',()=>{const r=review([item('PREPARED')]);assert.equal(r.counts.prepared,1);assert.equal(r.ready_for_apply,false);assert.equal(r.source_verified,false);});
test('invalid state or contradictory API receipt is reported without guessing',()=>{for(const row of [item('DONE'),item('API_CONFIRMED'),item('PREPARED',91),item('API_CONFIRMED','not-an-id')])assert.equal(review([row]).counts.invalid,1);});
test('duplicate or unfiltered input fails closed without leaking data',()=>{for(const input of [[item('UNKNOWN'),item('UNKNOWN')],[{...item('UNKNOWN'),payload:'PRIVATE'}],[{key:'TELEGRAM_BOT_TOKEN',status:'UNKNOWN',api_message_id:''}],{},Array(1001).fill(item('UNKNOWN'))])assert.throws(()=>review(input),e=>!e.message.includes('PRIVATE'));});
test('output contains only counts fixed actions and hashed keys',()=>{const r=review([item('API_CONFIRMED',918273)]),text=JSON.stringify(r);assert.ok(!text.includes('1001'));assert.ok(!text.includes('918273'));assert.ok(!text.includes('REPLY-NOTIFY'));assert.match(r.operations[0].operation_sha256,/^[a-f0-9]{64}$/);});
