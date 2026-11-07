# Security

## Reporting

Please use this repository's GitHub **Security → Report a vulnerability** option for confidential reports. Do not include live keys, passwords, session cookies, private learner data, or exploit details in public issues.

## Configuration

- Generate a unique service API key of at least 32 characters in `backend/.env`.
- Configure provider keys on the server. Browser-exposed `VITE_*` variables are public.
- The Compose database credentials are disposable local development defaults. Replace them for deployment.
- Configure account authentication, HTTPS, explicit origins, email, and provider callbacks before opening an instance to other users. Read `docs/authentication.md`.
- `compose.dev.yaml` grants Docker socket access for local rendering. Use it only on a trusted development machine.
- Treat generated executable lesson content as untrusted and preserve rendering isolation and timeouts.

## Public snapshot checks

The initial public release uses a fresh Git root, exports tracked source only, excludes local agent/editor configuration and unrelated planning files, clears the service-key example, replaces the personal default profile name, and includes selected reviewed demo media. Video container metadata is stripped. No old source history or private environment file is copied.

Gitleaks scans content and Git history. The only configured exceptions are exact known offline test strings, rather than whole test folders. Automated scanning reduces exposure risk but cannot establish that arbitrary content contains no sensitive information. If a real credential is ever exposed, revoke or rotate it at the provider; deleting it from a file alone is insufficient.
