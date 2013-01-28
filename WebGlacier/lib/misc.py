import os

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


