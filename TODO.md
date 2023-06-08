TO DO
=====

* [X] Create the script and its ArgumentParser.

* [X] Have the script generate the certificates.

* [X] Listen on the plain port run the MAPI simulator there

* [X] Have the script listen on the http port and serve the portmap.

* [X] Have the script listen on server1, test with pymonetdb prototype

* [X] Same, with server2 and server3.

* [X] Implement port tls12

* [X] Implement port expiredcert

* [X] Remove ports https and goaway from the documentation

* [X] Remove and SNI, ALPN from the documentation, cannot test it with Python ssl module

* [X] Implement port clientauth

* [X] Create prototype docker image

* [X] Implement GitHub Action in pymonetdb

* [X] Implement system certificate test in pymonetdb

* [X] Ask Panos to create tlstester container on Docker Hub, use it in pymonetdb

* [X] Allow to sign for multiple domains

* [X] Implement forwarding so simple tests don't need stunnel

* [X] Allow to use as a library, useful for Mtest

* [ ] Implement prototype integration of tlstester.py in Mtest

Maybe one day:

* For long running instances, renew certificates after a while
