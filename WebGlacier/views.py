from flask import redirect, url_for
from flask import render_template

from WebGlacier import app, handlers, db
from WebGlacier.utils import get_set_region
from WebGlacier.vault_methods import check_job_status
from models import Vault

@app.route("/glacier/<vault_name>/")
def vault_view(vault_name):
  vault = Vault.query.filter_by(name=vault_name).first()
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
  return render_template("vault.html",vault=vault)

@app.route("/glacier/",methods=["GET"])
def main():
  """The main interface for the glacier database."""
  region = get_set_region()
  #Get all the vaults
  vaults = Vault.query.filter_by(region=region)
  #Render them all nicely
  return render_template("main.html",vaults=vaults,rnom=region,regions=handlers.keys())
