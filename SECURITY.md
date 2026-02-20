# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

If you discover a security vulnerability in agentsync, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email **hello@spyrae.com** with:

1. Description of the vulnerability
2. Steps to reproduce
3. Potential impact
4. Suggested fix (if any)

We will acknowledge receipt within 48 hours and provide a timeline for a fix.

## Scope

agentsync reads and writes configuration files on your local filesystem. Security concerns include:

- **Path traversal** in config file paths
- **Arbitrary file write** outside expected directories
- **Credential exposure** in synced configs (MCP server env vars)

## Best Practices

- Review `agentsync.yaml` paths before running sync
- Use `--dry-run` to preview changes before writing
- Avoid committing configs with secrets to version control
- Use environment variables for sensitive MCP server credentials
