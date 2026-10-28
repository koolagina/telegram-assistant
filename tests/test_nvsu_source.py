import copy,datetime as dt,io,json,re,sys,tempfile,unittest
from contextlib import redirect_stdout,redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_source import fetch_week,SourceError,OnlyNvsu,MAX_HTML
from nvsu_preview import parse_week
from nvsu_calendar import main
FIXTURES=Path(__file__).parent/'fixtures/nvsu'
class SourceTests(unittest.TestCase):
 def test_fetch_selects_monday_and_validates_concrete_date(self):
  urls=[]
  def fetch(url):urls.append(url);return 200,'text/html',(FIXTURES/'current.html').read_bytes()
  result=fetch_week('2026-10-27','9999','Тестовый Преподаватель',fetch=fetch)
  self.assertIn('date=26_10_2026',urls[0]);self.assertEqual(result['week']['status'],'source_reports_no_schedule');self.assertEqual(len(result['raw_sha256']),64)
 def test_http_errors_wrong_mime_and_oversize_fail_closed(self):
  for response in [(403,'text/html',b''),(500,'text/html',b''),(200,'application/json',b'{}'),(200,'text/html',b'x'*(MAX_HTML+1)),(200,'text/html',b'\xff')]:
   with self.assertRaises((SourceError,ValueError)):fetch_week('2026-11-02','9999','Тестовый Преподаватель',fetch=lambda url:response)
 def test_wrong_week_is_not_empty_week(self):
  with self.assertRaises(ValueError):fetch_week('2026-11-02','9999','Тестовый Преподаватель',fetch=lambda url:(200,'text/html',(FIXTURES/'current.html').read_bytes()))
 def test_redirect_cannot_switch_host_or_call_mutating_routes(self):
  for url in ['http://tm.nvsu.ru/','https://evil.invalid/','https://tm.nvsu.ru/tm/index.php/timetable/setlink/1000']:
   with self.assertRaises(SourceError):OnlyNvsu('9999').redirect_request(Request('https://tm.nvsu.ru/'),None,302,'',{},url)
 def test_year_boundary_and_requested_date(self):
  html=(FIXTURES/'next.html').read_text().replace('02_11_2026','28_12_2026')
  names=['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'];months={12:'Декабря',1:'Января'}
  start=dt.date(2026,12,28)
  for index,name in enumerate(names):
   day=start+dt.timedelta(days=index);html=html.replace('2026-11-'+str(index+2).zfill(2),day.isoformat())
   html=re.sub(r'('+name+r'\s+)'+str(index+2)+r'\s+Ноября',lambda m:m[1]+str(day.day)+' '+months[day.month],html)
  result=parse_week(html,'9999','Тестовый Преподаватель',requested_date='2027-01-01');self.assertEqual(result['week_end'],'2027-01-03');self.assertTrue(any(x['start'].startswith('2027-01-01') for x in result['lessons']))
 def test_invalid_calendar_date_never_fetches(self):
  with self.assertRaises(ValueError):fetch_week('2026-02-30','9999','Тестовый Преподаватель',fetch=lambda url:self.fail('must not fetch'))
class CLITests(unittest.TestCase):
 def test_offline_prepare_never_loads_adc_and_marks_non_live_target(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);(p/'events.json').write_text('[]');out=p/'plan.json'
   with patch('nvsu_calendar.GoogleCalendarAdapter.from_adc',side_effect=AssertionError('ADC must not load')),redirect_stdout(io.StringIO()):
    result=main(['--date','2026-11-02','--lecturer-id','9999','--teacher-name','Тестовый Преподаватель','--calendar-id','calendar-test','--html',str(FIXTURES/'next.html'),'--calendar-snapshot',str(p/'events.json'),'--state-db',str(p/'state.sqlite3'),'--output',str(out)])
   self.assertEqual(result,0);envelope=json.loads(out.read_text());self.assertEqual(envelope['target_mode'],'snapshot');self.assertEqual(envelope['source']['mode'],'fixture');self.assertEqual(out.stat().st_mode&0o077,0)
 def test_no_apply_command_and_no_implicit_live_read(self):
  with patch('nvsu_calendar.GoogleCalendarAdapter.from_adc',side_effect=AssertionError('no auth')):
   with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):main(['--apply'])
