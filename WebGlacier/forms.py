"""
Models to create and validate complex forms used in the application.
"""

#External dependency imports
import os, sqlalchemy

#Flask imports
from flask import redirect, render_template
from flask.ext.wtf import Form
from wtforms import TextField, BooleanField, PasswordField,IntegerField,SelectField, ValidationError
from wtforms.validators import Required, Optional, IPAddress

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.lib.app import build_db_key, validate_db, validate_glacier, init_handlers_from_config

class Folder(object):
  """
  A validator which ensures that the content given is a folder
  on the server and that it is readable and writeable.
  """

  def __init__(self, writeable=True,readable=True,message=None):
    self.readable=readable
    self.writeable = writeable
    if not message:
      message= u'Field must be a valid folder on the server'
      if self.readable:
        message=message+u" and readable"
      if self.writeable:
        message=message+u" and writeable"
    self.message=message

  def __call__(self,form,field):
    if field.data and os.path.isdir(field.data):
      if self.readable and not os.access(field.data, os.R_OK):
        raise ValidationError(self.message)
      if self.writeable and not os.access(field.data, os.W_OK | os.X_OK):
        raise ValidationError(self.message)
    else:
      raise ValidationError(self.message)


class SettingsForm(Form):
  config=WG.app.config
  #SQL settings
  SQL_DIALECT = TextField(validators=[Required()])
  SQL_DATABASE_NAME = TextField(validators=[Required()])
  SQL_HOSTNAME = TextField()
  SQL_USERNAME = TextField()
  SQL_PASSWORD = PasswordField()
  SQL_PORT = IntegerField(validators=[Optional()])
  #Amazon settings
  DEFAULT_REGION = SelectField(choices=[(x,x) for x in WG.handlers.keys()])
  AWS_ACCESS_KEY = TextField(validators=[Required()])
  AWS_SECRET_ACCESS_KEY = TextField(validators=[Required()])
  #Web glacier settings
  CHUNK = IntegerField(validators=[Optional()])
  UNKNOWN_FILENAME = TextField()
  TEMP_FOLDER = TextField(validators=[Required(),Folder()])
  #Nerd SETTINGS
  DEBUG = BooleanField()
  APP_HOST = TextField(validators=[Required(),IPAddress()])
  URL_PREFIX = TextField()
  #SECRET_KEY = TextField()
  SQLALCHEMY_POOL_RECYCLE = IntegerField()
  SQL_DRIVER = TextField()
  #Security settings
  DISABLE_HTTPS = BooleanField()
  DISABLE_AUTH = BooleanField()

  def validate(self):
    rv = Form.validate(self)
    if not rv:
      return False
    self.errors['meta_sql']=[]
    self.errors['meta_amazon']=[]

    #Try and connect to the database using the given parameters
    try:
      #Fall back on existing value on empty password field
      password = None if self.SQL_PASSWORD.data=='' else self.SQL_PASSWORD.data
      if password is None and WG.app.config["SQL_PASSWORD"]!='':
        password=WG.app.config["SQL_PASSWORD"]
      key=build_db_key(self.SQL_DIALECT.data,self.SQL_DATABASE_NAME.data,self.SQL_HOSTNAME.data,self.SQL_USERNAME.data,password,self.SQL_DRIVER.data,self.SQL_PORT.data)
      validate_db(key)
      WG.app.config["SQLALCHEMY_DATABASE_URI"]=key
      WG.db.create_all()
      WG.validated_db=True
    except:
      WG.validated_db=False
      self.errors['meta_sql'].append("Can't connect to SQL database")
      return False
    #Amazon connection
    try:
      validate_glacier(self.AWS_ACCESS_KEY.data,self.AWS_SECRET_ACCESS_KEY.data,self.DEFAULT_REGION.data)
      WG.app.config['AWS_ACCESS_KEY']=self.AWS_ACCESS_KEY.data
      WG.app.config['AWS_SECRET_ACCESS_KEY']=self.AWS_SECRET_ACCESS_KEY.data
      init_handlers_from_config()
      WG.validated_glacier=True
    except:
      self.errors['meta_amazon'].append("Can't connect to Amazon")
      WG.validated_glacier=False
      return False
    try:
      #Check directory is writeable
      tmp=tempfile.NamedTemporaryFile(dir=self.TEMP_FOLDER,delete=False)
      tmp.write("Hello world")
      tmp.close()
    except:
      self.errors['meta_glacier'].append("Directory is not writeable.")
      return False
    return True


