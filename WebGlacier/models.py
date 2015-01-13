"""
Defines database models for the SQL database.
"""

#External dependency imports
import os,math,subprocess,re
from datetime import datetime

#Flask imports
from flask import request

#WebGlacier imports
import WebGlacier as WG
from WebGlacier import db
from WebGlacier.lib.misc import human_readable, ensure_path
from WebGlacier.lib.app import get_handler

class Archive(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  #These three are the key bits of info stored on amazon and are required
  archive_id = db.Column(db.String(200), unique=True)
  description = db.Column(db.Text)
  vault_id = db.Column(db.Integer, db.ForeignKey('vault.id'))
  #Other stuff that you should give me, but I'll live without it if you don't give it to me
  filename = db.Column(db.Text)
  fullpath = db.Column(db.Text)
  filesize = db.Column(db.Integer)
  insertion_date = db.Column(db.DateTime)
  md5sum = db.Column(db.Text)
  #The amazon crap
  SHA256_tree_hash = db.Column(db.String(256))
  #the backref thing gives vault instances the archives property, which can be used for cool shit like queries...
  vault = db.relationship("Vault",
    backref=db.backref("archives", lazy='dynamic'))
  #A pattern to convert descriptions to other things
  description_pattern = re.compile(r"(?P<main>.*?)\\nUploaded at (?P<utime>.*?)\\nFull path (?P<path>.*?)\\nFile size (?P<size>.*?)\\nMD5 (?P<md5>.*?)\\nSource machine id (?P<id>.*?)\\n")

  def __init__(self,archive_id,description,vault,filename=None,filesize=None,fullpath=None,tree_hash='',md5sum=''):
    self.archive_id = archive_id
    self.description = description
    self.vault = vault
    if filename is None:
      filename="NOT_GIVEN"
    self.filename=filename
    if fullpath is None:
      fullpath="NOT_GIVEN"
    self.fullpath=fullpath
    if filesize is None:
      filesize=0
    self.filesize=filesize
    insertion_date = datetime.utcnow()
    self.insertion_date = insertion_date
    self.md5sum=md5sum
    self.SHA256_tree_hash = tree_hash

  def __repr__(self):
    return '<Archive %r>' % self.archive_id

  @property
  def human_size(self):
    return human_readable(self.filesize)

  @property
  def short_description(self):
    """
    The description created by WebGlacier includes a bunch of metadata
    which you don't usually want to display.  This will strip it out if it
    exists.
    """
    me = self.description_pattern.match(self.description)
    return me.group('main') if me else self.description

  def populate_from_description(self):
    """
    If the description matches the pattern provided, we can use it to 
    populate the different fields of the object.
    """
    me = self.description_pattern.match(self.description)
    if me is None:
      if WG.app.config.get("VERBOSE",False):
        print "Description does not match expected pattern, cannot populate fields."
    else:
      self.insertion_date = datetime.fromtimestamp(int(float(me.group('utime'))))
      self.fullpath = me.group('path')
      self.filename = os.path.basename(me.group('path'))
      self.filesize = int(me.group('size'))
      self.md5sum = me.group('md5')
      #If we start storing machine id, save it here...

  def get_download_jobs(self):
    """
    Returns any pending or completed download jobs (sorted by either completion or insertion date)
    If there are none of either, None is returned
    """
    active = self.jobs.filter_by(live=True,action='download').all()
    if len(active)==0:
      return None
    done = [x for x in active if x.completed and x.status_message=="Succeeded"]
    #One of them succeeded, so present the link
    if len(done)!=0:
      done.sort(key=lambda x: x.completion_date,reverse=True)
      return done
    #If none of them have finished yet, return them
    pending = [x for x in active if not x.completed]
    if len(pending)!=0:
      pending.sort(key=lambda x: x.creation_date,reverse=True)
      return pending
    return None

class Job(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  #The amazon job_id
  job_id = db.Column(db.String(200), unique=True)
  #Type of job, either list or download
  action = db.Column(db.String(50))
  allowed_actions = ['list','download']
  #What vault is it operating on?
  vault_id = db.Column(db.Integer, db.ForeignKey("vault.id"))
  vault = db.relationship("Vault",
    backref = db.backref("jobs", lazy="dynamic"))
  #What archive is it operating on (required if download, ignored otherwise)?
  archive_id = db.Column(db.Integer, db.ForeignKey("archive.id"))
  archive = db.relationship("Archive",
    backref = db.backref("jobs", lazy='dynamic'))
  #The extra stuff, which is not always needed
  #Is this job complete or not?
  completed = db.Column(db.Boolean)
  #When did it finish
  completion_date = db.Column(db.DateTime)
  #When was it created
  creation_date = db.Column(db.DateTime)
  description = db.Column(db.Text)
  #For downloading, 
  retrieval_range = db.Column(db.String(100))
  status_code = db.Column(db.String(100))
  status_message = db.Column(db.Text)
  #Not sure what these are exactly...
  inventory_size = db.Column(db.Integer)
  SHA256_tree_hash = db.Column(db.String(256))
  SNS_topic = db.Column(db.String(100))
  #Whether the job still exists or not
  live = db.Column(db.Boolean)

  def __init__(self,job_id,action,vault,archive=None,completed=False,completion_date=None, 
      creation_date = None, description='', retrieval_range ='',
      status_code='', status_message='', inventory_size = 0, tree_hash = '',
      SNS_topic = '', live=True):
    self.job_id = job_id
    if action not in self.allowed_actions:
      raise ValueError("Job must be one of "+str(self.allowed_actions))
    self.action = action
    self.vault = vault
    if action=='list':
      archive = None
      retrieval_range = ''
    elif action=='download':
      if archive is None:
        #It's possible that the job points at a deleted archive...
        pass
      inventory_size = 0
      #Maybe the tree hash here?
    self.archive = archive
    self.completed = completed
    self.completion_date = completion_date
    self.creation_date = creation_date
    self.description = description
    self.retrieval_range = retrieval_range
    self.status_code = status_code
    self.status_message = status_message
    #The weird things
    self.inventory_size = inventory_size
    self.SHA256_tree_hash = tree_hash
    self.SNS_topic = SNS_topic
    #Does it still exist
    self.live = True
    
  def stream_output(self,chunk_size=None,file_handler=None):
    """
    A generator that can be used to stream a download job from Amazon's
    servers without saving it locally.  Obviously the job must be live,
    complete and successful.  The database values are taken to be true
    for each of these, so it makes sense to run this straight after
    checking the status of jobs.
    chunk_size has its usual meaning and will default to the config value
    if not given
    If file_handler is a file object, which should be open for writing,
    then in addition to streaming the response, the object will be written
    to file.  The object will be closed after the last chunk has been processed.
    """
    handler = get_handler(self.vault.region)
    if self.action!='download':
      raise TypeError("Can only stream download jobs")
    if not self.live or not self.completed:
      raise AttributeError("Job is not live and complete.")
    if chunk_size is None:
      chunk_size=int(WG.app.config.get('CHUNK_SIZE',1048576))
    file_size = self.archive.filesize
    vault_name = self.vault.name
    job_id = self.job_id
    num_chunks = int(math.ceil(file_size / float(chunk_size)))
    for i in xrange(num_chunks):
      byte_range = ((i * chunk_size), ((i + 1) * chunk_size) - 1)
      response = handler.get_job_output(vault_name,job_id,byte_range)
      if file_handler:
        file_handler.write(response.read())
        #Close after last chunk
        if i==num_chunks-1:
          file_handler.close()
      yield response.read()

  def __repr__(self):
    return '<Job (%r) %r>' %(self.action,self.job_id)

class Vault(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(100))
  region = db.Column(db.String(50))
  creation_date = db.Column(db.DateTime)
  ARN = db.Column(db.String(200))
  #Things that you should be able to get from the local db anyway...
  last_inventory_date = db.Column(db.DateTime)
  no_of_archives = db.Column(db.Integer)
  size = db.Column(db.Integer)
  #If trying to initialise from server, don't let anything else be done
  lock = db.Column(db.Boolean)

  def __init__(self,name,region='eu-west-1',ARN='',creation_date=None,inv=None,nofiles=0,size=0,lock=False):
    self.name = name
    self.region = region
    self.ARN = ARN
    if creation_date is None:
      creation_date = datetime.utcnow()
    self.creation_date = creation_date
    self.last_inventory_date = inv
    self.no_of_archives = nofiles
    self.size = size
    self.lock = lock

  def __repr__(self):
    return '<Vault %r>' % self.name

  @property
  def human_size(self):
    return human_readable(self.size)

  def get_inventory_jobs(self):
    """
    If there is any outstanding inventory retrieval job, return it.  Otherwise return the
    most recently completed, live, inventory job or None.
    """
    live = self.jobs.filter_by(live=True,action='list').all()
    #If there aren't any, none to return
    if len(live)==0:
      return None
    #If any of them are yet to be completed
    pending = [x for x in live if not x.completed]
    if len(pending)!=0:
      pending.sort(key=lambda x: x.creation_date,reverse=True)
      return pending
    #If they're all done
    done = [x for x in live if x.completed and x.status_message=="Succeeded"]
    #One of them succeeded, so present the link
    if len(done)!=0:
      done.sort(key=lambda x: x.completion_date,reverse=True)
      return done
    #If all live inventory jobs failed...
    return None
