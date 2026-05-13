#!/usr/bin/env python3
"""Generate a self-signed TLS cert + key.

Idempotent: if both files already exist, do nothing. Otherwise create a
2048-bit RSA key and a cert valid for ~2 years, with Subject Alternative
Names derived from a comma-separated hostname list (auto-detects IPs).
"""
from __future__ import annotations

import ipaddress
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def generate(cert_path: Path, key_path: Path, hostnames: list[str]) -> None:
    san: list[x509.GeneralName] = []
    for raw in hostnames:
        name = raw.strip()
        if not name:
            continue
        try:
            san.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            san.append(x509.DNSName(name))
    if not san:
        san.append(x509.DNSName("localhost"))
        san.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "cp-mcp-hub")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    sans_pretty = ", ".join(str(s.value) for s in san)
    print(f"generated TLS cert {cert_path} (SAN: {sans_pretty})", file=sys.stderr)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: gen_tls.py <cert_path> <key_path> <comma,separated,hostnames>", file=sys.stderr)
        return 2
    cert_path = Path(sys.argv[1])
    key_path = Path(sys.argv[2])
    hostnames = sys.argv[3].split(",")
    if cert_path.exists() and key_path.exists():
        print(f"TLS cert already present at {cert_path}; skipping generation", file=sys.stderr)
        return 0
    generate(cert_path, key_path, hostnames)
    return 0


if __name__ == "__main__":
    sys.exit(main())
