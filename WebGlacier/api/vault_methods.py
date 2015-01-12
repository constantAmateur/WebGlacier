"""
File that contains all the non-visible routes
that are used for communicating with the app.

This particular file contains routines that
are used for vault specific tasks.
"""

#External dependency imports
import tempfile,os

#Flask imports
from flask import request, redirect, url_for, abort

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.models import Vault, Archive, Job
from WebGlacier.lib.app import get_valid_clients, get_handler
from WebGlacier.lib.glacier import process_job, download_archive, upload_archive, process_archive, upload_archive_queue

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/submit",methods=['POST'])
def multi_dispatch(vault_name):
  """
  This should handle the big form submit.  That is, when we hit any of the
  buttons on the vault pages, it should end up here and do what was
  asked after some validation.
  """
  #Get the valid clients and make sure the one we selected is one of them
  clients = get_valid_clients()
  client = request.form.get("client_select")
  if client in clients:
    #We've got a valid client, save it
    WG.app.config['current_client'] = client
  print client
  #Are we just changing vaults, if so don't need the extra validation stuff
  if 'vault_select_pressed' in request.form:
    print "Changing vault"
    #Change vault and we're done
    return redirect(url_for("vault_view",vault_name=request.form['vault_select']))
  #Either we're done, or we need to do something else
  if client in clients:
    #Did we press upload?
    if 'upload_pressed' in request.form:
      #Extract description
      description=request.form.get('upload_description','')
      if description=="Description of file.":
        description=''
      #Do upload
      print "Doing upload from vault %s with path %s"%(vault_name,request.form['upload_path'])
      upload_archive_queue(vault_name,request.form['upload_path'],client,description)
    elif 'download' in request.form:
      #Do download
      print "Doing download from vault %s with id %s"%(vault_name,request.form['download'])
      download_archive(vault_name,request.form['download'],client)
  else:
    if 'add_archive_via_server' in request.form:
      print "Doing upload via server with request.form %s and request.files %s"%(str(request.form),str(request.files))
      #Need to do the via elsewhere upload.
      return upload_file(vault_name)
    print "Invalid client, doing nothing"
  print request.form
  print WG.queues
  return redirect(request.referrer)

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/addfile",methods=["POST"])
def upload_file(vault_name):
  """
  Handle file upload
  """
  print "Got into this with vault_name=%s"%vault_name
  handler = get_handler()
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  print region,vault
  if vault is None:
    abort(401)
  if vault.lock:
    abort(401)
  print "Do we has request?"
  print request
  print request.files
  file = request.files['file']
  if file:
    print "starting to do stuff with file"
    #Save to a temporary file on the server...  Needs to be done for calculating hashes and the like.
    tmp=tempfile.NamedTemporaryFile(dir=WG.app.config["TEMP_FOLDER"],delete=False)
    file.save(tmp)
    print "Server has accepted payload"
    description=request.form.get('upload_description','')
    if description=="Description of file.":
      description=''
    upload_archive(tmp.name,vault,file.filename,description=description)
    tmp.close()
    return redirect(request.referrer)

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/download",methods=["GET"])
def download_file(vault_name):
  """
  Download a file if the link is available...
  """
  handler = get_handler()
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Need to get the archive too...
  if 'archive_id' not in request.args:
    abort(401)
  archive = Archive.query.filter_by(archive_id=request.args['archive_id']).first()
  if archive is None:
    abort(401)
  if archive.filename!="NOT_GIVEN":
    fname=archive.filename
  else:
    fname=app.config["UNKNOWN_FILENAME"]
  #Are we serving from cache?
  #cache = archive.cached()
  #if cache==1:
  #  print "Serving from cache."
  #  return send_from_directory(os.path.join(app.config["LOCAL_CACHE"],region,vault.name),archive.archive_id,attachment_filename=fname,as_attachment=True)
  #Is there a finished job knocking about?
  job=archive.jobs.filter_by(action='download',completed=True,live=True,status_message="Succeeded").first()
  if job is None:
    abort(401)
  #OK, everything exists, go ahead...
  if False and cache==2:
    #Save to cache whilst serving
    print "Adding to cache."
    f = open(os.path.join(app.config["LOCAL_CACHE"],region,vault.name,archive.archive_id),'wb')
  else:
    #Don't add to cache, just serve
    print "No cache, only serve."
    f = None
  h=Headers()
  h.add("Content-Disposition",'attachment;filename="'+fname+'"')
  return Response(stream_with_context(job.stream_output(file_handler=f)),headers=h)

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/checkjobstatus")
def check_job_status(vault_name):
  """
  Pretty self explanatory isn't it?
  """
  handler = get_handler()
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Get the live jobs from Amazon
  live_jobs = handler.list_jobs(vault.name)
  #First update/add all of them to db
  for job in live_jobs['JobList']:
    process_job(job,vault)
  #Then kill any ones that are in our db and should be dead
  jobs = vault.jobs.filter_by(live=True).all()
  live_ids = [x["JobId"] for x in live_jobs['JobList']]
  for job in jobs:
    if job.job_id not in live_ids:
      job.live=False
      WG.db.session.add(job)
      WG.db.session.commit()
  return redirect(request.referrer)
 
@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/runjobs",methods=["GET"])
def run_jobs(vault_name):
  """
  Execute a completed job.  If not completed, updates its status.
  """
  handler = get_handler()
  #Need to get the vault as always...
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Get the job from our local db
  job=Job.query.filter_by(job_id=(request.args['job_id'])).first()
  #If we don't have the job, or our records show it's incomplete, check with amazon
  if job is None or not job.completed:
    if vault.lock:
      abort(401)
    job=process_job(handler.describe_job(vault.name,request.args['job_id']),vault)
  #If it's still none, something went wrong...
  if job is None or not job.completed or not job.live or not job.status_code=="Succeeded":
    abort(401)
  #Now we have the job, get its output
  if job.action=='list':
    dat=handler.get_job_output(vault.name,job.job_id)
    for archive in dat["ArchiveList"]:
      process_archive(archive,vault)
    vault.lock=False
    WG.db.session.add(vault)
    WG.db.session.commit()
  elif job.action=='download':
    pass
  #return redirect(request.referrer)
  return redirect(url_for("vault_view",vault_name=vault.name))
 
@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/getinventory",methods=["GET"])
def get_inventory(vault_name):
  """
  Initiates an inventory job for the specified vault.
  Currently lacks any checks on if it's a good idea to submit another of these jobs
  """
  handler = get_handler()
  #Need to get the vault...
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Already asked for one, don't need another...
  if vault.lock:
    abort(401)
  def_opts={"Description":"Auto-made inventory job.",
    "Type":"inventory-retrieval","Format":"JSON"}
  job_id = handler.initiate_job(vault.name, def_opts)
  #Lock the vault...
  vault.lock=True
  WG.db.session.add(vault)
  WG.db.session.commit()
  #Add the job to the database
  job=process_job(handler.describe_job(vault.name,job_id["JobId"]),vault)
  return redirect(request.referrer)

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/getarchive",methods=["GET"])
def request_archive(vault_name):
  """
  Asks glacier to get your data.  You'll have to wait for it to get back first...
  """
  handler = get_handler()
  #Need to get the vault as always...
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Need to get the archive too...
  if 'archive_id' not in request.args:
    abort(401)
  archive = Archive.query.filter_by(archive_id=request.args['archive_id']).first()
  if archive is None:
    abort(401)
  #OK, everything exists, go ahead...
  def_opts={"Description":"Fetch archive.",
    "Type":"archive-retrieval",
    "ArchiveId":archive.archive_id}
  job_id = handler.initiate_job(vault.name, def_opts)
  job=process_job(handler.describe_job(vault.name,job_id["JobId"]),vault)
  return redirect(request.referrer)

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/action/deletearchive",methods=["GET"])
def delete_archive(vault_name):
  """
  Delete archive from glacier's servers
  """
  handler = get_handler()
  #Need to get the vault as always...
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None or vault.lock:
    abort(401)
  #Need to get the archive too...
  if 'archive_id' not in request.args:
    abort(401)
  archive = Archive.query.filter_by(archive_id=request.args['archive_id']).first()
  if archive is None:
    abort(401)
  #OK, everything exists, go ahead...
  handler.delete_archive(vault.name,archive.archive_id)
  #Delete the archive and any jobs associated with it...
  for job in archive.jobs:
    WG.db.session.delete(job)
  WG.db.session.delete(archive)
  WG.db.session.commit()
  return redirect(request.referrer)
