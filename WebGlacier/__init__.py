from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from boto import glacier

#We don't want the Flask call to create the static endpoint (we'll be making it ourselves in a minute), hence static_folder=None
app = Flask(__name__,static_folder=None)

#Configure the application
app.config.from_pyfile("../settings.cfg")
app.config.from_envvar("GLACIER_CONFIG",silent=True)
#Generate a secret key if one doesn't exist.
if 'SECRET_KEY' not in app.config:
  import os
  #Generate a secret key and save it to file
  with open(os.path.join(__path__[0],"../settings.cfg"),'a') as f:
    tmp=os.urandom(24)
    f.write('\n#Auto-generated secret key using os.urandom(24)\nSECRET_KEY = """'+tmp+'"""\n')
    app.config["SECRET_KEY"]=tmp
#Make a dictionary of queues of stuff that remotes need to do
queues = dict()
#Make a dictionary of clients
live_clients = dict()
#Global variable to hold the current client
app.config['current_client'] = None

#Make a new static endpoint so that the path gets set goodly
app.static_url_path = app.config.get("URL_PREFIX","")+'/static'
app.static_folder='static'
app.add_url_rule(app.static_url_path + '/<path:filename>',endpoint='static',view_func=app.send_static_file)

#Make the database handler
db = SQLAlchemy(app)
db.create_all()

#Make a dictionary to hold handlers for glacier
handlers = dict()
for region in glacier.regions():
  handlers[region.name] = None

#Has the current config been validated?
validated_glacier=False
validated_db=False

#Import views
import WebGlacier.views
import WebGlacier.api.region_methods
import WebGlacier.api.vault_methods
import WebGlacier.api.communication
