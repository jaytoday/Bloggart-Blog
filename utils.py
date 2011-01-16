import os
import re
import unicodedata
import logging
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.template import _swap_settings

import django.conf
from django import template
from django.template import loader

import config

BASE_DIR = os.path.dirname(__file__)

if isinstance(config.theme, (list, tuple)):
  TEMPLATE_DIRS = config.theme
else:
  TEMPLATE_DIRS = [os.path.abspath(os.path.join(BASE_DIR, 'themes/default'))]
  if config.theme and config.theme != 'default':
    TEMPLATE_DIRS.insert(0,
                         os.path.abspath(os.path.join(BASE_DIR, 'themes', config.theme)))


def slugify(s):
  s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')
  return re.sub('[^a-zA-Z0-9-]+', '-', s).strip('-')


def format_post_path(post, num):
  slug = slugify(post.title)
  if num > 0:
    slug += "-" + str(num)
  return config.post_path_format % {
      'slug': slug,
      'year': post.published.year,
      'month': post.published.month,
      'day': post.published.day,
  }


def get_template_vals_defaults(template_vals=None):
  if template_vals is None:
    template_vals = {}
  template_vals.update({
      'config': config,
      'devel': os.environ['SERVER_SOFTWARE'].startswith('Devel'),
  })
  return template_vals


def render_template(template_name, template_vals=None, theme=None):
  template_vals = get_template_vals_defaults(template_vals)
  template_vals.update({'template_name': template_name})
  old_settings = _swap_settings({'TEMPLATE_DIRS': TEMPLATE_DIRS})
  try:
    tpl = loader.get_template(template_name)
    rendered = tpl.render(template.Context(template_vals))
  finally:
    _swap_settings(old_settings)
  return rendered


def _get_all_paths():
  import static
  keys = []
  q = static.StaticContent.all(keys_only=True).filter('indexed', True)
  cur = q.fetch(1000)
  while len(cur) == 1000:
    keys.extend(cur)
    q = static.StaticContent.all(keys_only=True)
    q.filter('indexed', True)
    q.filter('__key__ >', cur[-1])
    cur = q.fetch(1000)
  keys.extend(cur)
  return [x.name() for x in keys]


def _regenerate_sitemap():
  logging.info('temporarily skipping sitemap regen')
  import static
  import gzip
  from StringIO import StringIO
  paths = _get_all_paths()
  rendered = render_template('sitemap.xml', {'paths': paths})
  static.set('/sitemap.xml', rendered, 'application/xml', False)
  s = StringIO()
  gzip.GzipFile(fileobj=s,mode='wb').write(rendered)
  s.seek(0)
  renderedgz = s.read()
  static.set('/sitemap.xml.gz',renderedgz, 'application/x-gzip', False)
  if config.google_sitemap_ping and not Debug():
      ping_googlesitemap()     

def ping_googlesitemap():
  import urllib
  from google.appengine.api import urlfetch
  google_url = 'http://www.google.com/webmasters/tools/ping?sitemap=http://' + config.host + '/sitemap.xml.gz'
  response = urlfetch.fetch(google_url, '', urlfetch.GET)
  if response.status_code / 100 != 2:
    raise Warning("Google Sitemap ping failed", response.status_code, response.content)

ROOT_PATH = os.path.dirname(__file__) + "/.."


def redirect_to_login(*args, **kwargs):
    from google.appengine.api import users
    return args[0].redirect(users.create_login_url(args[0].request.uri))

def admin_only(handler):
    def wrapped_handler(*args, **kwargs):    
        # allow cron jobs (TODO: make sure tasks also work!)
        for gae_header in ['X-AppEngine-TaskName', 'X-AppEngine-Cron']:
          if args[0].request.headers.get(gae_header, None):
            logging.info("giving script permission for header %s" % gae_header)
            return handler(args[0])
        from google.appengine.api import users
        user = users.get_current_user()
        if user:
            if users.is_current_user_admin():
                return handler(args[0])
            else:
                logging.warning('An unauthorized user has attempted\
 to use admin_only method %s' % str(args[0]))
                return redirect_to_login(*args, **kwargs)
        else:
            logging.warning('unknown user attempting to access admin only\
 method %s. redirecting to login.' % str(args[0]))
            return redirect_to_login(*args, **kwargs)

    return wrapped_handler


def is_admin():
  # check if user is admin
  is_admin = False	
  from google.appengine.api import users
  user = users.get_current_user()
  if user:
    if users.is_current_user_admin():
      is_admin = True
  return is_admin


def GetPathElements():
    '''split PATH_INFO out to a list, filtering blank/empty values'''
    return [ x for x in os.environ['PATH_INFO'].split('/') if x ]

def GetUserAgent():
    '''return the user agent string'''
    return os.environ['HTTP_USER_AGENT']

def Debug():
    '''return True if script is running in the development envionment'''
    return 'Development' in os.environ['SERVER_SOFTWARE']

def Production():
  import app_settings, os
  return ('Development' not in os.environ['SERVER_SOFTWARE']
  ) and os.environ['APPLICATION_ID'] == app_settings.PRODUCTION_APP_ID


def hash_pipe(private_object):
    import md5 # TODO use something else
    from google.appengine.api import memcache
    new_hash = md5.md5()
    new_hash.update(str(private_object))
    public_token = new_hash.hexdigest()
    memcache.add(public_token, private_object, 6000) # length?
    return public_token


def randomInt(digits=5):
  max = int(''.join('9' for d in range(digits)))
  import random
  return int(str(random.randint(0,max)).zfill(digits))
  
def entity_set(entity_list):
	from google.appengine.ext.db import NotSavedError
	set_list = []
	key_list = []
	for entity in entity_list:
	    try:
	      if entity.key() not in key_list:
	        key_list.append( entity.key() )
	        set_list.append( entity )
	    except NotSavedError: 
	        # NOTE: make sure new items can't be added twice!
	        logging.info(
	        'unable to access key for entity %s' % entity.__dict__ )
	        set_list.append( entity )
	return set_list
	        


### RANDOM

def sort_by_attr(seq,attr, reverse=True):
    intermed = [ (getattr(seq[i],attr), i, seq[i]) for i in xrange(len(seq)) ]
    intermed.sort()
    if reverse: 
      intermed.reverse() # ranked from greatest to least
    return [ tup[-1] for tup in intermed ]

def sort_by_key(seq,attr, reverse=True):
    intermed = [ (seq[i][attr], i, seq[i]) for i in xrange(len(seq)) ]
    intermed.sort()
    if reverse: 
      intermed.reverse() # ranked from greatest to least
    return [ tup[-1] for tup in intermed ]
       
       
# set descriptor
def setdesc(x, name, desc):
  t = type(x)
  if not issubclass(t, wrapper):
    class awrap(Wrapper, t): pass
    x.__class__ = awrap
  setattr(x.__class__, name, desc)

def jsonp(callback, html):
    html = html.replace('\r\n','').replace("\n", "").replace("'", "&rsquo;");
    return callback + "('" + html + "');"


def compress(data, compresslevel=9):
    """
    gzips - might be WSGI issue?
    if you can get this to work, patch minify and cssmin
    """
    import cStringIO
    import gzip
    zbuf = cStringIO.StringIO()
    zfile = gzip.GzipFile(mode='wb', compresslevel=compresslevel, fileobj=zbuf)
    try: zfile.write(data)
    except UnicodeEncodeError:
      logging.error('error gzipping content %s' % data[:20])
      return data
    zfile.close()
    return zbuf.getvalue()


def frequency_rank(l):
	# Relevency Tally for Semantic Tags
	from collections import defaultdict
	import operator 
	# tag ranking helper function
	# take a list of tags ['tag1', 'tag2', 'tag2', tag3'....]
	# sort set of tags by order of frequency, top down
	tally = defaultdict(int)
	for x in l:
		tally[x] += 1
	sorted_tags = sorted(tally.items(), key=operator.itemgetter(1))
	tags = []
	for tag in sorted_tags:
		tags.append(tag[0]) 
	tags.reverse()
	return tags
		  

# only for debugging
def set_trace():
    import sys
    import pdb
    for attr in ('stdin', 'stdout', 'stderr'):
        setattr(sys, attr, getattr(sys, '__%s__' % attr))
    return pdb.set_trace # needs to be activated in local scope!


class TaskFailError(Exception):
  """ Tasks fail all the time, but 
  they shouldn't be clogging the error logs. """
  def __init__(self, error_msg):
    logging.warning(error_msg)
    



 
def parseDateTime(s):
	"""Create datetime object representing date/time
	   expressed in a string
 
	Takes a string in the format produced by calling str()
	on a python datetime object and returns a datetime
	instance that would produce that string.
 
	Acceptable formats are: "YYYY-MM-DD HH:MM:SS.ssssss+HH:MM",
							"YYYY-MM-DD HH:MM:SS.ssssss",
							"YYYY-MM-DD HH:MM:SS+HH:MM",
							"YYYY-MM-DD HH:MM:SS"
	Where ssssss represents fractional seconds.	 The timezone
	is optional and may be either positive or negative
	hours/minutes east of UTC.
	"""
	import re
	from datetime import datetime
	if s is None:
		return None
	# Split string in the form 2007-06-18 19:39:25.3300-07:00
	# into its constituent date/time, microseconds, and
	# timezone fields where microseconds and timezone are
	# optional.
	m = re.match(r'(.*?)(?:\.(\d+))?(([-+]\d{1,2}):(\d{2}))?$',
				 str(s))
	datestr, fractional, tzname, tzhour, tzmin = m.groups()
 
	# Create tzinfo object representing the timezone
	# expressed in the input string.  The names we give
	# for the timezones are lame: they are just the offset
	# from UTC (as it appeared in the input string).  We
	# handle UTC specially since it is a very common case
	# and we know its name.
	if tzname is None:
		tz = None
	else:
		tzhour, tzmin = int(tzhour), int(tzmin)
		if tzhour == tzmin == 0:
			tzname = 'UTC'
		tz = FixedOffset(timedelta(hours=tzhour,
								   minutes=tzmin), tzname)
 
	# Convert the date/time field into a python datetime
	# object.
	x = datetime.strptime(datestr, "%Y-%m-%d %H:%M:%S")
 
	# Convert the fractional second portion into a count
	# of microseconds.
	if fractional is None:
		fractional = '0'
	fracpower = 6 - len(fractional)
	fractional = float(fractional) * (10 ** fracpower)
 
	# Return updated datetime object with microseconds and
	# timezone information.
	return x.replace(microsecond=int(fractional), tzinfo=tz)
 

def izip_longest(*args, **kwds):
    import itertools
    # izip_longest('ABCD', 'xy', fillvalue='-') --> Ax By C- D-
    fillvalue = kwds.get('fillvalue')
    def sentinel(counter = ([fillvalue]*(len(args)-1)).pop):
        yield counter()         # yields the fillvalue, or raises IndexError
    fillers = itertools.repeat(fillvalue)
    iters = [itertools.chain(it, sentinel(), fillers) for it in args]
    try:
        for tup in itertools.izip(*iters):
            yield tup
    except IndexError:
        pass

def slice_up_list(list, max_list_len=30): # 30 is subquery limit
  """ slice up a list by a maximium length.
  """
  list_groups = []
  for i in xrange(0, len(list), max_list_len):
    list_groups.append(list[i: i+max_list_len])
  return list_groups
    

def print_page(url):
  """ fetches and renders a page """
  print ""
  from google.appengine.api import urlfetch
  fetched_page = urlfetch.fetch(url)
  print "PAGE: \n "
  print fetched_page.content





def delete_entities(entities, group=500):
  from itertools import islice 
  entity_groups = iter(lambda x=iter(entities): list(islice(x,group)), []) 
  for items in list(entity_groups):
    db.delete(items)


def save_entities(entities, group=500):
  from itertools import islice 
  entity_groups = iter(lambda x=iter(entities): list(islice(x,group)), []) 
  for items in list(entity_groups):
    db.put(items)



def strip_html(string):
 import re
 tag_token = re.compile('<(.*?)>')
 # two lines could be used for closing tag, etc. 
 plaintext_string = re.sub(tag_token,'',string)
 return plaintext_string




def epoch(value):
  import time
  return int(time.mktime(value.timetuple())  *1000)



def transactionize(fun):
  def decorate(*args, **kwargs):
    return db.run_in_transaction(fun, *args, **kwargs)
  return decorate


def validateZip(*args):
  sizes = []
  for arg in args:
   sizes.append(len(arg))
  for s in sizes:
    differences = [ (-1 < (s - i) < 1) for i in sizes]
    if False in differences:
      logging.error('LIST INEQUALITY! %s' % sizes)
  return zip(*args)


def context_to_string(context):
 response = ''
 for key, value in context.items():
   response += "__"
   response += str(key)
   response += "--"
   if isinstance(value, db.Model):
     response += str(value.key())
   else:
     response += str(value)
 return response
   

    
