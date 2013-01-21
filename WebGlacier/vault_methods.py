from flask import request, session
from flask import abort, redirect, url_for
from flask import send_from_directory
from werkzeug import secure_filename
from tempfile import mkstemp
import os

from WebGlacier import app,  db
from WebGlacier.utils import get_set_region, get_handler, process_job, process_archive,upload_archive
from models import Vault,Archive,Job

@app.route("/glacier/<vault_name>/action/checkjobstatus")
def check_job_status(vault_name):
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
      db.session.add(job)
      db.session.commit()
  return redirect(url_for('main'))
 
@app.route("/glacier/<vault_name>/action/addfile",methods=["GET","POST"])
def upload_file(vault_name):
  region = get_set_region()
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  if vault.lock:
    abort(401)
  if request.method == "POST":
    file = request.files['file']
    if file:
      filename = secure_filename(file.filename)
      file.save(os.path.join(app.config["UPLOAD_FOLDER"],filename))
      print "Server has accepted payload"
      archive = upload_archive(os.path.join(app.config["UPLOAD_FOLDER"],filename),vault)
      return redirect(url_for('main'))
  return '''
  <!doctype html>
  <title>Upload new File</title>
  <h1>Upload new File</h1>
  <form action="" method=post enctype=multipart/form-data>
    <p><input type=file name=file>
       <input type=submit value=Upload>
  </form>
  '''

@app.route("/glacier/<vault_name>/action/runjobs",methods=["GET"])
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
  if job.action=='download':
    pass
  elif job.action=='list':
    dat=handler.get_job_output(vault.name,job.job_id)
    for archive in dat["ArchiveList"]:
      process_archive(archive,vault)
    vault.lock=False
    db.session.add(vault)
    db.session.commit()
  return redirect(url_for('main'))
 
@app.route("/glacier/<vault_name>/action/getinventory",methods=["GET"])
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
  db.session.add(vault)
  db.session.commit()
  #Add the job to the database
  job=process_job(handler.describe_job(vault.name,job_id["JobId"]),vault)
  return redirect(url_for('main'))

@app.route("/glacier/<vault_name>/action/getarchive",methods=["GET"])
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
  return redirect(url_for('main'))

@app.route("/glacier/<vault_name>/action/deletearchive",methods=["GET"])
def delete_archive(vault_name):
  """
  Asks glacier to get your data.  You'll have to wait for it to get back first...
  """
  handler = get_handler()
  #Need to get the vault as always...
  region = handler.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  if vault.lock:
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
    db.session.delete(job)
  db.session.delete(archive)
  db.session.commit()
  return redirect(url_for('main'))

@app.route("/glacier/<vault_name>/action/download",methods=["GET"])
def dload_archive(vault_name):
  """
  Asks glacier to get your data.  You'll have to wait for it to get back first...
  """
  handler = get_handler(2)
  region = handler.layer1.region.name
  vault = Vault.query.filter_by(name=vault_name,region=region).first()
  if vault is None:
    abort(401)
  #Need to get the archive too...
  if 'archive_id' not in request.args:
    abort(401)
  archive = Archive.query.filter_by(archive_id=request.args['archive_id']).first()
  if archive is None:
    abort(401)
  #Is there a finished job knocking about?
  job=archive.jobs.filter_by(action='download',completed=True).first()
  if job is None:
    abort(401)
  #OK, everything exists, go ahead...
  vv = handler.get_vault(str(vault.name))
  jj = vv.get_job(str(job.job_id))
  #Make a temp file and close it, but keep its name
  t,fnom = mkstemp(dir=app.config['UPLOAD_FOLDER'])
  os.fdopen(t).close()
  jj.download_to_file(fnom)
  #And do what with it?
  if archive.filename!="NOT_GIVEN":
    ret_name = archive.filename
  else:
    ret_name = app.config["UNKNOWN_FILENAME"]
  return send_from_directory(app.config["UPLOAD_FOLDER"],os.path.basename(fnom),attachment_filename=ret_name,as_attachment=True)


