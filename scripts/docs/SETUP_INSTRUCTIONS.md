# Complete Python 3.12 Setup Instructions

## 🚀 Quick Setup (Recommended)

### Option 1: Automated Setup (Easy)

1. **Right-click** `scripts\RUN_ME_AS_ADMIN.bat` → **Run as Administrator**
2. Wait for the script to complete
3. **Disable App Execution Aliases** (important!):
   - Press `Win + I` → Settings
   - Go to: **Apps** → **Advanced app settings** → **App execution aliases**
   - Turn **OFF** the toggles for `python.exe` and `python3.exe`
4. **Restart your computer**
5. Open PowerShell and verify:
   ```
   python --version
   pip --version
   ```

### Option 2: Manual PowerShell (Advanced)

1. Open PowerShell as Administrator
2. Run:
   ```powershell
   Set-ExecutionPolicy Bypass -Scope Process -Force
   .\complete_python_setup.ps1
   ```
3. Follow steps 3-5 from Option 1 above

---

## 📋 What the Script Does

1. **Cleanup Phase**
   - Stops all Python processes
   - Removes old Python installations from:
     - `%LOCALAPPDATA%\Programs\Python`
     - `C:\Program Files\Python*`
     - `C:\Python*`
   - Cleans PATH environment variables
   - Removes Python registry entries

2. **Installation Phase**
   - Downloads Python 3.12.8 (64-bit)
   - Installs to `C:\Python312`
   - Configures system PATH
   - Installs pip and setuptools

3. **Project Setup Phase**
   - Creates fresh virtual environment
   - Installs Django and all dependencies
   - Configures project for development

---

## ✅ Verification Steps

After completing setup and restarting:

```powershell
# Check Python version
python --version
# Should show: Python 3.12.8

# Check pip version
pip --version
# Should show: pip 24.x.x from C:\Python312\...

# Check installation location
where python
# Should show: C:\Python312\python.exe

# Activate virtual environment
.\venv\Scripts\activate

# Run Django
python manage.py runserver
```

---

## 🛠 Troubleshooting

### Issue: "Python was not found"

**Solution:**
1. Verify Python is installed: `dir C:\Python312`
2. Check if App Execution Aliases are disabled
3. Restart your computer
4. Open a NEW PowerShell window

### Issue: PATH not updated

**Solution:**
1. Open System Properties → Advanced → Environment Variables
2. System variables → PATH → Edit
3. Ensure these are at the TOP:
   - `C:\Python312`
   - `C:\Python312\Scripts`
4. Click OK and restart

### Issue: Permission Denied

**Solution:**
- Run PowerShell or Command Prompt as Administrator
- Ensure no Python processes are running (Task Manager)

### Issue: Package installation fails

**Solution:**
```powershell
# Activate venv
.\venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install packages one by one
pip install Django
pip install djangorestframework
pip install django-cors-headers
pip install pillow
pip install channels
pip install daphne
```

---

## 🎯 Manual Setup (If Script Fails)

### 1. Download Python

Go to: https://www.python.org/downloads/
- Download Python 3.12.8 (Windows installer 64-bit)

### 2. Install Python

Run installer with these options:
- ✅ Install for all users
- ✅ Add Python to PATH
- ✅ Install pip
- Install location: `C:\Python312`

### 3. Configure Environment

1. Open System Properties:
   - Right-click "This PC" → Properties
   - Advanced system settings
   - Environment Variables

2. Edit System PATH:
   - Add to the TOP of PATH:
     - `C:\Python312`
     - `C:\Python312\Scripts`

3. Disable App Execution Aliases:
   - Settings → Apps → Advanced app settings → App execution aliases
   - Turn OFF python.exe and python3.exe

4. Restart computer

### 4. Setup Project

```powershell
# Navigate to project
cd d:\8sem\DuoBackend

# Create virtual environment
python -m venv venv

# Activate
.\venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start server
python manage.py runserver
```

---

## 📝 Important Notes

1. **Always use Administrator** when running setup scripts
2. **Restart computer** after installation for PATH changes to take effect
3. **Disable App Execution Aliases** to prevent Microsoft Store interference
4. **Use virtual environment** for project dependencies
5. **Close all terminals** before running setup to avoid file locks

---

## 🔧 Project Commands

```powershell
# Activate virtual environment
.\venv\Scripts\activate

# Run development server
python manage.py runserver

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Install new package
pip install package-name

# Update requirements
pip freeze > requirements.txt

# Deactivate virtual environment
deactivate
```

---

## 📞 Still Having Issues?

If setup fails, check:
1. Antivirus isn't blocking installation
2. You have admin rights
3. No Python processes are running
4. Sufficient disk space (at least 500MB)

Run the cleanup script first:
```powershell
.\scripts\cleanup_python_simple.ps1
```

Then try the full setup again.
