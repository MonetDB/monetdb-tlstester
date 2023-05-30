TO DO
=====

* [X] Create the script and its ArgumentParser.

* [ ] Have the script generate the certificates.

* [ ] Listen on the plain port run the MAPI simulator there

* [ ] Have the script listen on the http port and serve the portmap.

* [ ] Have the script listen on server1, test with pymonetdb prototype

* [ ] Same, with server2 and server3.

* [ ] Implement port tls12

* [ ] Implement port expiredcert

* [ ] Implement port goaway

* [ ] Implement port https

* [ ] Implement port clientauth

* [ ] Implement GitHub Action in pymonetdb

* [ ] Implement system certificate test in pymonetdb

* [ ] Implement forwarding to a real MonetDB instance.

* [ ] Make the certificates live for 14 days. Once they're 7 days old, when a
  new connection comes in and the previous connection was more than 15 minutes
  ago, renew all certificates. This allows to leave tlstester running for long
  periods of time.