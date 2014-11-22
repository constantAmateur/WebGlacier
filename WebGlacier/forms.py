from flask.ext.wtf import Form
from wtforms import TextField, BooleanField, PasswordField,IntegerField,SelectField, ValidationError
from wtforms.validators import Required, Optional, IPAddress

from WebGlacier import app,handlers
from boto.glacier.layer1 import Layer1
import os,sqlalchemy

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
  config=app.config
  #SQL settings
  SQL_DIALECT = TextField(validators=[Required()])
  SQL_DATABASE_NAME = TextField(validators=[Required()])
  SQL_HOSTNAME = TextField()
  SQL_USERNAME = TextField()
  SQL_PASSWORD = PasswordField()
  SQL_PORT = IntegerField(validators=[Optional()])
  #Amazon settings
  DEFAULT_REGION = SelectField(choices=[(x,x) for x in handlers.keys()])
  AWS_ACCESS_KEY = TextField(validators=[Required()])
  AWS_SECRET_ACCESS_KEY = TextField(validators=[Required()])
  #Web glacier settings
  UCHUNK = IntegerField(validators=[Optional()])
  DCHUNK = IntegerField(validators=[Optional()])
  UNKNOWN_FILENAME = TextField()
  #Nerd SETTINGS
  DEBUG = BooleanField()
  APP_HOST = TextField(validators=[Required(),IPAddress()])
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

    #Try and connect using the given 
    try:
      key = self.SQL_DIALECT.data
      #Fall back on existing value on empty password field
      if self.SQL_PASSWORD.data=='' and app.config["SQL_PASSWORD"]!='':
        pwd=app.config["SQL_PASSWORD"]
      else:
        pwd=self.SQL_PASSWORD.data
      if self.SQL_DRIVER.data!="":
        key = key+"+"+self.SQL_DRIVER.data
      if self.SQL_DIALECT.data == "sqlite":
        tmp=":////"
      else:
        tmp="://"
      key = key+tmp
      extra_slash=False
      if self.SQL_USERNAME.data!='' and pwd!='':
        extra_slash=True
        key = key+self.SQL_USERNAME.data+":"+pwd+"@"
      if self.SQL_HOSTNAME.data!='':
        extra_slash=True
        key = key+self.SQL_HOSTNAME.data
        if self.SQL_PORT.data is not None:
          key = key+":"+self.SQL_PORT.data
      if extra_slash:
        key = key+'/'
      key = key+self.SQL_DATABASE_NAME.data
      a=sqlalchemy.engine.create_engine(key)
      b=a.connect()
      b.close()
    except:
      self.errors['meta_sql'].append("Can't connect to SQL database")
      return False
    #Amazon connection
    try:
      tst=Layer1(aws_access_key_id = self.AWS_ACCESS_KEY.data, aws_secret_access_key = self.AWS_SECRET_ACCESS_KEY.data,region_name=self.DEFAULT_REGION.data)
      a=tst.list_vaults()
      tst.close()
    except:
      self.errors['meta_amazon'].append("Can't connect to Amazon")
      return False
    return True
