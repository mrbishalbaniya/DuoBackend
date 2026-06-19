# 🚀 Start Here - Python 3.12 Setup

## Quick Start (3 Steps)

### Step 1: Run Setup Script
**Right-click** `scripts\RUN_ME_AS_ADMIN.bat` → **Run as Administrator**

The script will:
- Remove all old Python installations
- Install Python 3.12.8
- Setup environment variables
- Install Django and dependencies

### Step 2: Disable App Execution Aliases
1. Press `Win + I` (open Settings)
2. Go to: **Apps** → **Advanced app settings** → **App execution aliases**
3. Turn **OFF** these toggles:
   - `python.exe`
   - `python3.exe`

### Step 3: Restart Computer
**Important:** Restart your computer for PATH changes to take effect.

---

## After Restart

### Verify Setup
Run: `.\scripts\verify_setup.ps1`

This checks if everything is working correctly.

### Start Development

```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Run Django server
python manage.py runserver
```

Your server should start at: http://127.0.0.1:8000

---

## Files Overview

| File | Purpose |
|------|---------|
| `scripts\RUN_ME_AS_ADMIN.bat` | **START HERE** - Main setup script |
| `scripts\complete_python_setup.ps1` | Full automated setup |
| `scripts\verify_setup.ps1` | Verify installation after restart |
| `docs\SETUP_INSTRUCTIONS.md` | Detailed setup guide |
| `scripts\cleanup_python_simple.ps1` | Cleanup only (if needed) |

---

## Troubleshooting

**"Python was not found"**
- Check: Did you disable App Execution Aliases?
- Check: Did you restart your computer?
- Solution: Open a NEW PowerShell window

**"Permission denied"**
- Run PowerShell as Administrator

**Packages won't install**
```powershell
.\venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Need Help?

See detailed instructions in: `scripts\docs\SETUP_INSTRUCTIONS.md`
