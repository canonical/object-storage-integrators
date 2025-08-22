import dataclasses


@dataclasses.dataclass(frozen=True)
class S3ConnectionInfo:
    endpoint: str
    access_key: str
    secret_key: str
    region: str
    tls_ca_chain: str
