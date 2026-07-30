# Optional company root certificate

The backend trusts normal public certificate authorities by default.

If a company network inspects HTTPS traffic, export the company root certificate as PEM and save
it in this directory, for example:

```text
backend/certs/company-root-ca.pem
```

Then set this inside the project `.env`:

```dotenv
ATS_CA_BUNDLE=/app/certs/company-root-ca.pem
OUTBOUND_CA_BUNDLE=/app/certs/company-root-ca.pem
```

Rebuild the backend after changing the certificate:

```bash
docker compose up --build
```

Never commit the company certificate. TLS verification must not be disabled.
