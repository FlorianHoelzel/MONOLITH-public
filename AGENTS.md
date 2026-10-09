# MONOLITH development

- Keep credentials, device identifiers, databases and runtime state outside Git.
- Use `.env.example` as the configuration reference. Never publish a real `.env`.
- Use temporary data and `PYTHON_DOTENV_DISABLED=1` for automated tests.
- Do not start a persistent dashboard or HomeKit bridge during verification.
- Deploy only to an explicitly supplied destination with the user's authorization.
- Keep MONOLITH on a trusted local network; never enable public port forwarding.
- Review tracked files and build outputs for personal data before publishing.
