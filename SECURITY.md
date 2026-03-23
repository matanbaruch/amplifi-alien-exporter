# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | ✅ Yes             |
| < 1.0   | ❌ No              |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub Issues.**

To report a security issue privately:

1. Go to the [Security Advisories](https://github.com/matanbaruch/amplifi-alien-exporter/security/advisories) page
2. Click **"Report a vulnerability"**
3. Fill in the details, including:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

You can expect:
- **Acknowledgement** within 48 hours
- **Status update** within 5 business days
- **Credit** in the release notes (if desired)

## Security Considerations

### Credentials
- The `AMPLIFI_PASSWORD` environment variable is **required** and has no default
- Never commit your password to version control
- Use Docker secrets, `.env` files (excluded via `.gitignore`), or a secrets manager

### Network
- The exporter communicates with your AmpliFi router over HTTPS but **disables certificate verification** (self-signed cert)
- Run the exporter on a trusted internal network only
- The `/metrics` endpoint is unauthenticated — consider using a reverse proxy with auth if exposed externally

### Updates
- Pin image versions in production (`ghcr.io/matanbaruch/amplifi-alien-exporter:1.0.0` not `:latest`)
- Watch for new releases and update regularly
