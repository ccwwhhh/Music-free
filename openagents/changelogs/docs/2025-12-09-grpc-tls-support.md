# gRPC TLS Support: Secure Agent-to-Network Communication

## Overview

OpenAgents now supports TLS/SSL encryption for gRPC connections between agents and networks. This enables secure, encrypted communication with optional mutual TLS (mTLS) for client certificate authentication.

## Features

### Server-Side TLS

Configure TLS on the network server:

```yaml
transports:
  - type: "grpc"
    config:
      port: 8600
      tls:
        enabled: true
        cert_file: "./certs/server.crt"
        key_file: "./certs/server.key"
        ca_file: "./certs/ca.crt"
        require_client_cert: false
        min_version: "TLS1.2"
```

### Client-Side TLS

Connect agents using the `grpcs://` URL scheme:

```python
from openagents.agents import WorkerAgent

agent = WorkerAgent()

# Using URL (recommended)
await agent.async_start(
    url="grpcs://localhost:8600",
    ssl_ca_cert="./certs/ca.crt"
)

# Using explicit parameters
await agent.async_start(
    network_host="localhost",
    network_port=8600,
    use_tls=True,
    ssl_ca_cert="./certs/ca.crt"
)
```

### Mutual TLS (mTLS)

For enhanced security, enable client certificate verification:

**Network config:**
```yaml
tls:
  enabled: true
  cert_file: "./certs/server.crt"
  key_file: "./certs/server.key"
  ca_file: "./certs/ca.crt"
  require_client_cert: true
```

**Agent code:**
```python
await agent.async_start(
    url="grpcs://localhost:8600",
    ssl_ca_cert="./certs/ca.crt",
    ssl_client_cert="./certs/client.crt",
    ssl_client_key="./certs/client.key"
)
```

## Certificate Management

### CLI Commands

Generate self-signed certificates for development:

```bash
# Generate certificates
openagents certs generate --output ./certs --common-name localhost

# Verify a certificate
openagents certs verify ./certs/server.crt
```

### Certificate Generator API

```python
from openagents.utils.cert_generator import CertificateGenerator

# Generate certificates
paths = CertificateGenerator.generate_self_signed(
    output_dir="./certs",
    common_name="localhost",
    days_valid=365,
    san_names=["127.0.0.1", "myhost.local"]
)

# Verify certificate
info = CertificateGenerator.verify_certificate("./certs/server.crt")
print(f"Valid until: {info['valid_until']}")
```

### Generated Files

```
certs/
├── ca.crt          # CA certificate (distribute to clients)
├── ca.key          # CA private key (keep secure)
├── server.crt      # Server certificate
└── server.key      # Server private key (chmod 600)
```

## URL Schemes

OpenAgents supports multiple URL schemes for agent connections:

| Scheme | Description | Default Port |
|--------|-------------|--------------|
| `grpc://` | Plain gRPC | 8600 |
| `grpcs://` | gRPC with TLS | 8600 |
| `http://` | Plain HTTP | 8700 |
| `https://` | HTTP with TLS | 8700 |
| `openagents://` | Network discovery | - |

## Configuration Models

### TLSConfig (Server)

```python
@dataclass
class TLSConfig:
    enabled: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None
    ca_file: Optional[str] = None
    require_client_cert: bool = False
    min_version: str = "TLS1.2"
```

### SSLConfig (Client)

```python
@dataclass
class SSLConfig:
    verify: bool = True
    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
```

## API Parameters

### AgentRunner.async_start() / start()

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | str | Connection URL (e.g., `grpcs://host:port`) |
| `ssl_ca_cert` | str | Path to CA certificate for server verification |
| `ssl_client_cert` | str | Path to client certificate (for mTLS) |
| `ssl_client_key` | str | Path to client private key (for mTLS) |
| `ssl_verify` | bool | Verify server certificate (default: True) |

### AgentClient.connect()

| Parameter | Type | Description |
|-----------|------|-------------|
| `use_tls` | bool | Enable TLS connection |
| `ssl_ca_cert` | str | Path to CA certificate |
| `ssl_client_cert` | str | Path to client certificate |
| `ssl_client_key` | str | Path to client key |
| `ssl_verify` | bool | Verify server certificate |

## Security Best Practices

### Development

- Use `openagents certs generate` for self-signed certificates
- Set `ssl_verify=False` only for local development (logs warning)

### Production

- Use CA-signed certificates (Let's Encrypt, DigiCert, etc.)
- Enable `require_client_cert: true` for mTLS
- Always set `ssl_verify=True`
- Keep private keys secure (chmod 600)
- Rotate certificates before expiration

## Troubleshooting

### Certificate Verification Failed

```
ssl.SSLCertVerificationError: certificate verify failed
```

**Solutions:**
- Ensure `ssl_ca_cert` points to the correct CA certificate
- Verify the server certificate is signed by the CA
- Check certificate hasn't expired: `openagents certs verify cert.pem`

### Connection Refused

```
grpc._channel._InactiveRpcError: Connection refused
```

**Solutions:**
- Verify the server is listening with TLS enabled
- Check firewall allows the port
- Ensure URL scheme matches server config (`grpcs://` for TLS)

### Permission Denied on Key File

```
PermissionError: [Errno 13] Permission denied: 'server.key'
```

**Solutions:**
- Set correct permissions: `chmod 600 server.key`
- Verify file ownership

## Backward Compatibility

TLS support is fully backward compatible:

- Non-TLS connections work unchanged
- All new parameters are optional
- Legacy connection methods still supported
- Existing configurations require no changes

## Performance

- TLS adds ~5-10ms latency per connection establishment
- No ongoing performance impact after connection
- Certificate loading is one-time on startup

## Related Documentation

- [gRPC Authentication Guide](https://grpc.io/docs/guides/auth/)
- [Example: grpcs_example.py](../examples/grpcs_example.py)
- [Example: grpcs_network.yaml](../examples/grpcs_network.yaml)
