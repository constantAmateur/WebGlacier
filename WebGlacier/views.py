from flask import redirect, url_for
from flask import render_template
from flask import request

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
  return render_template("vault.html",vault=vault,altvaults=altvaults)

@app.route("/glacier/settings/",methods=["GET","POST"])
def settings():
  if request.method == "POST":
    save_settings(request.form)
    app.config.from_pyfile("settings.cfg")
    app.config.from_envvar("GLACIER_CONFIG",silent=True)
    return redirect(url_for('settings'))
  rnom=get_set_region()
  return render_template("settings.html",config=app.config,regions=handlers.keys(),rnom=rnom)

def save_settings(d):
  #First get the file name of the current settings file
  nome=os.environ.get("GLACIER_CONFIG","settings.cfg")
  dat=open(nome,'r').read()
  #Save either the current setting, or the new one if validated
  #Debug?
  if 'debug' in d:
    tmp="True"
  else:
    tmp="False"
  dat=re.sub("(^|\n)DEBUG( |=).*","\\1DEBUG = "+tmp,dat)
  #APP_host
  if d['app_host']!='':
    tmp=d['app_host']
    dat=re.sub("(^|\n)APP_HOST( |=).*","\\1APP_HOST = '"+tmp+"'",dat)
  #Secret_key
  #if d['secret_key']!='':
  #  tmp=d['secret_key']
  #else:
  #  tmp=(app.config["SECRET_KEY"])
  #f.write("SECRET_KEY = '''")
  #f.write(tmp)
  #f.write("'''\n")
  #SQLALCHEMY_POOL_RECYCLE
  try:
    tmp=int(d['sqlalchemy_pool_recycle'])
    dat=re.sub("(^|\n)SQLALCHEMY_POOL_RECYCLE( |=).*","\\1SQLALCHEMY_POOL_RECYCLE = "+str(tmp),dat)
  except ValueError:
    pass
  #SQL_TYPE
  tmp=d['sql_type']
  tmp=tmp.lower()
  dat=re.sub("(^|\n)SQL_TYPE( |=).*","\\1SQL_TYPE = '"+str(tmp)+"'",dat)
  #SQL Username
  if d['sql_username']!='':
    tmp=d['sql_username']
    dat=re.sub("(^|\n)SQL_USERNAME( |=).*","\\1SQL_USERNAME = '"+str(tmp)+"'",dat)
  #SQL password
  if d['sql_password']!='':
    tmp=d['sql_password']
    dat=re.sub("(^|\n)SQL_PASSWORD( |=).*","\\1SQL_PASSWORD = '"+str(tmp)+"'",dat)
  #SQL hostname
  if d['sql_hostname']:
    tmp=d['sql_hostname']
    dat=re.sub("(^|\n)SQL_HOSTNAME( |=).*","\\1SQL_HOSTNAME = '"+str(tmp)+"'",dat)
  #SQL Db Name
  if d['sql_database_name']!='':
    tmp=d['sql_database_name']
    dat=re.sub("(^|\n)SQL_DATABASE_NAME( |=).*","\\1SQL_DATABASE_NAME = '"+str(tmp)+"'",dat)
  #Chunk size
  try:
    tmp=int(d['chunk_size'])
    dat=re.sub("(^|\n)CHUNK_SIZE( |=).*","\\1CHUNK_SIZE = "+str(tmp),dat)
  except ValueError:
    pass
  #Default region
  tmp=d['default_region']
  tmp=tmp.lower()
  dat=re.sub("(^|\n)DEFAULT_REGION( |=).*","\\1DEFAULT_REGION = '"+tmp+"'",dat)
  #AWS key
  if d['aws_access_key']!='':
    tmp=d['aws_access_key']
    dat=re.sub("(^|\n)AWS_ACCESS_KEY( |=).*","\\1AWS_ACCESS_KEY = '''"+str(tmp)+"'''",dat)
  #AWS secret key
  if d['aws_secret_access_key']!='':
    tmp=d['aws_secret_access_key']
    dat=re.sub("(^|\n)AWS_SECRET_ACCESS_KEY( |=).*","\\1AWS_SECRET_ACCESS_KEY = '''"+str(tmp)+"'''",dat)
  #cache
  if d['local_cache']!='':
    tmp=d['local_cache']
    dat=re.sub("(^|\n)LOCAL_CACHE( |=).*","\\1LOCAL_CACHE = '"+str(tmp)+"'",dat)
  #cache size
  try:
    tmp=int(d['local_cache_size'])
    dat=re.sub("(^|\n)LOCAL_CACHE_SIZE( |=).*","\\1LOCAL_CACHE_SIZE = "+str(tmp),dat)
  except ValueError:
    pass
  #cache file size
  try:
    tmp=int(d['local_cache_max_file_size'])
    dat=re.sub("(^|\n)LOCAL_CACHE_MAX_FILE_SIZE( |=).*","\\1LOCAL_CACHE_MAX_FILE_SIZE = "+str(tmp),dat)
  except ValueError:
    pass
  #Temp folder
  if d['temp_folder']!='':
    tmp=d['temp_folder']
    dat=re.sub("(^|\n)TEMP_FOLDER( |=).*","\\1TEMP_FOLDER = '"+str(tmp)+"'",dat)
  #Unknown filename
  if d['unknown_filename']!='':
    tmp=d['unknown_filename']
    dat=re.sub("(^|\n)UNKNOWN_FILENAME( |=).*","\\1UNKNOWN_FILENAME = '"+str(tmp)+"'",dat)
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
