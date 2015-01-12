###################
# User parameters #
###################

##########################
# You **MUST** set these #
##########################
#Directory where files are downloaded to.  Must exist.
ddir = '/home/myoung/Downloads/'
#Nickname of this computer.  Used to help identify which machine should download
client_name = 'pikachoo'
#########################################################################################
# These must be accurate, but should be set automatically if downloaded from the server #
#########################################################################################
#Root of server.  Must include any prefix that we require...
server_address = ''
#Server username/password
username = ''
password = ''
#####################################################
# Default here should be fine, change if you'd like #
#####################################################
#Polling frequency.  That is, wait time between checking the queue
#Time to wait between checks of the queue
check_wait = 10
#Chunk size for downloading
dchunk = 1048576
#Chunk size for uploading
uchunk = 4194304

###########################################
# **DO NOT ALTER ANYTHING BELOW HERE!!!** #
###########################################


###############
# Client code #
###############


from boto.glacier.layer1 import Layer1
from boto.glacier.concurrent import ConcurrentUploader
import urllib3
import time
import json
import os
import math
import hashlib
import collections

#Initialise some stuff
pool = urllib3.PoolManager()
server_address = server_address.strip('/')
#Make the authentication headers
auth_head = urllib3.util.make_headers(basic_auth=username+":"+password)
#Chunks must be powers of 2 times megabytes
dchunk = 1048576*2**int(math.floor(math.log(dchunk/1048576.,2)))
uchunk = 1048576*2**int(math.floor(math.log(uchunk/1048576.,2)))

def chunkedmd5(filename,csize=8192):
  """
  Calculate the md5sum of a file without loading any more than csize bytes into
  memory at a time
  """
  md5=hashlib.md5()
  with open(filename,'rb') as f:
    for chunk in iter(lambda: f.read(csize), b''):
      md5.update(chunk)
  return md5.digest().encode('hex')

def deunicode(data):
  """
  Gets rid of unicode strings introduced by decoding that mess some things up.
  """
  if isinstance(data, basestring):
    return str(data)
  elif isinstance(data, collections.Mapping):
    return dict(map(deunicode, data.iteritems()))
  elif isinstance(data, collections.Iterable):
    return type(data)(map(deunicode, data))
  else:
    return data

def download_file(command):
  """
  Takes a command and uses it to download the file.
  """
  if 'action' not in command or command['action']!='DOWNLOAD':
    raise ValueError("Command not of type DOWNLOAD")
  ret={}
  handler = Layer1(aws_access_key_id = command['access_key'],aws_secret_access_key = command['secret_access_key'],region_name=command['region_name'])
  f=open(os.path.join(ddir,command['file_name']),'wb')
  num_chunks = int(math.ceil(command['file_size'] / float(dchunk)))
  print "Downloading file %s"%command['file_name']
  for i in xrange(num_chunks):
    byte_range = ((i * dchunk), ((i + 1) * dchunk) - 1)
    dload = handler.get_job_output(command['vault_name'],command['job_id'],byte_range)
    f.write(dload.read())
    print "%g %%"%(100*float(i)/float(num_chunks))
  f.close()
  print "100 %"
  print "Completed."
  return {}
  
def upload_file(command):
  """
  Uploads a file from the local machine that is specified in the given command.
  """
  if 'action' not in command or command['action']!="UPLOAD":
    raise ValueError("Command not of type UPLOAD")
  if 'file_pattern' not in command: 
    raise ValueError("Missing file pattern")
  path = command['file_pattern'] 
  if not os.path.exists(path):
    raise ValueError("No valid file for upload found")
  returner={}
  handler = Layer1(aws_access_key_id = command['access_key'],aws_secret_access_key = command['secret_access_key'],region_name=command['region_name'])
  uploader = ConcurrentUploader(handler,command['vault_name'],part_size=uchunk)
  file_size = os.path.getsize(path)
  csum = chunkedmd5(path)
  itime=time.time()
  file_name = os.path.basename(path)
  machine_id = str(command['target']) if client_name == '' else client_name+' ('+str(command['target']) + ')'
  #Construct a meaningful description object for the file
  #The limits are that the description can be no more than 1024 characters in length and must use only ascii characters between 32 and 126 (i.e., 32<=ord(char)<=126)
  dscrip = command['description']+'\\n'
  dscrip = dscrip + "Uploaded at "+str(itime)+'\\n'+ "Full path "+str(path)+'\\n'+ "File size "+str(file_size)+'\\n' + "MD5 "+str(csum)+'\\n' + "Source machine id "+str(command['target'])+'\\n'
  print "Uploading file %s"%file_name
  #Put some validation stuff here...
  #Do the upload
  archive_id = uploader.upload(path,dscrip)
  print "Completed successfully.  Archive ID: %s"%archive_id
  #Done the upload, send the bastard back
  returner['archive_id'] = archive_id
  returner['description'] = dscrip
  returner['file_name'] = file_name
  returner['true_path'] = path
  returner['file_size'] = file_size
  returner['md5sum'] = csum
  returner['insert_time']=int(itime)
  returner['region_name']=command['region_name']
  returner['vault_name'] = command['vault_name']
  return returner
 
def send_returns(returns):
  """
  Having completed everything, send them back for them to be initiated into the archive.
  """
  #Build the header
  head = {'Content-Type':'application/json'}
  head.update(auth_head)
  r = pool.urlopen('POST',server_address+'/command_returns?client_name='+client_name,headers=head,body=json.dumps(returns))
  if r.data!="Processed":
    print "Something went horribly wrong on the other end.  Here are the bits of information to retry later with..."
    print json.dumps(returns)

#Main loop
while True:
  print "Attempting to poll server for new commands."
  try:
    r = pool.request('GET',server_address+'/command_queue?client_name='+client_name+"&poll_freq="+str(check_wait),headers=auth_head)
    dat = deunicode(json.loads(r.data))
    r.close()
    returns={}
    for k,command in dat.iteritems():
      if k[0]=='d':
        try:
          returns[k]=download_file(command)
        except ValueError as e:
          print "Download failed with error "+str(e)
          returns[k]={'error':e.message}
      elif k[0]=='u':
        try:
          returns[k]=upload_file(command)
        except ValueError as e:
          print "Upload failed with error "+str(e)
          returns[k]={'error':e.message}
      else:
        print "Received command with invalid action.  Ignoring.  Key and Command were:",k,command
    if returns:
      send_returns(returns)
  except (urllib3.exceptions.MaxRetryError,ValueError):
    print "Server did not respond, waiting and then trying again..."
  time.sleep(check_wait)
