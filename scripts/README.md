# DuoBackend scripts

Utility scripts for local development and Windows setup. Run these from the `DuoBackend` root unless noted.

## Daily use

- `run-server.ps1` / `run-server.bat` — start Django on port 8001
- `install-deps.ps1` — install `requirements.txt` into `venv`
- `setup_project.ps1` — full project setup (venv + deps + migrations)

## Data helpers

- `run_seed_random_users.py` — seed random demo users
- `run_seed_profile_photos.py` — add profile photo URLs
- `reset_demo_password.py` — reset `demo` user password to `demo1234`

## Windows Python setup (optional)

- `RUN_ME_AS_ADMIN.bat` — full Python 3.12 setup (run as Administrator)
- `complete_python_setup.ps1` — called by the batch file above
- `install_python312.ps1` — install Python 3.12 only
- `cleanup_python.ps1` / `cleanup_python_simple.ps1` — remove old Python installs
- `verify_setup.ps1` — verify Python/venv after setup

See `docs/` for detailed setup guides.
