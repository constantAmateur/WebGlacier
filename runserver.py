from WebGlacier import app
from OpenSSL import SSL
from flask.ext.basicauth import BasicAuth

#Create an SSL context for http goodness
try:
  context = SSL.Context(SSL.SSLv23_METHOD)
  context.use_privatekey_file('/etc/ssl/private/ssl-cert-snakeoil.key')
  context.use_certificate_file('/etc/ssl/certs/ssl-cert-snakeoil.pem')
except SSL.Error:
  context = 'adhoc'
#Disable https if we're foolish enough to request that
if app.config.get('DISABLE_HTTPS',False):
  context = None
#Disable authentication.  Don't do this unless you've replaced it...
#if not app.config.get("DISABLE_AUTH",False):
#  #Apply basic auth on entire site
#  app.config['BASIC_AUTH_FORCE'] = True
#  basic_auth = BasicAuth(app)

app.run(app.config.get('APP_HOST'),debug=app.config.get('DEBUG',True),use_reloader=app.config.get('USE_RELOADER',True),ssl_context=context)
