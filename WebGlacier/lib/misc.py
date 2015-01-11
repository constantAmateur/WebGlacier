import os
import collections
from datetime import datetime

def ensure_path(tgt):
  """
  Makes sure the directory needed to store this file exits
  """
  directory=os.path.dirname(tgt)
  if not os.path.exists(directory):
    os.makedirs(directory)

def human_readable(size,roundoff=2):
  """
  Returns a string representing the size (given in bytes) in human readable format
  """
  if size >= 1099511627776:
    return ("%.0"+str(roundoff)+"f TiB") % (size/1099511627776.)
  if size >= 1073741824:
    return ("%.0"+str(roundoff)+"f GiB") % (size/1073741824.)
  if size >= 1048576:
    return ("%.0"+str(roundoff)+"f MiB") % (size/1048576.)
  if size >= 1024:
    return ("%.0"+str(roundoff)+"f KiB") % (size/1024.)
  return "%d B" % size

def deunicode(data):
  """
  Gets rid of unicode strings introduced by decoding that mess some things up.
  """
  if isinstance(data, basestring):
    return str(data)
  elif isinstance(data, collections.Mapping):
    return dict(map(deunicode, data.iteritems()))
  elif isinstance(data, collections.Iterable):
    return type(data)(map(deunicode, data))
  else:
    return data

def str_to_dt(string):
  """
  Converts an amazon datetime string to a python localized datetime object
  """
  if string is None or string=='':
    return None
  try:
    t=datetime.strptime(string,"%Y-%m-%dT%H:%M:%S.%fZ")
    return t
    #utc=pytz.UTC
    #return utc.localize(t)
  except ValueError:
    return None
