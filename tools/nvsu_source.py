"""Verified public NVSU week acquisition; no Calendar/Telegram operations."""
import datetime as dt,hashlib,re
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler,HTTPSHandler
from urllib.error import HTTPError,URLError
from nvsu_preview import parse_week

MAX_HTML=1024*1024
class SourceError(ValueError):pass
class OnlyNvsu(HTTPRedirectHandler):
    def __init__(self,lecturer_id):self.prefix='/tm/index.php/timetable/show_timetable/lectur/'+lecturer_id
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urlsplit(newurl)
        if parsed.scheme!='https' or parsed.netloc!='tm.nvsu.ru' or not (parsed.path==self.prefix or parsed.path.startswith(self.prefix+'/')):raise SourceError('NVSU redirect outside the verified source is forbidden')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_week(requested_date,lecturer_id,teacher_name,*,fetch=None,now=None):
    if not re.fullmatch(r'\d+',str(lecturer_id)):raise SourceError('Numeric lecturer ID required')
    date=dt.date.fromisoformat(requested_date);monday=date-dt.timedelta(days=date.weekday())
    # Exact route/query mechanism observed and documented in NVSU_SOURCE.md.
    url='https://tm.nvsu.ru/tm/index.php/timetable/show_timetable/lectur/'+str(lecturer_id)+'//0/?'+urlencode({'date':monday.strftime('%d_%m_%Y')})
    if fetch is None:
        def fetch(url):
            opener=build_opener(HTTPSHandler(),OnlyNvsu(str(lecturer_id)))
            try:
                with opener.open(Request(url,headers={'User-Agent':'KulaginaSchedulePreview/1.0'}),timeout=20) as response:
                    return response.status,response.headers.get_content_type(),response.read(MAX_HTML+1)
            except HTTPError as error:raise SourceError('NVSU HTTP '+str(error.code)) from None
            except (URLError,TimeoutError):raise SourceError('NVSU connection failed') from None
    code,content_type,body=fetch(url)
    if code!=200:raise SourceError('NVSU HTTP '+str(code))
    if content_type.split(';')[0].strip().lower()!='text/html':raise SourceError('NVSU returned non-HTML content')
    if not isinstance(body,bytes) or len(body)>MAX_HTML:raise SourceError('NVSU HTML size limit exceeded')
    try:html=body.decode('utf-8')
    except UnicodeDecodeError:raise SourceError('NVSU returned invalid UTF-8') from None
    week=parse_week(html,str(lecturer_id),teacher_name,requested_date=requested_date)
    return dict(mode='live',fetched_at=(now or dt.datetime.now(dt.timezone.utc)).isoformat(),url=url,raw_sha256=hashlib.sha256(body).hexdigest(),lecturer_id=str(lecturer_id),teacher_name=teacher_name,week=week)
