WebGlacier
==========

A basic web interface to manage your Amazon Glacier account.

It works in a very basic way at the moment, so use at your own risk.  Uses the boto libraries to do the communication with the Amazon web servers and stores all the information about archives you've submitted, vaults, etc. in an SQL database (I've tested it with MySQL) so you don't spend your whole life polling Amazon's glacially slow (haha, I'm so not funny) inventory retrieval service.

The web server runs using flask (plus some plugins).  You can use this directly as the webserver, or plug it into uWSGI+nginx or whatever tickles your fancy.

The biggest flaw so far (other than the but ugly interface) is that you double your bandwidth as any client using the webinterface must upload/download archives to/from the webserver, which then shuttles the data to/from Amazon.  If some clever person wants to tell me how to not do this, that would be super...  This has been made less of an issue somewhat by implementing a download time cache on the server.  There's no way around the extra upload bandwidth, because the entire thing has to be stored somewhere where it can calculate hashes of stuff.  Unless I can find some clever way to instruct the client on how to hash a file and then construct the headers for a POST request to a remote server, I don't think there's any alternative.  Javascript is the obvious way to try and do this, but it seems like this isn't allowed in general for security reasons.
