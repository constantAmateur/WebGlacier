from flask import request, session
from boto.glacier.concurrent import ConcurrentUploader
import os
from datetime import datetime

from WebGlacier import app, handlers, db
from WebGlacier.models import Vault,Archive,Job
from WebGlacier import live_clients


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

def get_set_region():
  """
  Gets the current region by looking first in url args, then in the session object, finally reverting to default.
  """
  if 'region' in request.args and request.args['region'] in handlers:
    return request.args['region']
  elif 'region' in session and session['region'] in handlers:
    return session['region']
  return app.config["DEFAULT_REGION"]

def update_live_clients():
  """
  Check how long it has been since the last check-in and drops any clients that
  have missed too many check-ins.
  """
  now=datetime.utcnow()
  kill_em_all=[]
  for client,dat in live_clients.iteritems():
    last_seen,poll_freq,processing = dat
    delta=(now-last_seen).total_seconds()
    nmiss = delta/poll_freq
    if nmiss > 5 and not processing:
      kill_em_all.append(client)
  for hit in kill_em_all:
    _ = live_clients.pop(hit)

def get_valid_clients():
  """
  Determine which of the client are connected and have a valid IP.
  If it's in the list, put the current client first.
  """
  #Update the clients first
  update_live_clients()
  #Now get the clients that match this ip and are live
  webip=str(request.remote_addr)
  passed=[]
  for client in live_clients.keys():
    cip = client[client.rfind("(")+1:-1] if client[-1]==")" else client
    if cip == webip:
      passed.append(client)
  #Put the current one at the front if it's in it
  if app.config['current_client'] in passed:
      passed.insert(0,passed.pop(passed.index(app.config['current_client'])))
  return passed

def get_handler(region=None):
  if region is None:
    region=get_set_region()
  return handlers[region]

def process_vault(vault):
  """
  vault should be a dictionary returned from list_vaults (from amazon).
  """
  #Check if it already exists
  tmp=Vault.query.filter_by(name = vault["VaultName"]).first()
  #Add it if not
  if tmp is None:
    tmp=Vault(vault["VaultName"],vault["VaultARN"].split(":")[3])
  tmp.creation_date = str_to_dt(vault["CreationDate"])
  tmp.ARN = vault['VaultARN']
  tmp.last_inventory_date = str_to_dt(vault["LastInventoryDate"])
  tmp.no_of_archives=vault["NumberOfArchives"]
  tmp.size=vault["SizeInBytes"]
  db.session.add(tmp)
  db.session.commit()
  return tmp

def process_job(job,vault):
  """
  job should be a dictionary returned by amazon with all the pertinent info.
  """
  #Check if it exists
  tmp=Job.query.filter_by(job_id = job['JobId']).first()
  #If it doesn't add it first
  if tmp is None:
    if job['Action']==u'InventoryRetrieval':
      tmp = Job(action='list',job_id = job['JobId'],vault=vault)
    elif job['Action']==u'ArchiveRetrieval':
      archive = Archive.query.filter_by(archive_id = job["ArchiveId"]).first()
      if archive is None:
        #Archive either not added, or deleted
        print "Couldn't find the archive being referenced."
      tmp = Job(action='download',job_id = job['JobId'],vault=vault,archive=archive)
  else:
    #if it does, ensure that the essential attributes are correct
    pass
  #Now add all the little extras we may have
  tmp.completed = job['Completed']
  tmp.completion_date = str_to_dt(job['CompletionDate'])
  tmp.creation_date = str_to_dt(job['CreationDate'])
  tmp.inventory_size = job['InventorySizeInBytes']
  tmp.description = job['JobDescription']
  tmp.retrieval_range = job['RetrievalByteRange']
  tmp.SHA256_tree_hash = job['SHA256TreeHash']
  tmp.SNS_topic = job['SNSTopic']
  tmp.status_code = job['StatusCode']
  tmp.status_message = job['StatusMessage']
  db.session.add(tmp)
  db.session.commit()
  return tmp

def process_archive(archive,vault):
  """
  Like above
  """
  #Check if it exists
  tmp = Archive.query.filter_by(archive_id = archive["ArchiveId"]).first()
  #If it doesn't, first thing is to add it
  if tmp is None:
    tmp = Archive(archive["ArchiveId"],archive["ArchiveDescription"],vault)
  #Now make everything what it should be...
  tmp.description = archive["ArchiveDescription"]
  tmp.insertion_date = str_to_dt(archive["CreationDate"])
  tmp.SHA256_tree_hash = archive["SHA256TreeHash"]
  tmp.filesize = archive["Size"]
  #Try and fill in metadata from the description if possible
  tmp.populate_from_description()
  db.session.add(tmp)
  db.session.commit()
  return tmp

#def upload_archive(fname,vault,chunk=None,true_path=None):
#  """
#  Usually fname is just the name of a temporary file, in which
#  case the true pathname of the file must be given to true_path
#  or the database will record garbage for the filename and path
#  """
#  if true_path is None:
#    true_path = fname
#  if not os.path.isfile(fname):
#    print("%s is not a valid file!  Upload failed!" % fname)
#    return None
#  if chunk is None:
#    chunk=app.config["CHUNK_SIZE"]
#  handler = get_handler()
#  uploader = ConcurrentUploader(handler,str(vault.name),part_size=chunk)
#  print("Beginning upload of file %s.  Please by patient, there is no progress bar..." % fname)
#  #description = raw_input("Enter description for file %s (enter nothing to use filename):"%fname)
#  description="Automatic upload of "+true_path
#  archive_id = uploader.upload(fname,description)
#  print("Successfully uploaded %s" % fname)
#  filesize = os.path.getsize(fname) 
#  filename = os.path.basename(true_path)
#  fullpath = true_path
#  archive = Archive(archive_id,description,vault,filename=filename,fullpath=fullpath,filesize=filesize)
#  db.session.add(archive)
#  db.session.commit()
#  return archive
