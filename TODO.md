TO DO
=====

* [X] Create the script and its ArgumentParser.

* [X] Have the script generate the certificates.

* [X] Listen on the plain port run the MAPI simulator there

* [X] Have the script listen on the http port and serve the portmap.

* [ ] Have the script listen on server1, test with pymonetdb prototype

* [X] Same, with server2 and server3.

* [X] Implement port tls12

* [X] Implement port expiredcert

* [ ] Implement port goaway

* [ ] Remove https port from the documentation

* [ ] Remove ALPN from the documentation, cannot test it with Python ssl module

* [ ] Decide on SNI, with Panos

* [X] Implement port clientauth

* [ ] Create prototype docker image

* [ ] Implement GitHub Action in pymonetdb

* [ ] Implement system certificate test in pymonetdb

* [ ] Implement prototype integration of tlstester.py in Mtest

* [ ] Ask Panos to create tlstester container on Docker Hub, use it in pymonetdb

Maybe one day:

* Implement forwarding to a real MonetDB instance.

* Make the certificates live for 14 days. Once they're 7 days old, when a
  new connection comes in and the previous connection was more than 15 minutes
  ago, renew all certificates. This allows to leave tlstester running for long
  periods of time.