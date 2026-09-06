# Masi Django backend

Use the repository `venv/` for Python and Django commands. See `CLAUDE.md` for
repository conventions and `documentation/build-log.md` for release evidence.

## Finance publisher dependency

Local installs from `requirements.txt` require `MASI_FINANCE_GITHUB_TOKEN` in the
environment for the private `masi-finance` v0.2.0 Git dependency. Alternatively,
manually install the verified `masi-finance` 0.2.0 wheel into the virtual
environment and install the remaining requirements without the private Git line;
pip will still attempt that Git URL if the complete requirements file is used.

Render must provide `MASI_FINANCE_GITHUB_TOKEN` as a service secret before the
foundation build. `build.sh` checks the installed publisher import and exact
version immediately after dependency installation, before migrations.
