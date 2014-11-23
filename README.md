# WebGlacier

[Amazon Glacier](http://aws.amazon.com/glacier/) is a low cost, long term backup service.  It's so low cost, that they don't bother providing any nice interface for uploading and downloading files, managing your backups, etc.  Instead you're pointed at a bunch of [very nerdy references](http://docs.aws.amazon.com/amazonglacier/latest/dev/amazon-glacier-api.html) and told to sort yourself out.

So where does that leave those that can't or don't want to code their own communication routines?  If you're planning to just use the one windows machine forever, there are some [acceptable looking clients with a gui](http://fastglacier.com/) around (disclaimer: I've never tried their software, but google seems to think it's relevant).

If you're a more nerdy type like me with your own web-server, perhaps you'd prefer to be able to manage your backups from any machine via a web interface.  I know I did, that's why I wrote WebGlacier.

The basic idea is that in order for Glacier to be a useful service, you need to keep a database where you keep track of the things you've uploaded, what those things are, how big they are, etc.  It makes sense to have that database stored somewhere that it can be accessed and modified from anywhere with minimal hassle and without having to worry about keeping multiple copies of your records of how uploaded what and when in sync.  

WebGlacier stores this database on your web server and provides a simple browser based interface for managing your Glacier backups from anywhere with an internet connection and a web browser.

Unfortunately, technical limitations mean that in order to upload a new archive or download one from Glacier, you need to also download and run a simple client on the machine doing the uploading/downloading.  But hopefully that's not too much hassle.

#Installation

## Server

Clone the git repository onto your web server in the usual way.  Install the application  by running 
````
python setup.py install 
````
I recommend you do this from a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

Edit `settings.cfg` to point to a valid SQL database (sqlite should be fine for most people).  While you're at it, specify the other configuration options.  As long as you have a valid database though, you can edit the settings file directly using the web interface (from /glacier/settings).

Run the application by typing `python runserver.py`.  The application should now be accessable at `localhost:5000/glacier` (or whatever you specified in settings.cfg).  If you point your web browser their, you should see a list of all your vaults (or none if you have none).

You can populate each of these vaults with your archives by clicking on the vault and then clicking the inventory job in the top right.  You'll have to wait for the job to finish, but once it's done your files should be added.

## Client

Setting up the client is dead simple.  Download `client.py` to a client machine, edit the first few lines to point it at a url where it can find the server and run it.  It should do the rest.

# Using WebGlacier

Should be pretty self-explanitory hopefully.  I'll write a better explanation if anyone but me starts using it.

# Planned features

At the moment I'd describe the web interface as "basic, but functional".  It could definitely be made a lot slicker and smoother with some basic javascript, so maybe I'll do that.

To upload something you have to give a file path.  It would be nice if you could use wild-cards and specify a bunch of files all at once.

While you can just use this on a local network, it's real utility is with it sitting on a web server, with password protection and SSL, accessable from anywhere.  It'd be good to have a daemon version of the app, or at least something that runs on start up and restarts when it crashes.  I guess I could show a simple nginx config too.

