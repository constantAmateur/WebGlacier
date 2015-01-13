"""
Routines for creating glacier objects in the database language
and various other glacier related functions.
"""

#External dependency imports
import os,time
from datetime import datetime
from boto.glacier.concurrent import ConcurrentUploader

#Flask imports
from flask import request, abort

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.models import Job, Vault, Archive
from WebGlacier.lib.misc import str_to_dt, chunkedmd5
from WebGlacier.lib.app import get_set_region, get_handler

def process_job(job,vault):
  """
  job should be a dictionary returned by amazon with all the pertinent info.
  vault is a vault object
  returns the newly created/updated job object created
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
        if WG.app.config.get("VERBOSE",False):
          print "Job points at unknown archive."
      tmp = Job(action='download',job_id = job['JobId'],vault=vault,archive=archive)
  else:
    #Ensure archive is set correctly
    if tmp.archive is None:
      archive = Archive.query.filter_by(archive_id = job["ArchiveId"]).first()
      if archive is None:
        #Archive either not added, or deleted
        if WG.app.config.get("VERBOSE",False):
          print "Job points at unknown archive."
      else:
        tmp.archive=archive
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
  WG.db.session.add(tmp)
  WG.db.session.commit()
  return tmp

def process_vault(vault):
  """
  vault should be a dictionary returned from list_vaults (from amazon).
  returns the newly created vault object
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
  WG.db.session.add(tmp)
  WG.db.session.commit()
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
  WG.db.session.add(tmp)
  WG.db.session.commit()
  return tmp

def download_archive(vault_name,archive_id,client):
  """
  Puts a download job in the queue, after some minor validation.
  """
  if WG.app.config.get("VERBOSE",False):
    print "Comm queues are %s"%str(WG.queues)
  region = get_set_region()
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Need to get the archive too...
  archive = Archive.query.filter_by(archive_id=archive_id).first()
  if archive is None:
    abort(401)
  if archive.filename!="NOT_GIVEN":
    fname=archive.filename
  else:
    fname=WG.app.config["UNKNOWN_FILENAME"]
  #Is there a finished job knocking about?
  job=archive.jobs.filter_by(action='download',completed=True,live=True,status_message="Succeeded").first()
  if job is None:
    abort(401)
  #Very well, stick a job in the queue
  command = {}
  command['action']='DOWNLOAD'
  command['access_key']=WG.app.config['AWS_ACCESS_KEY']
  command['secret_access_key']=WG.app.config["AWS_SECRET_ACCESS_KEY"]
  command['region_name']=region
  command['file_name']=fname
  command['file_size']=job.archive.filesize
  command['vault_name']=vault.name
  command['job_id']=job.job_id
  command['target']=request.remote_addr
  k='d'+str(time.time())+"_"+str(os.urandom(16).encode('hex'))[:4]
  if client not in WG.queues:
    WG.queues[client]={}
  WG.queues[client][k] = command

def upload_archive_queue(vault_name,path,client,description=''):
  """
  Create an upload job after some minor validation.
  """
  region = get_set_region()
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  if vault.lock:
    abort(401)
  command = {}
  command['action']='UPLOAD'
  command['access_key']=WG.app.config['AWS_ACCESS_KEY']
  command['secret_access_key']=WG.app.config["AWS_SECRET_ACCESS_KEY"]
  command['region_name']=region
  command['vault_name']=vault.name
  command['file_pattern']=path
  command['target']=request.remote_addr
  command['description']=description
  k='u'+str(time.time())+"_"+str(os.urandom(16).encode('hex'))[:4]
  if client not in WG.queues:
    WG.queues[client]={}
  WG.queues[client][k]=command

def upload_archive(fname,vault,real_name,chunk=None,description=''):
  """
  Upload a file to glacier via the web-server.
  """
  if not os.path.isfile(fname):
    print("%s is not a valid file!  Upload failed!" % fname)
    return None
  if chunk is None:
    chunk=WG.app.config.get("CHUNK_SIZE",1048576)
  handler = get_handler()
  uploader = ConcurrentUploader(handler,str(vault.name),part_size=chunk)
  if WG.app.config.get("VERBOSE",False):
    print("Beginning upload of file %s to Glacier.  Please by patient, there is no progress bar..." % fname)
  file_size = os.path.getsize(fname)
  csum = chunkedmd5(fname)
  itime=time.time()
  file_name = os.path.basename(real_name)
  machine_id = str(request.remote_addr)
  #Construct a meaningful description object for the file
  #The limits are that the description can be no more than 1024 characters in length and must use only ascii characters between 32 and 126 (i.e., 32<=ord(char)<=126)
  dscrip = description+'\\n'
  dscrip = dscrip + "Uploaded at "+str(itime)+'\\n'+ "Full path "+str(real_name)+'\\n'+ "File size "+str(file_size)+'\\n' + "MD5 "+str(csum)+'\\n' + "Source machine id "+machine_id+'\\n'
  archive_id = uploader.upload(fname,description)
  if WG.app.config.get("VERBOSE",False):
    print("Successfully uploaded %s" % fname)
  archive = Archive(archive_id,description,vault,filename=file_name,fullpath=real_name,filesize=file_size,md5sum=csum)
  archive.insertion_date = datetime.fromtimestamp(int(itime))
  WG.db.session.add(archive)
  WG.db.session.commit()
