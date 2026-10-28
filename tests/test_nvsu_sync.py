import unittest,sys,re,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_preview import parse_week
from nvsu_sync import event_payload,plan_sync,apply_sync_plan
FIXTURES=Path(__file__).parent/'fixtures/nvsu'
def source():return parse_week((FIXTURES/'next.html').read_text(),'9999','Тестовый Преподаватель',requested_date='2026-11-02')
def target(lesson,id='event-owned'):return dict(id=id,**event_payload(lesson))
def binding(lesson,id='event-owned'):return dict(event_id=id,source_refs=lesson['source_refs'],last_event=event_payload(lesson))
def small_week():
 week=source();week['lessons']=week['lessons'][:1];return week
class MemoryCalendar:
 def __init__(self,events=()):self.events={e['id']:copy.deepcopy(e) for e in events};self.created=0;self.updated=0;self.deleted=0;self.keys={};self.fail_create_once=False
 def create_event(self,key,payload):
  if key in self.keys:return self.keys[key]
  self.created+=1;id='created-'+str(self.created);self.events[id]=dict(id=id,**payload);self.keys[key]=id
  if self.fail_create_once:self.fail_create_once=False;raise RuntimeError('accepted then timeout')
  return id
 def list_events(self,start,end):return [copy.deepcopy(e) for e in self.events.values() if e['start']<end and e['end']>start]
 def get_event(self,id):return copy.deepcopy(self.events.get(id))
 def update_event(self,id,payload):self.updated+=1;self.events[id].update(payload)
 def delete_event(self,id):self.deleted+=1;self.events.pop(id,None)
class SyncTests(unittest.TestCase):
 def test_calendar_payload_only_time_subject_room(self):
  lesson=source()['lessons'][0];self.assertEqual(event_payload(lesson),dict(start=lesson['start'],end=lesson['end'],title='Учебный предмет',location=lesson['location']))
  self.assertNotIn('groups',lesson);self.assertNotIn('description',event_payload(lesson))
 def test_duplicate_group_rows_collapse_even_with_different_source_ids(self):
  html=(FIXTURES/'next.html').read_text();row=re.search(r'<tbody>\s*(<tr>[\s\S]*?</tr>)',html)[1];duplicate=row.replace('setlink/1000','setlink/2000').replace('3602','7777')
  html=html.replace(row,row+duplicate,1);week=parse_week(html,'9999','Тестовый Преподаватель',requested_date='2026-11-02')
  self.assertEqual(len(week['lessons']),11);self.assertEqual(len(week['lessons'][0]['source_refs']),2)
 def test_requested_date_must_match_selected_week_even_if_no_schedule(self):
  html=(FIXTURES/'current.html').read_text()
  with self.assertRaises(ValueError):parse_week(html,'9999','Тестовый Преподаватель',requested_date='2026-11-02')
 def test_plan_requires_requested_date_in_covered_week(self):
  with self.assertRaises(ValueError):plan_sync(small_week(),[],[],requested_date='2026-11-09')
 def test_create_then_second_import_is_noop(self):
  week=small_week();calendar=MemoryCalendar();ledger=[]
  apply_sync_plan(plan_sync(week,[],ledger,requested_date='2026-11-02'),calendar,ledger)
  plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02')
  self.assertEqual([o['action'] for o in plan['operations']],['unchanged']);apply_sync_plan(plan,calendar,ledger);self.assertEqual(calendar.created,1)
 def test_time_title_and_room_changes_update_same_event(self):
  for field,value in [('start','2026-11-02T10:20:00+05:00'),('title','Новая дисциплина'),('location','К4-999')]:
   week=small_week();lesson=copy.deepcopy(week['lessons'][0]);calendar=MemoryCalendar([target(lesson)]);ledger=[binding(lesson)];week['lessons'][0][field]=value
   plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02');self.assertEqual(plan['operations'][0]['action'],'update');apply_sync_plan(plan,calendar,ledger)
   self.assertEqual(calendar.created,0);self.assertEqual(calendar.updated,1);self.assertEqual(calendar.events['event-owned'][field],value)
 def test_unique_day_move_updates_same_event(self):
  week=small_week();lesson=copy.deepcopy(week['lessons'][0]);calendar=MemoryCalendar([target(lesson)]);ledger=[binding(lesson)];week['lessons'][0]['start']='2026-11-03T10:10:00+05:00';week['lessons'][0]['end']='2026-11-03T11:40:00+05:00'
  plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02');self.assertEqual(plan['operations'][0]['action'],'update')
 def test_exact_manual_event_is_bound_without_change(self):
  week=small_week();calendar=MemoryCalendar([target(week['lessons'][0],'manual')]);ledger=[]
  plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02');self.assertEqual(plan['operations'][0]['action'],'bind_existing');apply_sync_plan(plan,calendar,ledger)
  self.assertEqual(calendar.created,0);self.assertEqual(calendar.updated,0);self.assertEqual(ledger[0]['event_id'],'manual')
 def test_ambiguous_existing_event_is_not_duplicated(self):
  week=small_week();event=target(week['lessons'][0],'manual');event['title']='Ручная запись'
  plan=plan_sync(week,[event],[],requested_date='2026-11-02');self.assertEqual(plan['operations'][0]['action'],'review_overlap');self.assertFalse(plan['ready'])
 def test_manual_changes_to_owned_event_are_not_overwritten(self):
  week=small_week();lesson=week['lessons'][0];event=target(lesson);event['title']='Ручная правка'
  plan=plan_sync(week,[event],[binding(lesson)],requested_date='2026-11-02');self.assertEqual(plan['operations'][0]['action'],'review_manual_edit')
 def test_no_schedule_creates_nothing_and_removes_only_unchanged_owned_events(self):
  week=small_week();lesson=week['lessons'][0];owned=target(lesson);manual=target(lesson,'manual');week.update(status='source_reports_no_schedule',lessons=[])
  plan=plan_sync(week,[owned,manual],[binding(lesson)],requested_date='2026-11-02');self.assertEqual([o['action'] for o in plan['operations']],['delete']);calendar=MemoryCalendar([owned,manual]);ledger=[binding(lesson)];apply_sync_plan(plan,calendar,ledger)
  self.assertIn('manual',calendar.events);self.assertNotIn('event-owned',calendar.events);self.assertEqual(calendar.created,0)
 def test_incomplete_source_rejected_without_delete(self):
  week=small_week();week['status']='fetch_error'
  with self.assertRaises(ValueError):plan_sync(week,[],[],requested_date='2026-11-02')
 def test_ambiguous_source_identity_never_creates_or_deletes(self):
  week=small_week();first=week['lessons'][0];second=copy.deepcopy(first);second['start']='2026-11-02T14:00:00+05:00';second['end']='2026-11-02T15:30:00+05:00';week['lessons'].append(second)
  old=copy.deepcopy(first);old['start']='2026-11-02T12:00:00+05:00';old['end']='2026-11-02T13:30:00+05:00'
  plan=plan_sync(week,[target(old)],[binding(old)],requested_date='2026-11-02');self.assertFalse(plan['ready']);self.assertTrue(all(o['action'].startswith('review') for o in plan['operations']))
 def test_post_preview_calendar_change_prevents_any_write(self):
  week=small_week();lesson=copy.deepcopy(week['lessons'][0]);calendar=MemoryCalendar([target(lesson)]);ledger=[binding(lesson)];week['lessons'][0]['location']='К4-999';plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02');calendar.events['event-owned']['title']='Changed after preview'
  with self.assertRaises(ValueError):apply_sync_plan(plan,calendar,ledger)
  self.assertEqual(calendar.updated,0)
 def test_create_timeout_retry_uses_same_operation_key(self):
  week=small_week();calendar=MemoryCalendar();calendar.fail_create_once=True;ledger=[];plan=plan_sync(week,[],ledger,requested_date='2026-11-02')
  with self.assertRaises(RuntimeError):apply_sync_plan(plan,calendar,ledger)
  apply_sync_plan(plan,calendar,ledger);self.assertEqual(calendar.created,1);self.assertEqual(len(ledger),1)
 def test_unlinked_manual_lesson_at_old_time_is_reviewed_not_duplicated(self):
  week=small_week();old=target(week['lessons'][0],'manual');old['start']='2026-11-02T14:00:00+05:00';old['end']='2026-11-02T15:30:00+05:00'
  plan=plan_sync(week,[old],[],requested_date='2026-11-02');self.assertFalse(plan['ready']);self.assertEqual(plan['operations'][0]['action'],'review_unlinked_lesson')
 def test_changed_source_id_same_payload_keeps_owned_event(self):
  week=small_week();old=copy.deepcopy(week['lessons'][0]);week['lessons'][0]['source_refs']=['replacement-source-id']
  plan=plan_sync(week,[target(old)],[binding(old)],requested_date='2026-11-02');self.assertEqual([o['action'] for o in plan['operations']],['unchanged'])
 def test_changed_source_id_and_time_requires_review_not_delete_create(self):
  week=small_week();old=copy.deepcopy(week['lessons'][0]);week['lessons'][0].update(source_refs=['replacement-source-id'],start='2026-11-02T14:00:00+05:00',end='2026-11-02T15:30:00+05:00')
  plan=plan_sync(week,[target(old)],[binding(old)],requested_date='2026-11-02');self.assertFalse(plan['ready']);self.assertTrue(all(o['action'].startswith('review') for o in plan['operations']))
 def test_visible_payload_has_no_groups_streams_or_service_notes(self):
  week=small_week();week['lessons'][0].update(groups=['private group'],stream='service',description='service')
  plan=plan_sync(week,[],[],requested_date='2026-11-02');calendar=MemoryCalendar();ledger=[];apply_sync_plan(plan,calendar,ledger)
  self.assertEqual(set(next(iter(calendar.events.values()))),{'id','start','end','title','location'})
 def test_no_schedule_does_not_delete_manual_edits_or_other_week(self):
  week=small_week();old=copy.deepcopy(week['lessons'][0]);event=target(old);event['title']='Manual edit';week.update(status='source_reports_no_schedule',lessons=[])
  plan=plan_sync(week,[event],[binding(old)],requested_date='2026-11-02');self.assertFalse(plan['ready']);self.assertEqual(plan['operations'][0]['action'],'review_manual_edit')
  old['start']='2026-11-09T10:10:00+05:00';old['end']='2026-11-09T11:40:00+05:00';plan=plan_sync(week,[target(old)],[binding(old)],requested_date='2026-11-02');self.assertEqual(plan['operations'],[])
 def test_same_no_schedule_plan_replay_is_idempotent(self):
  week=small_week();old=copy.deepcopy(week['lessons'][0]);calendar=MemoryCalendar([target(old)]);ledger=[binding(old)];week.update(status='source_reports_no_schedule',lessons=[])
  plan=plan_sync(week,list(calendar.events.values()),ledger,requested_date='2026-11-02');apply_sync_plan(plan,calendar,ledger);apply_sync_plan(plan,calendar,ledger);self.assertEqual(calendar.events,{});self.assertEqual(ledger,[])
 def test_cli_requires_explicit_date_and_calendar_ledger_for_sync_plan(self):
  import subprocess
  script=Path(__file__).resolve().parents[1]/'tools/nvsu_preview.py'
  result=subprocess.run([sys.executable,str(script),'--html',str(FIXTURES/'next.html'),'--lecturer-id','9999','--teacher-name','Тестовый Преподаватель','--date','2026-11-02','--sync-plan'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertIn('--existing and --bindings',result.stderr)
 def test_manual_notes_on_owned_event_block_no_schedule_deletion(self):
  week=small_week();lesson=copy.deepcopy(week['lessons'][0]);event=target(lesson);event['description']='Личная заметка';week.update(status='source_reports_no_schedule',lessons=[])
  plan=plan_sync(week,[event],[binding(lesson)],requested_date='2026-11-02');self.assertFalse(plan['ready']);self.assertEqual(plan['operations'][0]['action'],'review_manual_edit')
 def test_manual_notes_added_after_preview_block_delete(self):
  week=small_week();lesson=copy.deepcopy(week['lessons'][0]);event=target(lesson);week.update(status='source_reports_no_schedule',lessons=[]);ledger=[binding(lesson)];calendar=MemoryCalendar([event]);plan=plan_sync(week,[event],ledger,requested_date='2026-11-02');calendar.events['event-owned']['description']='Личная заметка'
  with self.assertRaises(ValueError):apply_sync_plan(plan,calendar,ledger)
  self.assertEqual(calendar.deleted,0)
if __name__=='__main__':unittest.main()
