from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy
from boto import glacier,connect_glacier
from boto.glacier.layer1 import Layer1

app = Flask(__name__)
#Configure the application
app.config.from_pyfile("settings.cfg")
app.config.from_envvar("GLACIER_CONFIG",silent=True)
if "SQLALCHEMY_DATABASE_URI" not in app.config:
  app.config['SQLALCHEMY_DATABASE_URI'] = app.config["SQL_TYPE"]+"://"+app.config["SQL_USERNAME"]+":"+app.config["SQL_PASSWORD"]+"@"+app.config["SQL_HOSTNAME"]+'/'+app.config["SQL_DATABASE_NAME"]
#Make a dictionary of handlers for the amazon servers
handlers = dict()
for region in glacier.regions():
  handlers[region.name]=[Layer1(aws_access_key_id = app.config["AWS_ACCESS_KEY"], aws_secret_access_key = app.config["AWS_SECRET_ACCESS_KEY"],region_name=region.name)]
  handlers[region.name].append(connect_glacier(aws_access_key_id = app.config["AWS_ACCESS_KEY"], aws_secret_access_key = app.config["AWS_SECRET_ACCESS_KEY"],region_name=region.name))

#Make the database handler
db = SQLAlchemy(app)

#Import views
import WebGlacier.views
import WebGlacier.cli_hooks
import WebGlacier.region_methods
import WebGlacier.vault_methods