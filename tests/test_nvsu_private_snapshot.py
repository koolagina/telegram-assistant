"""Offline, synthetic snapshot transport and existing-planner regression tests."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_private_snapshot import decode_chunks, compare_snapshot, fingerprint
from test_nvsu_sync import small_week

def snapshot(week):
 return dict(format_version=1,purpose='nvsu_read_only_comparison',complete=True,timezone='Asia/Yekaterinburg',week_start=week['week_start'],week_end=week['week_end'],observed_at='2026-10-29T10:00:00.000Z',calendar_hash='a'*64,events=[])
def event(lesson):
 return dict(id_hash='b'*64,start=lesson['start'],end=lesson['end'],title_hash=fingerprint(lesson['title']),location_hash=fingerprint(lesson['location']),protected=False)
def chunks(s):
 data=json.dumps(s,separators=(',',':'),ensure_ascii=True);parts=[data[i:i+3000] for i in range(0,len(data),3000)];digest=hashlib.sha256(data.encode()).hexdigest()
 return '\n'.join(json.dumps(dict(kind='kulagina_calendar_chunk',index=i,total=len(parts),sha256=digest,data=v)) for i,v in enumerate(parts))
class SnapshotTests(unittest.TestCase):
 def test_complete_chunk_decode_and_missing_duplicate_tamper_fail(self):
  w=small_week();s=snapshot(w);self.assertEqual(decode_chunks(chunks(s)),s)
  line=chunks(s)
  for bad in ['',line+'\n'+line,line.replace('read_only','read_Xnly')]:
   with self.assertRaises(ValueError):decode_chunks(bad)
 def test_missing_or_mixed_part_of_large_snapshot_is_rejected(self):
  s=snapshot(small_week());s['events']=[event(small_week()['lessons'][0]) for _ in range(30)]
  lines=chunks(s).splitlines();self.assertGreater(len(lines),1);self.assertEqual(decode_chunks('\n'.join(reversed(lines))),s)
  for bad in ['\n'.join(lines[:-1]),'\n'.join(lines[1:])]:
   with self.assertRaises(ValueError):decode_chunks(bad)
 def test_cli_uses_private_local_files_and_prints_only_aggregate(self):
  import subprocess,tempfile
  w=small_week();s=snapshot(w);s['events']=[event(w['lessons'][0])]
  with tempfile.TemporaryDirectory() as d:
   proof=Path(d)/'source.json';log=Path(d)/'snapshot.log';proof.write_text(json.dumps({'week':w}));log.write_text(chunks(s))
   r=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'tools/nvsu_private_snapshot.py'),'--source-proof',str(proof),'--snapshot-log',str(log),'--date',w['week_start']],capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(r.stdout)['operations'],{'bind_existing':1});self.assertNotIn(w['lessons'][0]['title'],r.stdout)
 def test_exact_match_reuses_existing_planner_but_not_executable(self):
  w=small_week();s=snapshot(w);s['events']=[event(w['lessons'][0])];r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['operations'],{'bind_existing':1});self.assertFalse(r['ready_for_apply']);self.assertFalse(r['teaching_schedule_verified'])
 def test_empty_snapshot_creates_only_preliminary_candidates(self):
  w=small_week();r=compare_snapshot(w,snapshot(w),requested_date=w['week_start']);self.assertEqual(r['operations'],{'create':1});self.assertFalse(r['ready_for_apply'])
 def test_unknown_private_text_is_not_ignored_or_leaked(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);e['title_hash']=fingerprint('PRIVATE appointment');s['events']=[e];r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['unknown_events'],1);self.assertEqual(r['operations'],{'review_overlap':1});self.assertNotIn('PRIVATE',json.dumps(r));self.assertTrue(r['review_required'])
 def test_moved_known_title_is_review_not_duplicate_create(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);e.update(start='2026-11-03T10:00:00+05:00',end='2026-11-03T11:00:00+05:00');s['events']=[e];self.assertEqual(compare_snapshot(w,s,requested_date=w['week_start'])['operations'],{'review_unlinked_lesson':1})
 def test_wrong_week_incomplete_duplicates_invalid_hash_rejected(self):
  w=small_week();s=snapshot(w)
  variants=[]
  for k,v in [('week_start','2026-11-09'),('complete',False),('timezone','UTC'),('calendar_hash','bad')]:
   x=copy.deepcopy(s);x[k]=v;variants.append(x)
  e=event(w['lessons'][0]);x=copy.deepcopy(s);x['events']=[e,e];variants.append(x)
  x=copy.deepcopy(s);x['events']=[dict(e,title_hash='invalid')];variants.append(x)
  for x in variants:
   with self.assertRaises(ValueError):compare_snapshot(w,x,requested_date=w['week_start'])
 def test_no_schedule_never_deletes_manual_events(self):
  w=small_week();s=snapshot(w);s['events']=[event(w['lessons'][0])];w.update(status='source_reports_no_schedule',lessons=[]);r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['operations'],{});self.assertEqual(r['unknown_events'],1);self.assertFalse(r['ready_for_apply'])
 def test_protected_exact_match_is_reported_without_authorizing_writes(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);e['protected']=True;s['events']=[e]
  r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['exact_match_lessons'],1);self.assertEqual(r['protected_exact_match_lessons'],1);self.assertEqual(r['missing_exact_match_lessons'],0);self.assertEqual(r['duplicate_exact_match_lessons'],0);self.assertFalse(r['ready_for_apply']);self.assertEqual(r['operations'],{'review_overlap':1})
 def test_duplicate_exact_events_are_counted_and_never_bound(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);s['events']=[e,dict(e,id_hash='c'*64)]
  r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['exact_match_lessons'],1);self.assertEqual(r['duplicate_exact_match_lessons'],1);self.assertEqual(r['operations'],{'review_overlap':1})
 def test_time_only_match_does_not_hide_wrong_room(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);e['location_hash']=fingerprint('different room');s['events']=[e]
  r=compare_snapshot(w,s,requested_date=w['week_start']);self.assertEqual(r['exact_match_lessons'],0);self.assertEqual(r['missing_exact_match_lessons'],1);self.assertEqual(r['unknown_events'],1)
 def test_extra_raw_fields_rejected(self):
  w=small_week();s=snapshot(w);e=event(w['lessons'][0]);e['summary']='private';s['events']=[e]
  with self.assertRaises(ValueError):compare_snapshot(w,s,requested_date=w['week_start'])
if __name__=='__main__':unittest.main()
