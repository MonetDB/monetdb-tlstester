MAPI TLS Tester Utility
=======================

Small utility to help test TLS support in MonetDB MAPI clients.

Configured with a base port, it opens up a number of sockets on other ports,
most of them TLS ports with various certificates. Clients can use this to check
that they are actually correctly validating the certificate host name etc.

If the TLS handshake succeeds, the server performs a simulated MAPI
handshake ending in the error message 
`Sorry, this is not a real MonetDB server`.


Certificates
------------

On each run, `tlstester.py` generates a number of secret keys and certificates:

<dl>

<dt>ca1.key and ca1.crt</dt>
<dd>Private key used for CA 1, with self-signed certificate.
</dd>
<dt>server1.key and server1.crt</dt>
<dd>Private key and certificate for server 1, signed by CA 1.
</dd>

<dt>server1x.crt</dt>
<dd>Expired certificate for server1.key.</dd>

<dt>ca2.key and ca2.crt</dt>
<dd>Private key used for CA 2, with self-signed certificate.
</dd>
<dt>server2.key and server2.crt</dt>
<dd>Private key and certificate for server 2, signed by CA 2.
</dd>

<dt>client2.key and client2.crt</dt>
<dd>Another private key and certificate signed by CA 2.</dd>

<dt>ca3.key and ca3.crt</dt>
<dd>Private key used for CA 3, with self-signed certificate.
</dd>
<dt>server3.key and server3.crt</dt>
<dd>Private key and certificate for server 3, signed by CA 3.
</dd>

</dl>


Ports
-----

Note: unless mentioned otherwise, all MAPI ports will refuse connection attempts
when TLS version less than 1.3 is used. TLS 1.2 just doesn't make sense for a
protocol introduced in 2023.

<dl>

<dt>base port</dt>
<dd>
   On the base port, <code>tlstest.py</code> runs a small http server (not https).
   On <code>/</code> it serves a text file with each line containing a
   <code>«port name»:«port number»</code> pair.
   It also serves all the above keys and certificates, as <code>/server1.crt</code>,
   etc. This includes the private keys.
</dd>

<dt>server1</dt>
<dd>TLS MAPI server signed by certificate server1.crt.</dd>

<dt>server2</dt>
<dd>TLS MAPI server signed by certificate server2.crt.</dd>

<dt>server3</dt>
<dd>TLS MAPI server signed by certificate server3.crt.</dd>

<dt>plain</dt>
<dd>Plain unencrypted MAPI connection.</dd>

<dt>expiredcert</dt>
<dd>A port using the expired certificate server1x.crt.</dd>

<dt>tls12</dt>
<dd>A port using server1.crt, but forced to TLS protocol version 1.2.</dd>

<dt>clientauth</dt>
<dd>
   A port using server1.crt, but requiring client certificates signed by CA 2.
   Currently the server verifies the certificate but not the hostname or any
   user id.
</dd>

</dl>


Suggested test cases
--------------------

The client must know the hostname and base port on which tlstester.py is
running. It can then retrieve the portmap to find the other ports. Before each
test the client should probably first make a raw TCP connection to the socket to
verify that it is reachable.

A succesful TLS connection is a connection where we can perform a MAPI dialogue
over the TLS connection. When using the built-in MAPI simulator, the MAPI
exchange will end in an error message but it is still a succes from the
perspective of the TLS connection. The succesful error can be recognized by the
distinctive phrase `Sorry, this is not a real MonetDB server`.

<dl>

<dt>connect_plain</dt>
<dd>
   Connect to port 'plain', without using TLS. Have a succesful MAPI exchange.
</dd>

<dt>connect_tls</dt>
<dd>
   Connect to port 'server1' over TLS, verifying the connection using ca1.crt.
   Have a succesful MAPI exchange.
</dd>

<dt>refuse_no_cert</dt>
<dd>
   Connect to port 'server1' over TLS, without passing a certificate.
   The connection should fail because ca1.crt is not in the system trust root store.
</dd>

<dt>refuse_wrong_cert</dt>
<dd>
   Connect to port 'server1' over TLS, verifying the connection using ca2.crt.
   The client should refuse to let the connection proceed.
</dd>

<dt>refuse_tlsv12</dt>
<dd>
   Connect to port 'tls12' over TLS, verifying the connection using ca1.crt.
   The client should refuse to let the connection proceed because it should
   require at least TLSv1.3.
</dd>

<dt>refuse_expired</dt>
<dd>
   Connect to port 'expiredcert' over TLS, verifying the connection using ca1.crt.
   The client should refuse to let the connection proceed.
</dd>

<dt>connect_client_auth</dt>
<dd>
   Connect to port 'clientauth' over TLS, verifying the connection using ca1.crt.
   Authenticate using server2.key and server2.crt.
   Have a succesful MAPI exchange.
</dd>

<dt>fail_plain_to_tls</dt>
<dd>
   Connect to port 'plain' over TLS. This should fail, not hang.
</dd>

<dt>fail_tls_to_plain</dt>
<dd>
   Make a plain MAPI connection to port 'server1'. This should fail.
</dd>

<dt>connect_trusted</dt>
<dd>
   Only when running in a throwaway environment such as a Docker container:
   Install ca3.crt in the system root certificate store. This is highly
   system-specific. Connect to port 'server3' over TLS without passing a
   certificate to check. The implementation should pick it up from the system
   store. Have a succesful MAPI exchange.
</dd>

</dl>

Docker image
------------

The script is also shipped as a Docker image, NAME.
This is convenient for tests running on GitHub Actions, because they can access
it as a service container.

The container can be configured using the following environment variables:

<dl>

<dt>TLSTEST_DOMAIN</dt>
<dd>Host name to sign the certificates for. Defaults to localhost.localdomain.</dd>

</dl>

Example:

```
docker run --rm -i -t -e TLSTEST_DOMAIN=localhost.localdomain -p 127.0.0.1:4300-4350:4300-4350 monetdb/tlstester:0.1
```


Integration with client libraries
---------------------------------

If the source code of the client library is on GitHub, configure the test to run
in a container, and run tlstester as a "service container". This will make it
accessible with a real hostname and because the tests themselves run in a
container they can install ca3.crt in the system root certificate store.

This is sufficient for pymonetdb and also for monetdb-java which is mirrored on
GitHub.

Libmapi/mclient/ODBC need to be tested through Mtest. We should probably
tlstester.py into the source tree and manually keep it synchronized with this
repository. This is not a huge problem because tlstester.py should rarely change.
The system certificate test cannot be run because Mtest is often run on systems
that are not ephemeral. As an alternative, we could run the MAPI simulator behind
a TLS proxy on a publically reachable host name, say mapitest.monetdb.org. The
Mtest could then first verify if that host resolves and is reachable and only
then try to make a TLS connection and have a MAPI exchange.

