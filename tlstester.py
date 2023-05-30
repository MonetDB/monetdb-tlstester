#!/usr/bin/env python3

from argparse import ArgumentParser
from datetime import datetime, timedelta
import logging
import os
import sys
from typing import Any, List, Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa

DESCRIPTION = "A utility to help test TLS MAPI client implementations."

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
    "--listen",
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
        return self._files[name]

    def all(self) -> dict[str, str]:
        return self._files.copy()

    def gen_keys(self):
        ca1 = self.gen_ca("ca1")
        self.gen_server("server1", ca1)
        self.gen_server("server1x", ca1, not_before=-15, not_after=-1)
        ca2 = self.gen_ca("ca2")
        self.gen_server("server2", ca2)
        self.gen_server("client2", ca2)
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

    def gen_server(self, name: str, ca_name: x509.Name, not_before=0, not_after=14):
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
        pem = b""
        while n:
            c = self._certs[n]
            pem += c.public_bytes(serialization.Encoding.PEM)
            n = self._parents.get(n)
        self.insert_file(f"{name}.crt", pem)

    def insert_file(self, name, content):
        assert name not in self._files
        self._files[name] = content


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


if __name__ == "__main__":
    args = argparser.parse_args()
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level)
    log.debug(args)
    sys.exit(main(args) or 0)
