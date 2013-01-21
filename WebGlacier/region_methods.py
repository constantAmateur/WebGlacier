from flask import request, session
from flask import abort, redirect, url_for

from WebGlacier import app, handlers, db
from WebGlacier.utils import get_handler,process_vault
from models import Vault

@app.route("/glacier/action/setregion",methods=["GET"])
def set_region():
  if 'region_select' in request.args and request.args['region_select'] in handlers:
    session['region'] = request.args['region_select']
  return redirect(url_for('main'))

@app.route("/glacier/action/createvault",methods=["GET"])
def create_vault():
  if 'name' not in request.args:
    abort(401)
  hand = get_handler()
  hand.create_vault(request.args['name'])
  vault = process_vault(hand.describe_vault(request.args['name']))
  return redirect(url_for('main'))

@app.route("/glacier/action/deletevault",methods=["GET"])
def delete_vault():
  if 'name' not in request.args:
    abort(401)
  handler = get_handler()
  region=handler.region.name
  vault = Vault.query.filter_by(name=request.args['name'],region=region).first()
  if vault is None:
    abort(401)
  if vault.lock:
    return "Vault is locked! No delete for you."
  if vault.archives.count()!=0:
    return "Cannot delete non-empty vault!"
  #First try deleting it from the amazon
  handler.delete_vault(vault.name)
  #If it was deleted, all jobs/archives must be ghosts...
  for job in vault.jobs:
    db.session.delete(job)
  for archive in vault.archives:
    db.session.delete(archive)
  #Delete the vault
  db.session.delete(vault)
  db.session.commit()
  return redirect(url_for('main'))

@app.route("/glacier/action/getvaults",methods=["GET"])
def get_vaults():
  """
  Queries the Amazon API and gets a list of all the jobs, which is used to
  populate and/or update the local database.
  """
  handler = get_handler()
  vaults=handler.list_vaults()
  for vault in vaults["VaultList"]:
    tmp=process_vault(vault)
  return redirect(url_for("main"))


