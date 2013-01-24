from flask import request, session
from boto.glacier.concurrent import ConcurrentUploader
import os

from WebGlacier import app, handlers, db
from models import Vault,Archive,Job

def ensure_path(tgt):
  """
  Makes sure the directory needed to store this file exits
  """
  directory=os.path.dirname(tgt)
  if not os.path.exists(directory):
    os.makedirs(directory)

def get_set_region():
  """
  Gets the current region by looking first in url args, then in the session object, finally reverting to default.
  """
  if 'region' in request.args and request.args['region'] in handlers:
    return request.args['region']
  elif 'region' in session and session['region'] in handlers:
    return session['region']
  return app.config["DEFAULT_REGION"]

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
  tmp.creation_date = vault["CreationDate"]
  tmp.ARN = vault['VaultARN']
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
  tmp.completion_date = job['CompletionDate']
  tmp.creation_date = job['CreationDate']
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
  tmp.insertion_date = archive["CreationDate"]
  tmp.SHA256_tree_hash = archive["SHA256TreeHash"]
  tmp.filesize = archive["Size"]
  db.session.add(tmp)
  db.session.commit()
  return tmp

def upload_archive(fname,vault,chunk=None):
  if not os.path.isfile(fname):
    print("%s is not a valid file!  Upload failed!" % fname)
    return None
  if chunk is None:
    chunk=app.config["CHUNK_SIZE"]
  handler = get_handler()
  uploader = ConcurrentUploader(handler,str(vault.name),part_size=chunk)
  print("Beginning upload of file %s.  Please by patient, there is no progress bar..." % fname)
  #description = raw_input("Enter description for file %s (enter nothing to use filename):"%fname)
  description="Automatic upload of "+fname
  archive_id = uploader.upload(fname,description)
  print("Successfully uploaded %s" % fname)
  filesize = os.path.getsize(fname) 
  filename = os.path.basename(fname)
  fullpath = os.path.abspath(fname) 
  archive = Archive(archive_id,description,vault,filename=filename,fullpath=fullpath,filesize=filesize)
  db.session.add(archive)
  db.session.commit()
  return archive
