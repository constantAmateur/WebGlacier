"""
File containing the routes and code to load all the pages
that the end user actually views.
"""

#External dependency imports
import os

#Flask imports
from flask import redirect, url_for, render_template, request, session

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.models import Vault
from WebGlacier.forms import SettingsForm
from WebGlacier.api.region_methods import get_vaults
from WebGlacier.api.vault_methods import check_job_status
from WebGlacier.lib.app import get_valid_clients, get_set_region, save_settings
from WebGlacier.lib.app import build_db_key,validate_db,validate_glacier, init_handlers_from_config

#Not a view, but where else am I going to put it?
@WG.app.before_request
def validate_connection():
  """
  The whole app is useless unless we have a database 
  to store things and a valid connection to Amazon
  Glacier.  So check that we do and redirect to 
  settings page if we don't.
  """
  #Make sure we have set a region
  if 'region' not in session:
    session['region'] = get_set_region()
  #Are we at a url where we don't need to check things?
  print request.endpoint
  if request.endpoint!='settings' and request.endpoint!='static':
    #If everything has passed before, assume it will again
    #Is the db connection OK?
    if not WG.validated_db:
      try: 
        key=build_db_key(WG.app.config["SQL_DIALECT"],WG.app.config["SQL_DATABASE_NAME"],WG.app.config["SQL_HOSTNAME"],WG.app.config["SQL_USERNAME"],WG.app.config["SQL_PASSWORD"],WG.app.config["SQL_DRIVER"],WG.app.config["SQL_PORT"])
        validate_db(key)
        WG.app.config["SQLALCHEMY_DATABASE_URI"]=key
        WG.db.create_all()
        WG.validated_db=True
      except:
        print "Can't connect to database."
        WG.validated_db=False
        raise ValueError
        return redirect(url_for('settings'))
    #Is the Amazon Glacier config okay?
    if not WG.validated_glacier:
      try:
        validate_glacier(WG.app.config["AWS_ACCESS_KEY"],WG.app.config["AWS_SECRET_ACCESS_KEY"],WG.app.config.get("DEFAULT_REGION"))
        init_handlers_from_config()
        WG.validated_glacier=True
      except:
        print "Can't connect to Glacier."
        WG.validated_glacier=False
        return redirect(url_for('settings'))


@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/",methods=["GET"])
def main():
  """The main interface for the glacier database."""
  region = get_set_region()
  #Update from server
  _ = get_vaults()
  #Get all the vaults
  vaults = Vault.query.filter_by(region=region)
  #Render them all nicely
  return render_template("main.html",vaults=vaults,rnom=region,regions=WG.handlers.keys(),clients=get_valid_clients())

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/<vault_name>/")
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
      WG.db.session.add(vault)
      WG.db.session.commit()
  altvaults=Vault.query.filter_by(region=vault.region).all()
  altclients=WG.queues.keys()
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
          WG.db.session.add(vault)
          WG.db.session.commit()
        inv_job=None
        break
      elif j.status_code=="Succeeded":
        #There's at least one complete job
        #They're sorted by date, so the first one is what we want if there are more than one
        if inv_job is None:
          inv_job=url_for('run_jobs',vault_name=vault_name,job_id=j.job_id)
  return render_template("vault.html",vault=vault,altvaults=altvaults,inv_job=inv_job,clients=get_valid_clients())

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/settings/",methods=["GET","POST"])
def settings():
  """
  The settings page.  Where you can edit the settings.
  """
  form=SettingsForm(**WG.app.config)
  if form.validate_on_submit():
    cfile=os.path.join(WG.__path__[0],"../settings.cfg")
    save_settings(form.data,cfile)
    WG.app.config.from_pyfile("../settings.cfg")
    WG.app.config.from_envvar("GLACIER_CONFIG",silent=True)
    return redirect(url_for('settings'))
  rnom=get_set_region()
  return render_template("settings.html",config=WG.app.config,regions=WG.handlers.keys(),rnom=rnom,form=form,clients=get_valid_clients())
