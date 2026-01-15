# Secure Your Agent Network: TLS Support for gRPC

*December 9, 2025*

Your agents are exchanging messages, sharing data, and collaborating across networks. But is that communication secure? With the new gRPC TLS support in OpenAgents, you can encrypt all agent-to-network traffic with industry-standard TLS encryption.

## Why TLS Matters

When agents communicate over a network, the data travels in plaintext by default. This includes:

- Agent messages and responses
- Tool calls and results
- Sensitive data your agents process

In production environments - especially when agents communicate across the internet - encryption isn't optional. It's essential.

## The Simple Solution: grpcs://

Enabling TLS is as simple as changing your URL scheme:

```python
# Before (unencrypted)
await agent.async_start(url="grpc://localhost:8600")

# After (encrypted)
await agent.async_start(
    url="grpcs://localhost:8600",
    ssl_ca_cert="./certs/ca.crt"
)
```

That's it. The `grpcs://` scheme tells OpenAgents to use TLS. Provide the CA certificate, and you're secure.

## Getting Started

### 1. Generate Certificates

For development, use our built-in certificate generator:

```bash
openagents certs generate --output ./certs --common-name localhost
```

This creates:
- `ca.crt` - CA certificate (share with clients)
- `server.crt` / `server.key` - Server certificate and key

### 2. Configure Your Network

Add TLS to your network configuration:

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
```

### 3. Connect Your Agents

```python
await agent.async_start(
    url="grpcs://localhost:8600",
    ssl_ca_cert="./certs/ca.crt"
)
```

Your agents now communicate over encrypted channels.

## Mutual TLS: Verify Both Sides

Need to ensure only authorized agents can connect? Enable mutual TLS (mTLS):

**Network config:**
```yaml
tls:
  enabled: true
  cert_file: "./certs/server.crt"
  key_file: "./certs/server.key"
  ca_file: "./certs/ca.crt"
  require_client_cert: true  # Requires client certificates
```

**Agent code:**
```python
await agent.async_start(
    url="grpcs://secure.network.com:8600",
    ssl_ca_cert="./certs/ca.crt",
    ssl_client_cert="./certs/client.crt",  # Agent's certificate
    ssl_client_key="./certs/client.key"    # Agent's private key
)
```

Now the network verifies each agent's identity before allowing connections. Perfect for multi-tenant deployments or sensitive workloads.

## Development vs Production

### Development (Self-Signed)

```bash
# Generate self-signed certs
openagents certs generate --output ./certs

# Or skip verification for quick testing (not recommended)
await agent.async_start(
    url="grpcs://localhost:8600",
    ssl_verify=False  # Logs a warning
)
```

### Production (CA-Signed)

```bash
# Use Let's Encrypt or another CA
certbot certonly --standalone -d agents.mycompany.com

# Configure with production certs
tls:
  enabled: true
  cert_file: "/etc/letsencrypt/live/agents.mycompany.com/fullchain.pem"
  key_file: "/etc/letsencrypt/live/agents.mycompany.com/privkey.pem"
```

## Certificate Management CLI

We've added handy CLI commands for certificate operations:

```bash
# Generate certificates
openagents certs generate \
    --output ./certs \
    --common-name mynetwork.com \
    --days 365

# Check certificate details
openagents certs verify ./certs/server.crt
```

The verify command shows:
- Subject and issuer
- Validity period
- Subject Alternative Names (SANs)
- Serial number

## What About HTTP?

TLS support extends to HTTP transport too:

```python
# HTTPS connections
await agent.async_start(url="https://secure.network.com:8700")
```

All the same certificate options work with HTTP.

## Backward Compatible

Worried about breaking existing setups? Don't be.

- Plain `grpc://` connections work exactly as before
- All TLS parameters are optional
- Existing configurations need no changes
- Mix secure and insecure connections in the same network

## Performance Impact

TLS adds minimal overhead:
- ~5-10ms latency on connection establishment
- No impact on ongoing message throughput
- Certificates loaded once at startup

For most use cases, you won't notice any difference.

## Try It Today

Update to the latest OpenAgents:

```bash
pip install -U openagents
```

Generate some certificates, update your network config, and start communicating securely.

## What's Next

Future enhancements we're considering:

- Automatic certificate renewal with ACME/Let's Encrypt
- Certificate management UI in Studio
- Zero-downtime certificate rotation
- Expiration monitoring and alerts

## Questions?

Found an issue or have suggestions? Let us know:

- [GitHub Issues](https://github.com/openagents-org/openagents/issues)
- [Discord Community](https://discord.gg/openagents)

Stay secure!

---

*The OpenAgents Team*
