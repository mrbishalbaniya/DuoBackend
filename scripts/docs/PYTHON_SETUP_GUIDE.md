# Complete Python 3.12 Setup Guide

This guide will help you completely remove existing Python installations and install Python 3.12 properly.

## 🚀 Quick Start (3 Steps)

### Step 1: Cleanup (Run as Administrator)
```powershell
# Right-click PowerShell, select "Run as Administrator"
cd "d:\8sem\DuoBackend"
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\scripts\cleanup_python.ps1
```

**After cleanup:**
1. Go to **Settings** → **Apps** → **Advanced app settings** → **App execution aliases**
2. **Disable** these toggles:
   - ☐ python.exe
   - ☐ python3.exe
   - ☐ pip.exe
3. **Restart your computer**

### Step 2: Install Python 3.12 (Run as Administrator)
```powershell
# After restart, open PowerShell as Administrator
cd "d:\8sem\DuoBackend"
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
.\install_python312.ps1
```

**After installation:**
1. Close **ALL** PowerShell/Command Prompt windows
2. Open a **new** PowerShell window (normal, not admin)
3. Verify installation:
```powershell
python --version
# Should show: Python 3.12.9

pip --version
# Should show: pip 26.x.x from C:\Program Files\Python312\...
```

### Step 3: Setup Django Project
```powershell
# In a new PowerShell window (normal mode)
cd "d:\8sem\DuoBackend"
.\scripts\setup_project.ps1
```

---

## 📋 Manual Steps (If Scripts Don't Work)

### Manual Cleanup
1. **Uninstall Python:**
   - Open **Settings** → **Apps** → **Installed Apps**
   - Search "Python" and uninstall all entries

2. **Disable Store Aliases:**
   - **Settings** → **Apps** → **Advanced app settings** → **App execution aliases**
   - Disable: python.exe, python3.exe, pip.exe

3. **Clean Environment Variables:**
   - Press `Win + R` → type `sysdm.cpl` → Enter
   - Click **Environment Variables**
   - Edit **PATH** (both User and System)
   - Remove all lines containing "Python"

4. **Delete Python folders:**
   - `C:\Users\mrbis\AppData\Local\Programs\Python`
   - `C:\Users\mrbis\AppData\Local\Python`
   - `C:\Program Files\Python*`

5. **Restart computer**

### Manual Installation
1. Download Python 3.12.9:
   - https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe

2. Run installer:
   - ✅ Check "Add Python 3.12 to PATH"
   - Click "Customize installation"
   - ✅ Check all Optional Features
   - ✅ Check "Install for all users"
   - ✅ Check "Add Python to environment variables"
   - Install path: `C:\Program Files\Python312`

3. Verify in new terminal:
   ```powershell
   python --version
   pip --version
   ```

### Manual Project Setup
```powershell
# Create virtual environment
cd "d:\8sem\DuoBackend"
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Run server
python manage.py runserver
```

---

## ⚠️ Troubleshooting

### "Python not found" after installation
- Close ALL terminals and open new one
- If still not found, restart computer
- Check PATH: `$env:PATH -split ';' | Select-String Python`

### "Execution Policy" error
```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
```

### Virtual environment activation error
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Pip install fails
```powershell
python -m pip install --upgrade pip
pip cache purge
pip install -r requirements.txt --no-cache-dir
```

### "Access Denied" during cleanup
- Run PowerShell as Administrator
- Close any Python processes in Task Manager
- Restart and try again

---

## ✅ Success Checklist

- [ ] All old Python versions uninstalled
- [ ] App execution aliases disabled
- [ ] Computer restarted
- [ ] Python 3.12.9 installed
- [ ] `python --version` shows Python 3.12.9
- [ ] `pip --version` shows pip from Python312 folder
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Django migrations completed
- [ ] Development server runs successfully

---

## 🎯 Final Test

```powershell
# Test Python
python --version

# Test pip
pip --version

# Test Django
cd "d:\8sem\DuoBackend"
.\venv\Scripts\Activate.ps1
python manage.py check

# Run server
python manage.py runserver
```

If server starts successfully, visit: http://127.0.0.1:8000/

---

## 📞 Need Help?

If scripts fail, follow the "Manual Steps" section above. The automated scripts are designed to handle most scenarios, but manual steps ensure complete control over the process.
