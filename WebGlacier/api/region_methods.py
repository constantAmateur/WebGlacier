"""
File that contains all the non-visible routes
that are used for communicating with the app.

This file contains routines for doing region level
operations.
"""

#External dependency imports
from boto.glacier.exceptions import UnexpectedHTTPResponseError
import StringIO

#Flask imports
from flask import request, session, redirect, url_for, abort, send_file

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.models import Vault
from WebGlacier.lib.app import get_handler, validate_glacier,get_client_code
from WebGlacier.lib.glacier import process_vault

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/action/setregion",methods=["GET"])
def set_region():
  if 'region_select' in request.args and request.args['region_select'] in WG.handlers:
    try:
      #Check that the new region will actually work...
      validate_glacier(WG.app.config["AWS_ACCESS_KEY"],WG.app.config["AWS_SECRET_ACCESS_KEY"],request.args['region_select'])
      #Store it in the cookies
      session['region'] = request.args['region_select']
    except:
      print "Unable to switch to region %s"%request.args['region_select']
  return redirect(url_for('main'))

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/action/createvault",methods=["GET"])
def create_vault():
  if 'name' not in request.args:
    abort(401)
  hand = get_handler()
  try:
    hand.create_vault(request.args['name'])
    vault = process_vault(hand.describe_vault(request.args['name']))
  except UnexpectedHTTPResponseError as e:
    print "Failed to create vault.  Error message was %s"%e.message
  return redirect(url_for('main'))

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/action/deletevault",methods=["GET"])
def delete_vault():
  if 'name' not in request.args:
    abort(401)
  handler = get_handler()
  region=handler.region.name
  vault = Vault.query.filter_by(name=request.args['name'],region=region).first()
  if vault is None:
    #Trying to delete a non-existent vault...
    abort(401)
  if vault.lock:
    return "Vault is locked! No delete for you."
  if vault.archives.count()!=0:
    return "Cannot delete non-empty vault!"
  try:
    #First try deleting it from the amazon
    handler.delete_vault(vault.name)
  except UnexpectedHTTPResponseError as e:
    print "Failed to delete vault.  Error message was %s"%e.message
    abort(401)
  #If it was deleted, all jobs/archives must be ghosts...
  for job in vault.jobs:
    WG.db.session.delete(job)
  for archive in vault.archives:
    WG.db.session.delete(archive)
  #Delete the vault
  WG.db.session.delete(vault)
  WG.db.session.commit()
  return redirect(url_for('main'))

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/action/getvaults",methods=["GET"])
def get_vaults():
  """
  Queries the Amazon API and gets a list of all the jobs, which is used to
  populate and/or update the local database.
  """
  handler = get_handler()
  try:
    vaults=handler.list_vaults()
    for vault in vaults["VaultList"]:
      tmp=process_vault(vault)
  except UnexpectedHTTPResponseError as e:
    print "Failed processing/loading vaults.  Error was %s"%e.message
  return redirect(url_for("main"))


@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/action/getclient",methods=["GET"])
def get_client():
  """
  Not strictly a region method, more of a global method, but eh.
  Generates a custom client.py file with the appropriate server values set
  and sends it to requester.
  """
  strIO = StringIO.StringIO()
  strIO.write(str(get_client_code()))
  strIO.seek(0)
  return send_file(strIO,attachment_filename="WebGlacier_client.py",as_attachment=True)
