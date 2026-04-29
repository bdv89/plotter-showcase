# Release Procedure

## Versioning Strategy

This project uses **timestamp-based versioning** (YYMMDD format) instead of semantic versioning.

**Why timestamps?**
- ✅ Zero decision-making: version = build date
- ✅ Immediate traceability: "bug in version from Nov 18" is clearer than "bug in v1.2.3"
- ✅ Perfect for frequent releases: no need to decide between patch/minor/major
- ✅ Natural ordering: `251118` < `251119` (string comparison works)

**Version format**: `YYMMDD`
- Example: `251118` = November 18, 2025
- Displayed as: "18 Nov 2025" in the UI

## How to Publish a New Version

**Prerequisites**:
1. PyInstaller installed: `pip install pyinstaller`
2. SMB share configured on Windows Server (see Setup below)
3. Network access to the SMB share

**Release workflow** (2 minutes):

```bash
# 1. Test locally
python launcher.py

# 2. Build and deploy (automatically freezes version to today's date)
python build_and_deploy.py

# 3. Verify deployment
# - Check \\YOUR_SERVER\CSVPlotter\version.txt contains today's date (YYMMDD)
# - Check \\YOUR_SERVER\CSVPlotter\csvplotter.exe was updated
# - Check \\YOUR_SERVER\CSVPlotter\archive\csvplotter_YYMMDD.exe exists

# 4. Notify users (optional)
# Send message: "New version available on \\YOUR_SERVER\CSVPlotter"
```

**What `build_and_deploy.py` does**:
1. Freezes version in code (replaces `datetime.now()` with static timestamp)
2. Builds executable with PyInstaller (`dist/csvplotter.exe`)
3. Archives previous version to `\\SERVER\CSVPlotter\archive\csvplotter_OLDDATE.exe`
4. Copies new version to `\\SERVER\CSVPlotter\csvplotter.exe`
5. Updates `\\SERVER\CSVPlotter\version.txt` (SSOT for version checking)
6. Restores original source code (removes frozen version)

## Update Checking Behavior

**Default behavior**:
- App checks for updates on startup
- Reads `\\YOUR_SERVER\CSVPlotter\version.txt`
- If server version > local version, shows popup with download link
- Silent failure if network unavailable or share inaccessible

**Disabling update checks** (for offline development/testing):

```bash
# Temporary disable
set CSVPLOTTER_UPDATE_PATH=0
python launcher.py

# Permanent disable (Windows environment variable)
# System Properties → Environment Variables → Add user variable:
#   Name: CSVPLOTTER_UPDATE_PATH
#   Value: 0
```

**Using a different server** (for testing):

```bash
set CSVPLOTTER_UPDATE_PATH=\\TEST_SERVER\CSVPlotter
python launcher.py
```

## One-Time SMB Share Setup

**On Windows Server** (do this once):

1. **Create shared folder**:
   ```
   C:\Shares\CSVPlotter\
   C:\Shares\CSVPlotter\archive\
   ```

2. **Share via SMB**:
   - Right-click `C:\Shares\CSVPlotter` → Properties
   - "Sharing" tab → "Advanced Sharing"
   - Check "Share this folder"
   - Share name: `CSVPlotter`
   - Permissions:
     - Users: Read (for update checking and downloading)
     - Your account: Full Control (for deployment)

3. **Test access**:
   ```
   # From your dev machine
   \\YOUR_SERVER_NAME\CSVPlotter
   ```
   You should see the empty folder.

4. **Configure deployment script**:
   - Edit `build_and_deploy.py` line 25:
     ```python
     DEFAULT_SMB_PATH = r"\\YOUR_SERVER_NAME\CSVPlotter"
     ```
   - Edit `version.py` line 34:
     ```python
     DEFAULT_SMB_PATH = r"\\YOUR_SERVER_NAME\CSVPlotter"
     ```

## Troubleshooting Deployment

**"SMB share not accessible"**
- Verify server name: try `ping YOUR_SERVER_NAME`
- Check network connectivity (VPN connected if remote?)
- Verify share exists: browse to `\\YOUR_SERVER_NAME\CSVPlotter` in Windows Explorer
- Check permissions: you need Write access to deploy

**"Permission denied" when copying**
- Close any running instances of csvplotter.exe on the server
- Verify you have Full Control permissions on the SMB share
- Try running command prompt as Administrator

**"PyInstaller not found"**
```bash
pip install pyinstaller
```

**Users don't see update notification**
- Verify `version.txt` exists on share
- Check `version.txt` content matches deployed version (YYMMDD)
- Ensure users have Read access to SMB share
- Test manually: read `\\SERVER\CSVPlotter\version.txt` from user's machine

**Build succeeds but deployment fails**
- Deployment is optional: find built exe in `dist/csvplotter.exe`
- Copy manually to SMB share if needed
- Set `CSVPLOTTER_UPDATE_PATH=0` to skip deployment during build

## Version Display

**In the application**:
- Window title shows formatted version: "CSV Visualizer (18 Nov 2025)"
- About dialog (if added) should show `__version__` from `version.py`

**For bug reports**:
- Ask users: "What date is shown in the window title?"
- This maps directly to the build date
- Find corresponding archived version: `\\SERVER\CSVPlotter\archive\csvplotter_251118.exe`

## Hotfixes (Multiple Releases Same Day)

If you need multiple releases on the same day, manually add a suffix:

**Option A: Manual suffix**
```python
# In build_and_deploy.py, line 46:
BUILD_VERSION = datetime.now().strftime("%y%m%d") + "a"  # 251118a, 251118b, etc.
```

**Option B: Add timestamp**
```python
# In build_and_deploy.py, line 46:
BUILD_VERSION = datetime.now().strftime("%y%m%d_%H%M")  # 251118_1430
```

Then update `format_version_display()` in `version.py` to handle the suffix.
