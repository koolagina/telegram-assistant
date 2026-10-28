import copy,json,sys,tempfile,unittest,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_google import GoogleCalendarAdapter,CalendarError
from nvsu_state import StateStore,execute_plan,prepare_envelope
from nvsu_sync import plan_sync

PAYLOAD=dict(start='2026-11-02T10:10:00+05:00',end='2026-11-02T11:40:00+05:00',title='Экология',location='К4-307')
def week():return dict(week_start='2026-11-02',week_end='2026-11-08',status='parsed',lessons=[dict(**PAYLOAD,source_refs=['fixture-source'],source_key='fixture-occurrence')])
NOW=dt.datetime(2026,10,27,12,tzinfo=dt.timezone.utc)
def proof():return dict(mode='live',fetched_at=NOW.isoformat(),url='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/9999//0/?date=02_11_2026',week=week())
class Response:
 def __init__(self,status,data):self.status_code=status;self.data=data
 def json(self):return copy.deepcopy(self.data)
class FakeSession:
 def __init__(self):self.calls=[];self.events={};self.next_id=0;self.fail_insert=False;self.fail_patch=False;self.fail_delete=False;self.fail_precondition=False;self.pages=None
 def request(self,method,url,**kw):
  from urllib.parse import unquote,urlsplit
  self.calls.append((method,url,copy.deepcopy(kw)));path=urlsplit(url).path
  if path.endswith('/calendars/calendar-test'):return Response(200,dict(id='calendar-test',timeZone='Asia/Yekaterinburg'))
  if path.endswith('/events'):
   if method=='GET':
    if self.pages is not None:return Response(200,self.pages[1 if kw.get('params',{}).get('pageToken') else 0])
    return Response(200,dict(items=list(self.events.values())))
   if method=='POST':
    body=copy.deepcopy(kw['json']);id=body['id']
    if id in self.events:return Response(409,{})
    body.update(etag='"1"',status='confirmed');self.events[id]=body
    if self.fail_insert:self.fail_insert=False;raise TimeoutError('accepted then timeout')
    return Response(200,body)
  id=unquote(path.rsplit('/',1)[1]);event=self.events.get(id)
  if method=='GET':return Response(200,event) if event else Response(404,{})
  if method in ('PATCH','DELETE'):
   if not event:return Response(404,{})
   if self.fail_precondition or kw.get('headers',{}).get('If-Match')!=event['etag']:return Response(412,{})
   if method=='DELETE':
    del self.events[id]
    if self.fail_delete:self.fail_delete=False;raise TimeoutError('deleted then timeout')
    return Response(204,{})
   event.update(kw['json']);event['etag']='"2"'
   if self.fail_patch:self.fail_patch=False;raise TimeoutError('patched then timeout')
   return Response(200,event)
  raise AssertionError((method,url,kw))
 def seed(self,id='owned'):
  self.events[id]=dict(id=id,etag='"1"',summary=PAYLOAD['title'],location=PAYLOAD['location'],start={'dateTime':PAYLOAD['start']},end={'dateTime':PAYLOAD['end']})
class GoogleTests(unittest.TestCase):
 def client(self,session=None,write=False):return GoogleCalendarAdapter('calendar-test',session or FakeSession(),allow_writes=write)
 def test_readonly_is_default_and_no_write_http_is_attempted(self):
  s=FakeSession();c=self.client(s)
  for call in [lambda:c.create_event('key',PAYLOAD),lambda:c.update_event('owned',PAYLOAD),lambda:c.delete_event('owned')]:
   with self.assertRaises(CalendarError):call()
  self.assertEqual(s.calls,[])
 def test_explicit_target_required_no_primary_fallback(self):
  for id in ['', 'primary']:
   with self.assertRaises(ValueError):GoogleCalendarAdapter(id,FakeSession())
 def test_pagination_and_all_day_missing_room_are_preserved(self):
  s=FakeSession();s.seed();all_day=dict(id='holiday',etag='"a"',summary='Выходной',start={'date':'2026-11-03'},end={'date':'2026-11-04'})
  s.pages=[dict(items=[s.events['owned']],nextPageToken='second'),dict(items=[all_day])]
  events=self.client(s).list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');self.assertEqual(len(events),2);self.assertTrue(events[1]['protected']);self.assertEqual(events[1]['location'],'');self.assertTrue(events[1]['start'].endswith('+05:00'))
 def test_api_payload_whitelist_deterministic_id_and_conflict_recovery(self):
  s=FakeSession();c=self.client(s,True);id=c.create_event('key',dict(**PAYLOAD,groups=['ignore'],description='ignore'));self.assertEqual(id,c.create_event('key',PAYLOAD))
  posts=[x for x in s.calls if x[0]=='POST'];self.assertEqual(len(s.events),1);self.assertEqual(set(posts[0][2]['json']),{'id','summary','start','end','location'});self.assertRegex(id,r'^[0-9a-v]{5,1024}$')
 def test_conflicting_deterministic_id_is_never_overwritten(self):
  s=FakeSession();c=self.client(s,True);id=c.create_event('key',PAYLOAD);s.events[id]['summary']='Someone else'
  with self.assertRaises(CalendarError):c.create_event('key',PAYLOAD)
 def test_patch_and_delete_use_if_match_and_never_put(self):
  s=FakeSession();s.seed();c=self.client(s,True);c.get_event('owned');c.update_event('owned',dict(PAYLOAD,location='К4-999'));self.assertEqual(s.calls[-1][2]['headers']['If-Match'],'"1"');c.delete_event('owned');self.assertEqual(s.calls[-1][2]['headers']['If-Match'],'"2"');self.assertNotIn('PUT',[x[0] for x in s.calls])
 def test_precondition_failure_stops_without_retrying_mutation(self):
  s=FakeSession();s.seed();c=self.client(s,True);c.get_event('owned');s.fail_precondition=True
  with self.assertRaises(CalendarError):c.update_event('owned',PAYLOAD)
  self.assertEqual(len([x for x in s.calls if x[0]=='PATCH']),1)
 def test_recurring_and_notes_are_protected(self):
  s=FakeSession();s.seed();s.events['owned'].update(recurringEventId='series',description='manual')
  event=self.client(s).get_event('owned');self.assertTrue(event['protected']);self.assertEqual(event['description'],'manual')
class StateTests(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'state.sqlite3';self.session=FakeSession()
 def tearDown(self):self.temp.cleanup()
 def store(self):return StateStore(self.path,'calendar-test')
 def client(self):return GoogleCalendarAdapter('calendar-test',self.session,allow_writes=True)
 def prepare(self,store,source=None):return prepare_envelope(source or proof(),[],store,requested_date='2026-11-02',now=NOW,target_mode='live')
 def execute(self,store,envelope):return execute_plan(envelope,self.client(),store,source_verifier=lambda:proof(),now=NOW)
 def test_store_is_bound_to_one_calendar(self):
  with self.store():pass
  with self.assertRaises(ValueError):StateStore(self.path,'different-target')
 def test_insert_timeout_survives_reopen_and_replay(self):
  with self.store() as store:
   p=self.prepare(store);self.session.fail_insert=True
   with self.assertRaises(CalendarError):self.execute(store,p)
  with self.store() as store:
   self.execute(store,p);self.execute(store,p);self.assertEqual(len(store.bindings()),1);self.assertEqual(store.operation_status(p['plan_id'],0),'COMMITTED')
  self.assertEqual(len(self.session.events),1)
 def test_changed_or_stale_plan_cannot_write(self):
  with self.store() as store:
   p=self.prepare(store);bad=copy.deepcopy(p);bad['plan']['operations'][0]['event']['location']='tampered'
   with self.assertRaises(ValueError):self.execute(store,bad)
   with self.assertRaises(ValueError):execute_plan(p,self.client(),store,source_verifier=lambda:proof(),now=NOW+dt.timedelta(hours=2))
  self.assertEqual(self.session.events,{})
 def test_source_must_be_refetched_before_apply(self):
  with self.store() as store:
   p=self.prepare(store);other=proof();other['week']['lessons']=[];other['week']['status']='source_reports_no_schedule'
   with self.assertRaises(ValueError):execute_plan(p,self.client(),store,source_verifier=lambda:other,now=NOW)
  self.assertEqual(self.session.events,{})
 def test_offline_plan_cannot_be_applied_to_google(self):
  with self.store() as store:
   source=proof();source['mode']='fixture';p=self.prepare(store,source)
   with self.assertRaises(ValueError):self.execute(store,p)
  self.assertEqual(self.session.events,{})
 def test_etag_change_after_preview_is_rejected(self):
  with self.store() as store:
   p=self.prepare(store);self.execute(store,p)
   events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');source=proof();source['week']['lessons'][0]['location']='К4-999';p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live')
   id=next(iter(self.session.events));self.session.events[id]['etag']='"manual-change"'
   with self.assertRaises((ValueError,CalendarError)):execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW)
   self.assertEqual(self.session.events[id]['location'],PAYLOAD['location'])
 def test_patch_timeout_survives_reopen_and_does_not_patch_twice(self):
  with self.store() as store:
   first=self.prepare(store);self.execute(store,first);source=proof();source['week']['lessons'][0]['location']='К4-999'
   events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.session.fail_patch=True
   with self.assertRaises(CalendarError):execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW)
  with self.store() as store:execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW)
  self.assertEqual(len([c for c in self.session.calls if c[0]=='PATCH']),1)
 def test_delete_timeout_survives_reopen(self):
  with self.store() as store:
   first=self.prepare(store);self.execute(store,first);source=proof();source['week'].update(status='source_reports_no_schedule',lessons=[])
   events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.session.fail_delete=True
   with self.assertRaises(CalendarError):execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW)
  with self.store() as store:execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW);self.assertEqual(store.bindings(),[])
  self.assertEqual(len([c for c in self.session.calls if c[0]=='DELETE']),1)
 def test_new_conflict_after_preview_blocks_update(self):
  with self.store() as store:
   first=self.prepare(store);self.execute(store,first);source=proof();source['week']['lessons'][0].update(start='2026-11-02T14:00:00+05:00',end='2026-11-02T15:30:00+05:00')
   events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.session.seed('manual');self.session.events['manual']['start']['dateTime']='2026-11-02T14:00:00+05:00';self.session.events['manual']['end']['dateTime']='2026-11-02T15:00:00+05:00'
   with self.assertRaises(CalendarError):execute_plan(p,self.client(),store,source_verifier=lambda:source,now=NOW)
   self.assertEqual(len([c for c in self.session.calls if c[0]=='PATCH']),0)
 def test_linked_manual_event_is_not_implicitly_owned(self):
  self.session.seed('manual')
  with self.store() as store:
   source=proof();events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.execute(store,p)
   source['week']['lessons'][0]['location']='К4-999';p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.assertFalse(p['plan']['ready']);self.assertEqual(p['plan']['operations'][0]['action'],'review_ownership')
 def test_single_writer_lock(self):
  with self.store() as first,self.store() as second:
   with first.locked():
    with self.assertRaises(ValueError):
     with second.locked():pass
 def test_expired_unknown_insert_can_be_reconciled_without_calendar_writes(self):
  from nvsu_state import reconcile_plan
  with self.store() as store:
   p=self.prepare(store);self.session.fail_insert=True
   with self.assertRaises(CalendarError):self.execute(store,p)
  before=len([call for call in self.session.calls if call[0]!='GET'])
  with self.store() as store:
   result=reconcile_plan(p,GoogleCalendarAdapter('calendar-test',self.session),store)
   self.assertEqual(result['resolved'],1);self.assertEqual(store.operation_status(p['plan_id'],0),'COMMITTED');self.assertEqual(len(store.bindings()),1)
  self.assertEqual(before,len([call for call in self.session.calls if call[0]!='GET']))
 def test_unresolved_write_blocks_new_plan_until_reconciliation(self):
  with self.store() as store:
   p=self.prepare(store);self.session.fail_insert=True
   with self.assertRaises(CalendarError):self.execute(store,p)
   later=self.prepare(store);self.assertFalse(later['plan']['ready']);self.assertTrue(any(op['action']=='review_pending_operation' for op in later['plan']['operations']))
 def test_snapshot_target_is_not_live_evidence(self):
  with self.store() as store:
   p=prepare_envelope(proof(),[],store,requested_date='2026-11-02',now=NOW)
   with self.assertRaises(ValueError):self.execute(store,p)
  self.assertEqual(self.session.events,{})
 def test_explicit_verified_link_changes_only_local_ownership(self):
  from nvsu_state import confirm_existing_binding
  self.session.seed('manual')
  with self.store() as store:
   source=proof();events=self.client().list_events(PAYLOAD['start'],'2026-11-09T00:00:00+05:00');p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.execute(store,p)
   confirm_existing_binding(p,'manual',GoogleCalendarAdapter('calendar-test',self.session),store,approved=True,source_verifier=lambda:proof(),now=NOW)
   self.assertEqual(store.bindings()[0]['ownership'],'adopted_verified')
   source['week']['lessons'][0]['location']='К4-999';p=prepare_envelope(source,events,store,requested_date='2026-11-02',now=NOW,target_mode='live');self.assertEqual(p['plan']['operations'][0]['action'],'update')
  self.assertTrue(all(call[0]=='GET' for call in self.session.calls))
 def test_explicit_link_confirmation_is_not_implicit(self):
  from nvsu_state import confirm_existing_binding
  with self.store() as store:
   p=self.prepare(store)
   with self.assertRaises(ValueError):confirm_existing_binding(p,'manual',GoogleCalendarAdapter('calendar-test',self.session),store,approved=False,source_verifier=lambda:proof(),now=NOW)
if __name__=='__main__':unittest.main()
