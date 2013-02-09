WebGlacier
==========

A basic web interface to manage your Amazon Glacier account.

It works in a very basic way at the moment, so use at your own risk.  Uses the boto libraries to do the communication with the Amazon web servers and stores all the information about archives you've submitted, vaults, etc. in an SQL database (I've tested it with MySQL and sqlite) so you don't spend your whole life polling Amazon's glacially slow (haha, I'm so not funny) inventory retrieval service.

The web server runs using flask (plus some plugins).  You can use this directly as the webserver, or plug it into uWSGI+nginx or whatever tickles your fancy.

INSTALLATION
============

Download the application and install with python setup.py install (I recommend you use a virtual-env for this).

Edit settings.cfg to point to a vaild SQL database.  You should also specify the other configuration options while you're at it.  As long as you have a valid database though, you can edit this directly from the web interface (from /glacier/settings).

Start the application with python runserver.py.  If you go to 127.0.0.1:5000/glacier (or whatever ip you set the app to broadcast on), you should see a list of all your vaults (or none if you have none).  

You can populate each of these vaults with your archives by clicking on the vault and then clicking the inventory job in the top right.  You'll have to wait for the job to finish, but once it's done your files should be added.

