from flask import redirect, url_for
from flask import render_template
from flask import request
from forms import SettingsForm

from WebGlacier import app, handlers, db
from WebGlacier.lib.db import get_set_region
from WebGlacier.vault_methods import check_job_status
from WebGlacier.region_methods import get_vaults
from models import Vault
import os,re

@app.route("/glacier/<vault_name>/")
def vault_view(vault_name):
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
  return render_template("vault.html",vault=vault,altvaults=altvaults,inv_job=inv_job)

@app.route("/glacier/settings/",methods=["GET","POST"])
def settings():
  form=SettingsForm(**app.config)
  if form.validate_on_submit():
    cfile=os.path.join(WebGlacier.__path__[0],"settings.cfg")
    save_settings(form.data,cfile)
    app.config.from_pyfile("settings.cfg")
    app.config.from_envvar("GLACIER_CONFIG",silent=True)
    return redirect(url_for('settings'))
  rnom=get_set_region()
  return render_template("settings.html",config=app.config,regions=handlers.keys(),rnom=rnom,form=form)

def save_settings(data,cfile):
  #Options that if empty, don't change
  empty_no_change=["SQL_PASSWORD"]
  no_quote=["DEBUG","APP_HOST","SQLALCHEMY_POOL_RECYCLE","CHUNK_SIZE","","SQL_PORT","LOCAL_CACHE_SIZE","LOCAL_CACHE_MAX_FILE_SIZE"]
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
  return render_template("main.html",vaults=vaults,rnom=region,regions=handlers.keys())
