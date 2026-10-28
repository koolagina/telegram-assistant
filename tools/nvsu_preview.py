"""Read-only parser/preview for the observed NVSU lecturer timetable.

No Google client, tokens or write operation. HTML comes from an explicit local file.
ICS is deliberately not imported: live exports include dates outside the selected week.
"""
from __future__ import annotations
import argparse,datetime as dt,json,re
from dataclasses import dataclass,field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from zoneinfo import ZoneInfo

@dataclass
class Node:
 tag:str
 attrs:dict=field(default_factory=dict)
 children:list=field(default_factory=list)
 parent:object=None
 closed:bool=False
 def walk(self):
  yield self
  for child in self.children:
   if isinstance(child,Node):yield from child.walk()
 def text(self):
  return re.sub(r'\s+',' ',''.join(c.text() if isinstance(c,Node) else c for c in self.children)).strip()

class Tree(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.root=Node('root');self.stack=[self.root]
 def handle_starttag(self,tag,attrs):
  node=Node(tag,dict(attrs),parent=self.stack[-1]);self.stack[-1].children.append(node)
  if tag not in {'br','meta','link','img','input','hr','area','base','embed','param','source','wbr'}:self.stack.append(node)
  else:node.closed=True
 def handle_startendtag(self,tag,attrs):
  self.handle_starttag(tag,attrs)
  if self.stack[-1].tag==tag:self.stack.pop().closed=True
 def handle_endtag(self,tag):
  for index in range(len(self.stack)-1,0,-1):
   if self.stack[index].tag==tag:
    self.stack[index].closed=True;del self.stack[index:];break
 def handle_data(self,data):self.stack[-1].children.append(data)

def has_class(node,name):return name in node.attrs.get('class','').split()
def cells(row):return [n for n in row.children if isinstance(n,Node) and n.tag=='td']
def parse_week(html,lecturer_id,expected_teacher,timezone='Asia/Yekaterinburg',requested_date=None):
 tree=Tree();tree.feed(html)
 nodes=list(tree.root.walk());titles=[n.text() for n in nodes if n.tag=='title']
 if len(titles)!=1 or expected_teacher not in titles[0] or 'Расписание преподавателя' not in titles[0]:raise ValueError('Teacher/title mismatch')
 export=[]
 for node in nodes:
  if node.tag!='a':continue
  url=urlsplit(node.attrs.get('href',''))
  if url.scheme=='https' and url.netloc=='tm.nvsu.ru' and url.path==f'/tm/index.php/timetable/show_timetable/lectur/{lecturer_id}/0/ics/':export.append(parse_qs(url.query).get('date',[]))
 if len(export)!=1 or len(export[0])!=1:raise ValueError('Missing/ambiguous selected-week evidence')
 try:start=dt.datetime.strptime(export[0][0],'%d_%m_%Y').date()
 except ValueError as error:raise ValueError('Invalid week date') from error
 if start.weekday()!=0:raise ValueError('Selected week must start on Monday')
 end=start+dt.timedelta(days=6)
 if requested_date is not None and not start<=dt.date.fromisoformat(requested_date)<=end:raise ValueError('Requested date does not match selected week')
 tables=[n for n in nodes if n.tag=='table' and n.attrs.get('id')=='timetable']
 absent=any(n.tag=='div' and has_class(n,'message') and n.text()=='Расписание отсутствует' for n in nodes)
 if not tables:
  if absent:return dict(week_start=start.isoformat(),week_end=end.isoformat(),status='source_reports_no_schedule',lessons=[])
  raise ValueError('Missing timetable structure')
 if len(tables)!=1 or not tables[0].closed or absent:raise ValueError('Ambiguous/incomplete timetable')
 table=tables[0];rows=[n for n in table.walk() if n.tag=='tr']
 headers=[tuple(c.text().lower() for c in cells(r)) for r in rows if has_class(r,'thead')]
 expected=('время','п/г','дисциплина','группы','поток','кабинет')
 if not headers or any(h not in (expected,('занятий нет',)) for h in headers):raise ValueError('Timetable header contract changed')
 lessons=[];seen={};physical={};zone=ZoneInfo(timezone);days_seen=set();current_day=None
 weekdays=['понедельник','вторник','среда','четверг','пятница','суббота','воскресенье']
 months=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']
 for row in rows:
  columns=cells(row)
  day_titles=[c.text().lower() for c in columns if has_class(c,'title')]
  if day_titles:
   if len(day_titles)!=1:raise ValueError('Ambiguous day header')
   text=day_titles[0];matches=[]
   for offset in range(7):
    day=start+dt.timedelta(days=offset)
    if text==f'{weekdays[day.weekday()]} {day.day} {months[day.month-1]}':matches.append(day)
   if len(matches)!=1 or matches[0] in days_seen:raise ValueError('Day/week header mismatch')
   current_day=matches[0];days_seen.add(current_day)
  time_cells=[c for c in columns if has_class(c,'time')]
  if not time_cells:
   if row.parent.tag=='tbody' and columns:raise ValueError('Incomplete lesson row')
   continue
  if len(columns)!=7 or len(time_cells)!=1 or not row.closed:raise ValueError('Incomplete lesson row')
  times=re.search(r'\b(\d{2}:\d{2})\s+(\d{2}:\d{2})\b',time_cells[0].text())
  if not times:raise ValueError('Invalid lesson time')
  links=[n.attrs.get('href','') for n in columns[3].walk() if n.tag=='a' and '/timetable/setlink/' in n.attrs.get('href','')]
  if len(links)!=1:raise ValueError('Missing/ambiguous source lesson identity')
  url=urlsplit(links[0]);query=parse_qs(url.query)
  try:
   date=dt.date.fromisoformat(query['date'][0]);time=dt.time.fromisoformat(times[1]);finish=dt.time.fromisoformat(times[2])
   source_id=re.fullmatch(r'/tm/index.php/timetable/setlink/(\d+)',url.path)[1]
   if dt.time.fromisoformat(query['time'][0])!=time:raise ValueError('Time/source mismatch')
  except (KeyError,TypeError,IndexError,ValueError) as error:raise ValueError('Invalid source date/time') from error
  if not start<=date<=end or date!=current_day or finish<=time:raise ValueError('Lesson outside selected week or invalid interval')
  # Only the discipline label is visible in Calendar, never lesson type/group/stream.
  subject_links=[n.text() for n in columns[3].walk() if n.tag=='a' and n.text() and '/timetable/setlink/' not in n.attrs.get('href','') and '/timetable/setvisit/' not in n.attrs.get('href','')]
  if len(set(subject_links))==1:title=subject_links[0]
  elif subject_links:raise ValueError('Ambiguous discipline label')
  else:
   title=columns[3].text()
   types=[n.text() for n in columns[3].walk() if n.tag=='span' and has_class(n,'lowercase')]
   if len(types)!=1 or not title.startswith(types[0]):raise ValueError('Missing discipline label')
   title=title[len(types[0]):].lstrip(' -').strip()
  location=columns[6].text()
  if not title or not location:raise ValueError('Incomplete lesson fields')
  key=f'lecturer:{lecturer_id}:{source_id}:{date.isoformat()}:{time.isoformat()}'
  ref=f'lecturer:{lecturer_id}:{source_id}'
  lesson=dict(source_key=key,title=title,start=dt.datetime.combine(date,time,zone).isoformat(),end=dt.datetime.combine(date,finish,zone).isoformat(),location=location,source_refs=[ref])
  signature=(lesson['start'],lesson['end'],title,location)
  if key in seen and seen[key]!=signature:raise ValueError('Conflicting duplicate source lesson key')
  seen[key]=signature
  if signature in physical:
   previous=physical[signature]
   previous['source_refs']=sorted(set(previous['source_refs'])|{ref})
  else:
   physical[signature]=lesson;lessons.append(lesson)
 if days_seen!={start+dt.timedelta(days=i) for i in range(6)}:raise ValueError('Incomplete Monday-Saturday coverage')
 if not lessons:raise ValueError('Empty table without explicit no-schedule state')
 return dict(week_start=start.isoformat(),week_end=end.isoformat(),status='parsed',lessons=lessons)

def instant(value):
 try:parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
 except (AttributeError,ValueError) as error:raise ValueError('Invalid calendar interval') from error
 if parsed.tzinfo is None:raise ValueError('Calendar timezone required')
 return parsed

def preview(lessons,existing):
 prepared=[]
 for event in existing:
  a,b=instant(event.get('start')),instant(event.get('end'))
  if b<=a:raise ValueError('Invalid calendar interval')
  prepared.append((a,b,event))
 plan=[]
 for lesson in lessons:
  a,b=instant(lesson['start']),instant(lesson['end'])
  overlaps=[event for x,y,event in prepared if a<y and b>x]
  exact=[event for event in overlaps if instant(event['start'])==a and instant(event['end'])==b and event.get('title')==lesson['title'] and event.get('location')==lesson['location']]
  action='already_present' if len(exact)==1 and len(overlaps)==1 else 'review_overlap' if overlaps else 'create_candidate'
  plan.append({**lesson,'action':action})
 return plan

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--html',type=Path,required=True);parser.add_argument('--lecturer-id',required=True);parser.add_argument('--teacher-name',required=True);parser.add_argument('--date',required=True,help='Concrete requested date, YYYY-MM-DD');parser.add_argument('--existing',type=Path);parser.add_argument('--output',type=Path);parser.add_argument('--sync-plan',action='store_true');parser.add_argument('--bindings',type=Path)
 args=parser.parse_args()
 if args.sync_plan and (args.existing is None or args.bindings is None):parser.error('--sync-plan requires explicit --existing and --bindings files')
 week=parse_week(args.html.read_text(),args.lecturer_id,args.teacher_name,requested_date=args.date)
 if args.existing is not None:
  existing=json.loads(args.existing.read_text())
  if not isinstance(existing,list):raise ValueError('Existing calendar must be a list')
  if args.sync_plan:
   from nvsu_sync import plan_sync
   bindings=json.loads(args.bindings.read_text())
   if not isinstance(bindings,list):raise ValueError('Bindings must be a list')
   week['sync_plan']=plan_sync(week,existing,bindings,requested_date=args.date)
  else:week['preview']=preview(week['lessons'],existing)
 else:week['comparison_status']='not_compared_calendar_export_required'
 if args.output:args.output.write_text(json.dumps(week,ensure_ascii=False,indent=2))
 print(json.dumps({'week_start':week['week_start'],'week_end':week['week_end'],'status':week['status'],'lessons':len(week['lessons']),'calendar_compared':args.existing is not None},ensure_ascii=False))
if __name__=='__main__':main()
