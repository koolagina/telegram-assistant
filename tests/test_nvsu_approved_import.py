import unittest,sys,copy,datetime as dt,hashlib,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_approved_import import build_import,render_import
from nvsu_sync import plan_sync,event_payload
from test_nvsu_sync import source

def fixture():
 proofs=[]
 for monday in ['2026-11-09','2026-11-16']:
  w=source();shift=(dt.date.fromisoformat(monday)-dt.date.fromisoformat(w['week_start'])).days
  for l in w['lessons']:
   for k in ['start','end']:l[k]=(dt.datetime.fromisoformat(l[k])+dt.timedelta(days=shift)).isoformat()
  w.update(week_start=monday,week_end=(dt.date.fromisoformat(monday)+dt.timedelta(days=6)).isoformat());w['lessons']=w['lessons'][:9]
  proofs.append(dict(mode='live',lecturer_id='3648',week=w,url='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/3648//0/?date='+dt.date.fromisoformat(monday).strftime('%d_%m_%Y'),raw_sha256='a'*64,fetched_at=dt.datetime.now(dt.timezone.utc).isoformat()))
 rows=[event_payload(l) for p in proofs for l in p['week']['lessons']]
 snapshot=dict(purpose='nvsu_read_only_november_comparison',snapshots=[dict(format_version=1,purpose='nvsu_read_only_comparison',complete=True,timezone='Asia/Yekaterinburg',week_start=d,week_end=(dt.date.fromisoformat(d)+dt.timedelta(days=6)).isoformat(),observed_at=dt.datetime.now(dt.timezone.utc).isoformat(),calendar_hash='b'*64,events=[] if d!='2026-11-02' else [{}]*11) for d in ['2026-11-02','2026-11-09','2026-11-16','2026-11-23']])
 return proofs,rows,snapshot
class ApprovedImportTests(unittest.TestCase):
 def test_uses_existing_planner_keys_and_exactly_18_payloads(self):
  p,a,s=fixture();v=build_import(p,a,s,now=dt.datetime.now(dt.timezone.utc));self.assertEqual(len(v['operations']),18)
  for proof in p:
   old=plan_sync(proof['week'],[],[],requested_date=proof['week']['week_start'])
   self.assertEqual([x['operation_key'] for x in old['operations']],[x['operation_key'] for x in v['operations'] if x['week_start']==proof['week']['week_start']])
  self.assertTrue(all(set(x['event'])=={'start','end','title','location'} for x in v['operations']))
 def test_changed_source_payload_approval_or_calendar_is_rejected(self):
  for kind in ['payload','count','busy','target']:
   p,a,s=fixture()
   if kind=='payload':p[0]['week']['lessons'][0]['location']='Other'
   if kind=='count':a.pop()
   if kind=='busy':s['snapshots'][1]['events']=[{}]
   if kind=='target':s['snapshots'][2]['calendar_hash']='c'*64
   with self.assertRaises(ValueError):build_import(p,a,s)
 def test_source_proof_must_be_live_correct_week_and_fixed_host(self):
  for field,val in [('mode','fixture'),('url','https://foreign.invalid/'),('raw_sha256','invalid'),('lecturer_id','9999')]:
   p,a,s=fixture();p[0][field]=val
   with self.assertRaises(ValueError):build_import(p,a,s)
 def test_stale_source_incomplete_snapshot_or_duplicate_approval_is_denied(self):
  for mode in ['stale','incomplete','duplicate']:
   p,a,s=fixture()
   if mode=='stale':p[0]['fetched_at']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=16)).isoformat()
   if mode=='incomplete':s['snapshots'][1]['complete']=False
   if mode=='duplicate':a[1]=a[0]
   with self.assertRaises(ValueError):build_import(p,a,s)
 def test_render_digest_matches_exact_json_and_wrapper_has_one_manual_entrypoint(self):
  p,a,s=fixture();v=build_import(p,a,s);out=render_import(v)
  self.assertIn('function importApprovedKulaginaNvsuLessons()',out);self.assertNotIn('function doPost',out)
  text=json.dumps(v,ensure_ascii=False,separators=(',',':'));self.assertIn(hashlib.sha256(text.encode()).hexdigest(),out)
if __name__=='__main__':unittest.main()
