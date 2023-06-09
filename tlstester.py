#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime, timedelta
import http.server
import io
import logging
import os
import socketserver
import ssl
from ssl import SSLContext, SSLError, TLSVersion
import struct
import sys
import tempfile
from threading import Thread
from typing import Any, Callable, List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa

VERSION = "0.2.0"

DESCRIPTION = f"tlstester.py version {VERSION}: a utility to help test TLS MAPI client implementations."

log = logging.getLogger("tlstester")

argparser = ArgumentParser("tlstester", description=DESCRIPTION)
argparser.add_argument(
    "-p",
    "--base-port",
    type=int,
    required=True,
    help="base port on which utility is reachable",
)
argparser.add_argument(
    "-w",
    "--write",
    type=str,
    metavar="DIR",
    help="Write generated keys and certs to this directory",
)
argparser.add_argument(
    "-l",
    "--listen-addr",
    type=str,
    default="localhost",
    help="interface to listen on, default=localhost",
)
argparser.add_argument(
    "-n",
    "--hostname",
    type=str,
    default="localhost.localdomain",
    help="server name to sign certificates for, default=localhost.localdomain",
)
argparser.add_argument(
    "--sequential",
    action="store_true",
    help="allocate ports sequentially after BASE_PORT, instead of whatever the OS decides",
)
argparser.add_argument(
    "-v", "--verbose", action="store_true", help="Log more information"
)


class Certs:
    hostname: str
    _files: dict[str, str]
    _keys: dict[x509.Name, rsa.RSAPrivateKey]
    _certs: dict[x509.Name, x509.Certificate]
    _parents: dict[x509.Name, x509.Name]

    def __init__(self, hostname):
        self.hostname = hostname
        self._files = {}
        self._keys = {}
        self._certs = {}
        self._parents = {}
        self.gen_keys()

    def get_file(self, name):
        return self._files.get(name)

    def all(self) -> dict[str, str]:
        return self._files.copy()

    def gen_keys(self):
        ca1 = self.gen_ca("ca1")
        self.gen_server("server1", ca1)
        self.gen_server("server1x", ca1, not_before=-15, not_after=-1)
        ca2 = self.gen_ca("ca2")
        self.gen_server("server2", ca2)
        self.gen_server("client2", ca2, keycrt=True)
        ca3 = self.gen_ca("ca3")
        self.gen_server("server3", ca3)

    def gen_ca(self, name: str):
        ca_name = x509.Name(
            [
                x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, f"Org {name}"),
                x509.NameAttribute(
                    x509.NameOID.COMMON_NAME, f"The Certificate Authority"
                ),
            ]
        )
        critical_ca_extensions = [x509.BasicConstraints(ca=True, path_length=1)]
        self.gen_key(name, ca_name, critical_extensions=critical_ca_extensions)

        return ca_name

    def gen_server(self, name: str, ca_name: x509.Name, not_before=0, not_after=14, keycrt=False):
        server_name = x509.Name(
            [
                x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, f"Org {name}"),
                x509.NameAttribute(x509.NameOID.COMMON_NAME, self.hostname),
            ]
        )
        noncritical_server_extensions = [
            x509.SubjectAlternativeName([x509.DNSName(self.hostname)])
        ]
        self.gen_key(
            name=name,
            subject_name=server_name,
            parent_name=ca_name,
            not_before=not_before,
            not_after=not_after,
            noncritical_extensions=noncritical_server_extensions,
            keycrt=keycrt,
        )

    def gen_key(
        self,
        name: str,
        subject_name: x509.Name,
        parent_name: Optional[x509.Name] = None,
        not_before=0,
        not_after=14,
        critical_extensions: List[x509.ExtensionType] = [],
        noncritical_extensions: List[x509.ExtensionType] = [],
        keycrt=False,
    ):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        if parent_name:
            issuer_name = parent_name
            issuer_key = self._keys[parent_name]
        else:
            issuer_name = subject_name
            issuer_key = key

        now = datetime.utcnow()
        builder = (
            x509.CertificateBuilder()
            .issuer_name(issuer_name)
            .subject_name(subject_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now + timedelta(not_before))
            .not_valid_after(now + timedelta(not_after))
        )
        for ext in critical_extensions:
            builder = builder.add_extension(ext, critical=True)
        for ext in noncritical_extensions:
            builder = builder.add_extension(ext, critical=False)
        cert = builder.sign(issuer_key, hashes.SHA256())

        self._keys[subject_name] = key
        self._certs[subject_name] = cert
        self._parents[subject_name] = parent_name

        pem_key = key.private_bytes(
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encoding=serialization.Encoding.PEM,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.insert_file(f"{name}.key", pem_key)

        n = subject_name
        pem_crt = b""
        while n:
            c = self._certs[n]
            pem_crt += c.public_bytes(serialization.Encoding.PEM)
            n = self._parents.get(n)
        self.insert_file(f"{name}.crt", pem_crt)

        if keycrt:
            pem_keycrt = pem_key + pem_crt
            self.insert_file(f"{name}.keycrt", pem_keycrt)

    def insert_file(self, name, content):
        assert isinstance(content, bytes)
        assert name not in self._files
        self._files[name] = content


class Server:
    certs: Certs
    portmap: dict[str, int]
    next_port: int
    workers: List[Callable[[], None]]

    def __init__(self, certs: Certs, listen_addr: str, base_port: int, sequential):
        self.certs = certs
        self.portmap = dict()
        self.next_port = base_port + 1 if sequential else 0
        self.workers = []

        self.spawn_http(listen_addr, base_port)

        self.spawn_mapi("plain", listen_addr, None)
        self.spawn_mapi("server1", listen_addr, self.ssl_context("server1"))
        self.spawn_mapi("server2", listen_addr, self.ssl_context("server2"))
        self.spawn_mapi("server3", listen_addr, self.ssl_context("server3"))

        self.spawn_mapi("expiredcert", listen_addr, self.ssl_context("server1x"))
        self.spawn_mapi(
            "tls12",
            listen_addr,
            self.ssl_context("server1", tls_version=TLSVersion.TLSv1_2),
        )
        self.spawn_mapi(
            "clientauth",
            listen_addr,
            self.ssl_context("server1", client_cert="ca2"),
        )

    def ssl_context(
        self, cert_name: str, tls_version=TLSVersion.TLSv1_3, client_cert=None
    ):
        context = SSLContext(ssl.PROTOCOL_TLS_SERVER)

        context.minimum_version = tls_version or TLSVersion.TLSv1_3
        if tls_version:
            context.maximum_version = tls_version

        # Turns out the ssl API forces us to write the certs to file. Yuk!
        with tempfile.NamedTemporaryFile(mode="wb") as f:
            f.write(self.certs.get_file(cert_name + ".key"))
            f.write(self.certs.get_file(cert_name + ".crt"))
            f.flush()
            context.load_cert_chain(f.name)

        if client_cert:
            context.verify_mode = ssl.CERT_REQUIRED
            cert_bytes = self.certs.get_file(client_cert + ".crt")
            cert_str = str(cert_bytes, "utf-8")
            context.load_verify_locations(cadata=cert_str)

        return context

    def serve_forever(self):
        threads = []
        for worker in self.workers:
            t = Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()

    def spawn_http(self, listen_addr: str, port: int):
        handler = lambda req, addr, server: WebHandler(
            req, addr, server, self.certs, self.portmap
        )
        server = http.server.HTTPServer((listen_addr, port), handler)
        log.debug(f"Bound base port {args.base_port}")
        self.workers.append(server.serve_forever)

    def spawn_mapi(self, name: str, listen_addr: str, ctx: SSLContext):
        port = self.next_port
        if self.next_port > 0:
            self.next_port += 1
        handler = lambda req, addr, server: MapiHandler(req, addr, server, name, ctx)
        server = MyTCPServer((listen_addr, port), handler)
        port = server.server_address[1]
        log.debug(f"Bound port {name} to {port}")
        self.portmap[name] = port
        self.workers.append(server.serve_forever)


class WebHandler(http.server.BaseHTTPRequestHandler):
    certs: Certs
    portmap: dict[str, int]

    def __init__(self, req, addr, server, certs: Certs, portmap: dict[str, int]):
        self.certs = certs
        self.portmap = portmap
        super().__init__(req, addr, server)

    def do_GET(self):
        idx = self.path.find("?")
        path = self.path[:idx] if idx > 0 else self.path
        if path == "/":
            return self.do_root()
        content = self.certs.get_file(path[1:])
        if content:
            return self.do_content(content)
        self.send_error(http.HTTPStatus.NOT_FOUND)

    def do_root(self):
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        w = io.TextIOWrapper(
            self.wfile,
            encoding="ascii",
        )
        for name, port in self.portmap.items():
            print(f"{name}:{port}", file=w)
        w.flush()
        w.detach()

    def do_content(self, content: bytes):
        try:
            str(content, encoding="ascii")
            content_type = "text/plain; charset=utf-8"
        except UnicodeDecodeError:
            content_type = "application/binary"

        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(content)


class MyTCPServer(socketserver.ForkingTCPServer):
    allow_reuse_address = True
    pass


class MapiHandler(socketserver.BaseRequestHandler):
    name: str
    context: SSLContext
    conn: ssl.SSLSocket

    CHALLENGE = b"s7NzFDHo0UdlE:merovingian:9:RIPEMD160,SHA512,SHA384,SHA256,SHA224,SHA1:LIT:SHA512:"
    ERRORMESSAGE = b"!Sorry, this is not a real MonetDB instance"

    def __init__(self, req, addr, server, name, context):
        self.name = name
        self.context = context
        super().__init__(req, addr, server)

    def handle(self):
        log.debug(f"port '{self.name}': new connection")
        if self.context:
            log.debug(f"port '{self.name}': trying to set up TLS")
            try:
                self.conn = self.context.wrap_socket(self.request, server_side=True)
                log.info(f"port '{self.name}': TLS handshake succeeded")
            except SSLError as e:
                log.info(f"port '{self.name}': TLS handshake failed: {e}")
                return
        else:
            self.conn = self.request
            log.info(f"port '{self.name}' no TLS handshake necessary")

        try:
            self.send_message(self.CHALLENGE)
            log.debug(f"port '{self.name}': sent challenge, awaiting response")
            if self.recv_message():
                self.send_message(self.ERRORMESSAGE)
                log.debug(
                    f"port '{self.name}': received response, sent closing message"
                )

        except OSError as e:
            log.info(f"port '{self.name}': error {e}")

    def send_message(self, msg: bytes):
        n = len(msg)
        head = struct.pack("<h", 2 * n + 1)
        self.conn.sendall(head + msg)

    def recv_message(self):
        nread = 0
        while True:
            head = self.recv_bytes(2)
            nread += len(head)
            if len(head) < 2:
                break
            n = struct.unpack("<h", head)[0]
            size = n // 2
            last = (n & 1) > 0
            if size > 0:
                body = self.recv_bytes(size)
                nread += len(body)
                if len(body) < size:
                    break
            if last:
                return True

        log.info("port '{self.name}': incomplete message, EOF after {nread} bytes")
        return False

    def recv_bytes(self, size):
        """Read 'size' bytes. Only return fewer if EOF"""
        buf = b""
        while len(buf) < size:
            remaining = size - len(buf)
            more = self.conn.recv(remaining)
            if more == b"":
                return buf
            else:
                buf += more
        return buf


def main(args):
    log.debug("Creating certs")
    certs = Certs(args.hostname)
    if args.write:
        dir = args.write
        try:
            os.mkdir(dir)
        except FileExistsError:
            pass
        count = 0
        for name, content in certs.all().items():
            with open(os.path.join(dir, name), "wb") as f:
                f.write(content)
                count += 1
        log.info(f"Wrote {count} files to {dir!r}")

    server = Server(
        certs=certs,
        base_port=args.base_port,
        listen_addr=args.listen_addr,
        sequential=args.sequential,
    )

    log.info("Serving requests")
    server.serve_forever()


if __name__ == "__main__":
    args = argparser.parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level)
    log.debug(args)
    sys.exit(main(args) or 0)
