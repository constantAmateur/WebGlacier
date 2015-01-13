# WebGlacier

[Amazon Glacier](http://aws.amazon.com/glacier/) is a low cost, long term backup service.  It's so low cost, that they don't bother providing any nice interface for uploading and downloading files, managing your backups, etc.  Instead you're pointed at a bunch of [very nerdy references](http://docs.aws.amazon.com/amazonglacier/latest/dev/amazon-glacier-api.html) and told to sort yourself out.

So where does that leave those that can't or don't want to code their own communication routines?  If you're planning to just use the one windows machine forever, there are some [acceptable looking clients with a gui](http://fastglacier.com/) around (disclaimer: I've never tried their software, but google seems to think it's relevant).

If you're a more nerdy type like me with your own web-server, perhaps you'd prefer to be able to manage your backups from any machine via a web interface.  I know I did, that's why I wrote WebGlacier.

The basic idea is that in order for Glacier to be a useful service, you need to keep a database where you keep track of the things you've uploaded, what those things are, how big they are, etc.  It makes sense to have that database stored somewhere that it can be accessed and modified from anywhere with minimal hassle and without having to worry about keeping multiple copies of your records of how uploaded what and when in sync.  

WebGlacier stores this database on your web server and provides a simple browser based interface for managing your Glacier backups from anywhere with an internet connection and a web browser.

Unfortunately, because Amazon Glacier doesn't support <a href="https://en.wikipedia.org/wiki/Cross-origin_resource_sharing">CORS</a>, uploading or downloading a file requires running some code outside of the web-browser.

This is handled by either passing everything via the web server where you stick WebGlacier, which is a waste of bandwidth and disk space, or by requiring you to download a simple python client, which is annoying.

If you don't download the client, WebGlacier will default to passing everything via the web server.

#Installation

## Server

Clone the git repository onto your web server in the usual way.  Install the application  by running 
````
python setup.py install 
````
I recommend you do this from a [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/).

Copy `settings.cfg.template` to `settings.cfg` in the same directory and point it to a valid SQL database (sqlite should be fine for most people).  While you're at it, specify the other configuration options.  As long as you have a valid database though, you can edit the settings file directly using the web interface (from /glacier/settings).  

For Web Glacier to work, you need to specify your Amazon Glacier credentials, a valid database and the path of a directory that the user running Web Glacier can write to.

You can run the application directly by typing `python runserver.py`.  The application should be accessible at the location you specified (`localhost:5000` by default).  If you point your web browser there, you should see a list of all your vaults (or none if you have none).

You can populate each of these vaults with your archives by clicking on the vault and then clicking the inventory job in the top right.  You'll have to wait for the job to finish, but once it's done your files should be added.

### Deploying to a server

Is pretty straight forward.  Using nginx and uwsgi, you would do something like this:
Set nginx server block to:

````
  location = /webglacier { rewrite ^ /webglacier/; }
  location /webglacier {
    include uwsgi_params;
    uwsgi_pass unix:/location/of/uwsgi/socket/for/webglacier;
  }

````

This example illustrates how to deploy to a sub-directory of a webserver.  It should be obvious how to deploy to the root.  If you are deploying to a sub-directory, make sure you set `URL_PREFIX` in settings.cfg (e.g. `URL_PREFIX = "/webglacier"` for this example).

Finally, you can run WebGlacier by navigating to where you installed WebGlacier and running something like:

````
uwsgi --uid www-data --gid www-data --chroot /path/to/webglacier/ -s /location/for/webglacier/uwsgi/socket -w WebGlacier:app
````

For more information see the nginx/uwsgi documentation.

## Client

Setting up the client is dead simple.  Download `client.py` to a client machine, verify that the auto-set parameters are correct and start it.  It should do the rest.

# Using WebGlacier

Should be pretty self-explanatory hopefully.  I'll write a better explanation if anyone but me starts using it.

# Planned features

At the moment I'd describe the web interface as "basic, but functional".  It could definitely be made a lot slicker and smoother with some basic javascript, so maybe I'll do that.

To upload something you have to give a file path.  It would be nice if you could use wild-cards and specify a bunch of files all at once.


