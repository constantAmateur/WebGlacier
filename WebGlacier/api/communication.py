"""
File that contains all the non-visible routes
that are used for communicating with the app.

This one contains routines that are used to communicate with
the remote client (not the web browser)
"""

#External dependency imports
import json
from datetime import datetime

#Flask imports
from flask import request, abort

#WebGlacier imports
import WebGlacier as WG
from WebGlacier.models import Vault, Archive
from WebGlacier.lib.misc import deunicode

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/command_queue",methods=['GET'])
def send_commands():
  """
  Main communication "socket" for client.  Informs the server
  that the client is alive and connected and the server returns
  any outstanding commands that are in the queue.
  """
  name = request.args.get('client_name','')
  qid = str(request.remote_addr) if name == '' else name+' ('+str(request.remote_addr) + ')'
  poll_freq = int(request.args.get('poll_freq',10))
  if WG.app.config.get("VERBOSE",False):
    print "Just checking in!  It's me "+qid
  #Register this client in the live_client list (or update it)
  #Format is [Last update, poll frequency, processing(bool)]
  WG.live_clients[qid]=[datetime.utcnow(),poll_freq,False]
  #Find the queue for the current machine, or return empty if nothing
  dat=WG.queues.get(qid,{})
  if dat:
    #The client is about to be busy, so update live_clients to reflect that
    WG.live_clients[qid][2]=True
  #Jsonify it and return it
  return json.dumps(dat), 200

@WG.app.route(WG.app.config.get("URL_PREFIX","")+"/command_returns",methods=['POST'])
def process_callbacks():
  """
  When the client has processed any commands in the queue, it will
  post any information needed by the server (such as the new archive id) 
  back at this url.
  Commands are then safely removed from the queue as they have been processed.
  """
  name = request.args.get('client_name','')
  qid = str(request.remote_addr) if name == '' else name+' ('+str(request.remote_addr) + ')'
  dat = deunicode(json.loads(request.get_data(as_text=True)))
  if WG.app.config.get("VERBOSE",False):
    print "Received return of %s"%str(dat)
  for k,val in dat.iteritems():
    #k is the hash, dat the data...
    #A completed download job
    if k[0]=='d':
      if WG.app.config.get("VERBOSE",False):
        print "Completed download job.  Returned:",val
      if qid not in WG.queues or k not in WG.queues[qid]:
        print "Download job not found in queue.  Strange..."
      else:
        _ = WG.queues[qid].pop(k)
    elif k[0]=='u':
      if WG.app.config.get("VERBOSE",False):
        print "Completed upload job.  Returned:",val
      if 'error' not in val:
        #Create a db object for it (provided it doesn't already exist)
        vault = Vault.query.filter_by(name=val['vault_name'],region=val['region_name']).first()
        if vault is None:
          print "Vault not found..."
          abort(401) 
        archive = Archive.query.filter_by(archive_id=val['archive_id']).first()
        if archive is not None:
          print "Archive already added.  We shouldn't be seeing this really..."
        else:
          archive = Archive(val['archive_id'],val['description'],vault,filename=val['file_name'],fullpath=val['true_path'],filesize=val['file_size'],md5sum=val['md5sum'])
          archive.insertion_date = datetime.fromtimestamp(int(val['insert_time']))
          WG.db.session.add(archive)
          WG.db.session.commit()
      if qid not in WG.queues or k not in WG.queues[qid]:
        print "Upload job not found in queue.  Strange..."
      else:
        _ = WG.queues[qid].pop(k)
  if WG.app.config.get("VERBOSE",False):
    print "After processing return, queue is %s"%str(WG.queues)
  return 'Processed'
