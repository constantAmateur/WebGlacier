from flask import request
from flask import abort

from WebGlacier import app, db
from models import Vault,Archive,Job

#These are methods that should be used by the remote client...
@app.route('/glacier/add/job',methods=["POST"])
def add_job():
  #Need to at least have these things
  if 'job_id' not in request.args or 'action' not in request.args:
    abort(401)
  if 'vault_name' not in request.args:
    abort(401)
  #Try and get the vault
  region = 'eu-west-1'
  if 'region' in request.args:
    region=request.args['region']
  vault = Vault.query.filter_by(region=region,name=request.args['vault_name']).first()
  if vault is None:
    abort(401)
  #OK, we've got the vault, now get the archive if we need it...
  if request.args['action']=='download':
    if 'archive_id' not in request.args:
      abort(401)
    archive = Archive.query.filter_by(achive_id=request.args['archive_id']).first()
    if archive is None:
      abort(401)
  else:
    archive=None
  #Sweet, got everything, now we make the entry
  kw=dict()
  if 'completed' in request.args:
    kw['completed']=bool(request.args['completed'])
  if 'statuscode' in request.args:
    kw['statusCode']=request.args['statuscode']
  if 'statusmessage' in request.args:
    kw['statusMessage']=request.args['statusmessage']
  job = Job(request.args['job_id'],request.args['action'],vault,archive,**kw)
  db.session.add(job)
  db.session.commit()
  return "Added job %s.\n" % job.job_id

#To be used by remote client
@app.route('/glacier/add/vault',methods=["POST"])
def add_vault():
  #Need to at least have these things
  if 'name' not in request.args:
    abort(401)
  #Try and get the vault
  region = 'eu-west-1'
  if 'region' in request.args:
    region=request.args['region']
  vault = Vault.query.filter_by(region=region,name=request.args['name']).first()
  if vault is not None:
    abort(401)
  #OK, doesn't already exist, so try and add it...
  vault = Vault(request.args['name'],region)
  db.session.add(vault)
  db.session.commit()
  return "Added vault %s to region %s.\n" % (vault.name,vault.region)

#To be used by remote client
@app.route('/glacier/add/archive',methods=["POST"])
def add_archive():
  #Need to at least have these things
  if 'archive_id' not in request.args or 'description' not in request.args:
    abort(401)
  if 'vault_name' not in request.args:
    abort(401)
  #Try and get the vault
  region = 'eu-west-1'
  if 'region' in request.args:
    region=request.args['region']
  vault = Vault.query.filter_by(region=region,name=request.args['vault_name']).first()
  if vault is None:
    abort(401)
  #OK, we're all good, get any extra info...
  kw=dict()
  if 'filename' in request.args:
    kw['filename']=request.args['filename']
  if 'fullpath' in request.args:
    kw['fullpath']=request.args['fullpath']
  if 'filesize' in request.args:
    kw['filesize']=int(request.args['filesize'])
  archive = Archive(request.args['archive_id'],request.args['description'],vault,**kw)
  db.session.add(archive)
  db.session.commit()
  return "Added archive %s to vault %s.\n" % (archive.archive_id,vault.name)


