import unittest,sys,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from nvsu_preview import parse_week,preview
FIXTURES=Path(__file__).parent/'fixtures/nvsu'
def page(name):return (FIXTURES/(name+'.html')).read_text()
class NvsuPreviewTests(unittest.TestCase):
 def parse(self,name='next'):return parse_week(page(name),'9999','Тестовый Преподаватель')
 def test_previous_and_next_weeks_are_bounded(self):
  for name,start in [('previous','2026-10-19'),('next','2026-11-02')]:
   result=self.parse(name);self.assertEqual(result['week_start'],start);self.assertGreater(len(result['lessons']),0)
   self.assertTrue(all(start<=lesson['start'][:10]<=result['week_end'] for lesson in result['lessons']))
 def test_explicit_no_schedule_preserves_week_and_does_not_import_future_ics(self):
  result=self.parse('current');self.assertEqual(result['week_start'],'2026-10-26');self.assertEqual(result['lessons'],[]);self.assertEqual(result['status'],'source_reports_no_schedule')
 def test_changed_structure_and_unrelated_page_rejected(self):
  for html in ['<html>Maintenance</html>',page('next').replace('дисциплина','changed')]:
   with self.assertRaises(ValueError):parse_week(html,'9999','Тестовый Преподаватель')
 def test_wrong_teacher_and_week_conflict_rejected(self):
  with self.assertRaises(ValueError):parse_week(page('next'),'9999','Другой Преподаватель')
  with self.assertRaises(ValueError):parse_week(page('next').replace('02_11_2026','09_11_2026'),'9999','Тестовый Преподаватель')
 def test_missing_row_date_or_bad_time_is_not_silently_skipped(self):
  for html in [page('next').replace('setlink/','removed/'),page('next').replace('10:10 11:40','25:10 11:40')]:
   with self.assertRaises(ValueError):parse_week(html,'9999','Тестовый Преподаватель')
 def test_multi_group_lesson_stays_one_calendar_candidate(self):
  lessons=self.parse()['lessons'];self.assertEqual(len(lessons),11);self.assertTrue(all('groups' not in x for x in lessons))
 def test_exact_match_skipped_ambiguous_overlap_reviewed_no_writes(self):
  lessons=self.parse()['lessons'];first=lessons[0]
  existing=[{'start':first['start'],'end':first['end'],'title':first['title'],'location':first['location']}]
  plan=preview(lessons,existing);self.assertEqual(plan[0]['action'],'already_present');self.assertEqual(len(existing),1)
  existing[0]['title']='Ручная запись';plan=preview(lessons,existing);self.assertEqual(plan[0]['action'],'review_overlap')
 def test_repeat_preview_is_deterministic(self):
  lessons=self.parse()['lessons'];self.assertEqual(preview(lessons,[]),preview(lessons,[]));self.assertEqual(len({l['source_key'] for l in lessons}),len(lessons))
if __name__=='__main__':unittest.main()
