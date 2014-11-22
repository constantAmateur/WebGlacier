from flask import redirect, url_for
from flask import render_template
from flask import request
from forms import SettingsForm
from datetime import datetime

from WebGlacier import app, handlers, db, live_clients
from WebGlacier import queues
from WebGlacier.models import Archive
from WebGlacier.lib.db import get_set_region,get_valid_clients
from WebGlacier.lib.misc import deunicode
from WebGlacier.vault_methods import check_job_status,download_archive,upload_archive
from WebGlacier.region_methods import get_vaults
from models import Vault
import os,re
import json
import WebGlacier


@app.route("/glacier/baba",methods=['POST'])
def multi_dispatch():
  """
  This should handle the big form submit.  That is, when we hit any of the
  buttons on the vault pages, it should end up hear and do what was
  asked after some validation.
  """
  #Get the valid clients and make sure the one we selected is one of them
  clients = get_valid_clients()
  client = request.form.get("client_select")
  if client in clients:
    #We've got a valid client, save it
    app.config['current_client'] = client
  print client
  #Are we just changing vaults, if so don't need the extra validation stuff
  if 'vault_select_pressed' in request.form:
    print "Changing vault"
    #Change vault and we're done
    return redirect("/glacier/"+request.form['vault_select'])
  #Either we're done, or we need to do something else
  if client in clients:
    #Did we press upload?
    if 'upload_pressed' in request.form:
      #Extract description
      description=request.form['upload_description']
      if description=="Description of file.":
        description=''
      #Do upload
      print "Doing upload from vault %s with path %s"%(request.form['vault_name'],request.form['upload_path'])
      upload_archive(request.form['vault_name'],request.form['upload_path'],client,description)
    elif 'download' in request.form:
      #Do download
      print "Doing download from vault %s with id %s"%(request.form['vault_name'],request.form['download'])
      download_archive(request.form['vault_name'],request.form['download'],client)
  else:
    print "Invalid client, doing nothing"
  print request.form
  print queues
  return redirect(request.referrer)

@app.route("/glacier/<vault_name>/")
def vault_view(vault_name):
  """
  Display the specified vault with all its contents...
  """
  region = get_set_region()
  vault = Vault.query.filter_by(region=region,name=vault_name).first()
  if vault is None:
    return redirect(url_for('main'))
  #Update the jobs
  null=check_job_status(vault_name)
  if vault.lock:
    #Check the jobs, execute the one we want if it's done
    live=vault.get_inventory_jobs()
    #Unlock if we have no live inventory jobs left, or the only live jobs left have completed
    if live is None or live[0].completed:
      #The successful option
      if live is not None:
        return redirect(url_for('run_jobs',vault_name=vault_name,job_id=live[0].job_id))
      vault.lock=False
      db.session.add(vault)
      db.session.commit()
  altvaults=Vault.query.filter_by(region=vault.region).all()
  altclients=queues.keys()
  altclients.sort()
  #Get any completed jobs
  live=vault.get_inventory_jobs()
  #Check the lock status and set the complete job if available
  inv_job=None
  if live is not None:
    for j in live:
      if not j.completed:
        #If there's an incomplete inventory job, make sure we're locked and finish
        if not vault.lock:
          vault.lock=True
          db.session.add(vault)
          db.session.commit()
        inv_job=None
        break
      elif j.status_code=="Succeeded":
        #There's at least one complete job
        #They're sorted by date, so the first one is what we want if there are more than one
        if inv_job is None:
          inv_job=url_for('run_jobs',vault_name=vault_name,job_id=j.job_id)
  return render_template("vault.html",vault=vault,altvaults=altvaults,inv_job=inv_job,clients=get_valid_clients())

@app.route("/glacier/command_queue",methods=['GET'])
def send_commands():
  """
  Main communication "socket" for client.  Informs the server
  that the client is alive and connected and the server returns
  any outstanding commands that are in the queue.
  """
  name = request.args.get('client_name','')
  qid = str(request.remote_addr) if name == '' else name+' ('+str(request.remote_addr) + ')'
  poll_freq = int(request.args.get('poll_freq',10))
  print "Just checking in!  It's me "+qid
  #Register this client in the live_client list (or update it)
  live_clients[qid]=[datetime.utcnow(),poll_freq,False]
  #Find the queue for the current machine, or return empty if nothing
  dat=queues.get(qid,{})
  if dat:
    #The client is about to be busy, so update live_clients to reflect that
    live_clients[qid][2]=True
  #Jsonify it and return it
  #dat=[{"action": "download", "hash": "ss2t3h542s1ntd1tns2hd3", "vault_name": "eu", "job_id": "2222sotnheus4t3h56s2nth4", "file_size": 1024},{"action": "download", "hash": "ss2t3h542s1ntd1tnsaa2hd3", "vault_name": "eu", "job_id": "2222sotnheus4t3h3456s2nth4", "file_size": 2024}]
  return json.dumps(dat), 200

@app.route("/glacier/command_returns",methods=['POST'])
def process_callbacks():
  """
  When the client has processed any commands in the queue, it will
  post any information needed by the server (such as the new archive id) 
  back at this url.
  Commands are then safely removed from the queue as they have been processed.
  """
  name = request.args.get('client_name','')
  qid = str(request.remote_addr) if name == '' else name+' ('+str(request.remote_addr) + ')'
  dat = deunicode(json.loads(request.get_data(as_text=True)))
  print dat
  for k,val in dat.iteritems():
    #k is the hash, dat the data...
    #A completed download job
    if k[0]=='d':
      print "Completed download job.  Returned:",val
      if qid not in queues or k not in queues[qid]:
        print "Download job not found in queue.  Strange..."
      else:
        _ = queues[qid].pop(k)
    elif k[0]=='u':
      print "Completed upload job.  Returned:",val
      #Create a db object for it (provided it doesn't already exist)
      vault = Vault.query.filter_by(name=val['vault_name'],region=val['region_name']).first()
      if vault is None:
        print "Vault not found..."
        abort(401) 
      archive = Archive.query.filter_by(archive_id=val['archive_id']).first()
      if archive is not None:
        print "Archive already added.  We shouldn't be seeing this really..."
      else:
        archive = Archive(val['archive_id'],val['description'],vault,filename=val['file_name'],fullpath=val['true_path'],filesize=val['file_size'],md5sum=val['md5sum'])
        archive.insertion_date = datetime.fromtimestamp(int(val['insert_time']))
        db.session.add(archive)
        db.session.commit()
      if qid not in queues or k not in queues[qid]:
        print "Upload job not found in queue.  Strange..."
      else:
        _ = queues[qid].pop(k)
  print queues
  return 'Processed'

@app.route("/glacier/settings/",methods=["GET","POST"])
def settings():
  """
  The settings page.  Where you can edit the settings.
  """
  form=SettingsForm(**app.config)
  if form.validate_on_submit():
    cfile=os.path.join(WebGlacier.__path__[0],"settings.cfg")
    save_settings(form.data,cfile)
    app.config.from_pyfile("settings.cfg")
    app.config.from_envvar("GLACIER_CONFIG",silent=True)
    return redirect(url_for('settings'))
  rnom=get_set_region()
  return render_template("settings.html",config=app.config,regions=handlers.keys(),rnom=rnom,form=form,clients=get_valid_clients())

def save_settings(data,cfile):
  """
  Update the settings file specified in cfile with
  the data in data.
  """
  #Options that if empty, don't change
  empty_no_change=["SQL_PASSWORD"]
  no_quote=["DEBUG","APP_HOST","SQLALCHEMY_POOL_RECYCLE","UCHUNK","DCHUNK","SQL_PORT"]
  #First get the file name of the current settings file
  nome=os.environ.get("GLACIER_CONFIG",cfile)
  dat=open(nome,'r').read()
  #Save either the current setting, or the new one if validated
  for conf in data.keys():
    if conf in empty_no_change and data[conf]=='':
      continue
    if data[conf]!=app.config[conf]:
      if conf in no_quote:
        dat=re.sub("(^|\n)"+str(conf)+"( |=).*","\\1"+str(conf)+" = "+str(data[conf]),dat)
      else:
        dat=re.sub("(^|\n)"+str(conf)+"( |=).*",'\\1'+str(conf)+' = """'+str(data[conf])+'"""',dat)
  f=open(nome,'w')
  f.write(dat)
  f.close()
 
@app.route("/glacier/",methods=["GET"])
def main():
  """The main interface for the glacier database."""
  if 'vault_select' in request.args:
    return redirect("/glacier/"+request.args['vault_select'])
  region = get_set_region()
  #Update from server
  null = get_vaults()
  #Get all the vaults
  vaults = Vault.query.filter_by(region=region)
  #Render them all nicely
  return render_template("main.html",vaults=vaults,rnom=region,regions=handlers.keys(),clients=get_valid_clients())
