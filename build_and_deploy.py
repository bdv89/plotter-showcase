"""Build and deploy script for CSV Plotter releases.

This script automates the release process:
1. Freezes the version timestamp (YYMMDD) at build time
2. Builds the executable with PyInstaller
3. Archives the previous version on the SMB share
4. Deploys the new version to the SMB share
5. Updates version.txt (SSOT for version checking)

Usage:
    python build_and_deploy.py

Environment Variables:
    CSVPLOTTER_UPDATE_PATH: Override default SMB path for deployment
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ============================================
# CONFIGURATION - CHANGE FOR YOUR ENVIRONMENT
# ============================================

# Default SMB share path (can be overridden with env var)
DEFAULT_SMB_PATH = r"\\<FILE_SERVER>\<SHARE>"

# PyInstaller configuration
MAIN_SCRIPT = "launcher.py"
DIST_DIR = "dist"
EXE_NAME = "csvplotter.exe"

# ============================================

# Generate version timestamp (frozen at build time)
BUILD_VERSION = datetime.now().strftime("%y%m%d")

# Allow override of deployment path
SMB_SHARE_PATH = os.getenv("CSVPLOTTER_UPDATE_PATH", DEFAULT_SMB_PATH)


def freeze_version_in_source():
    """Freeze the dynamic version to a static timestamp before build.

    This ensures the built executable has a fixed version string
    instead of generating it dynamically at runtime.

    Returns:
        Path: Backup file path for restoration
    """
    print(f"🔒 Freezing version to {BUILD_VERSION}...")

    version_py = Path("version.py")
    if not version_py.exists():
        raise FileNotFoundError("version.py not found in current directory")

    content = version_py.read_text(encoding='utf-8')

    # Replace dynamic version with frozen build timestamp
    frozen_content = content.replace(
        'datetime.now().strftime("%y%m%d")',
        f'"{BUILD_VERSION}"'
    )

    # Backup original
    backup = version_py.with_suffix(".py.bak")
    shutil.copy2(version_py, backup)

    # Write frozen version
    version_py.write_text(frozen_content, encoding='utf-8')

    print(f"   Backup created: {backup}")
    return backup


def restore_version_source(backup_path):
    """Restore the original version.py from backup.

    Args:
        backup_path: Path to the backup file
    """
    print("🔓 Restoring original version.py...")
    version_py = Path("version.py")
    shutil.move(backup_path, version_py)


def build_exe():
    """Build executable with PyInstaller.

    Returns:
        bool: True if build succeeded, False otherwise
    """
    print(f"🔨 Building CSV Plotter {BUILD_VERSION}...")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name", "csvplotter",
        MAIN_SCRIPT
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Build successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed:")
        print(e.stderr)
        return False


def deploy_to_smb():
    """Deploy built executable to SMB share.

    Raises:
        FileNotFoundError: If SMB share is not accessible
    """
    if SMB_SHARE_PATH in ("0", ""):
        print("⚠️  Deployment skipped (CSVPLOTTER_UPDATE_PATH=0)")
        print(f"   Built executable available at: {Path(DIST_DIR) / EXE_NAME}")
        return

    print(f"📦 Deploying to {SMB_SHARE_PATH}...")

    smb_path = Path(SMB_SHARE_PATH)
    if not smb_path.exists():
        raise FileNotFoundError(
            f"SMB share not accessible: {SMB_SHARE_PATH}\n"
            f"   - Check network connectivity\n"
            f"   - Verify share exists and you have permissions\n"
            f"   - Try accessing manually: {smb_path}"
        )

    # Paths
    exe_source = Path(DIST_DIR) / EXE_NAME
    exe_latest = smb_path / EXE_NAME
    exe_archive = smb_path / "archive" / f"csvplotter_{BUILD_VERSION}.exe"
    version_file = smb_path / "version.txt"
    archive_dir = smb_path / "archive"

    # Verify source exe exists
    if not exe_source.exists():
        raise FileNotFoundError(f"Built executable not found: {exe_source}")

    # Create archive dir if needed
    archive_dir.mkdir(exist_ok=True)

    # Archive current version if exists
    if exe_latest.exists():
        print(f"📂 Archiving previous version...")
        if version_file.exists():
            old_version = version_file.read_text().strip()
            old_archive = smb_path / "archive" / f"csvplotter_{old_version}.exe"
            try:
                shutil.copy2(exe_latest, old_archive)
                print(f"   Archived as: {old_archive.name}")
            except Exception as e:
                print(f"   ⚠️  Archive failed: {e}")

    # Copy new version
    print(f"📤 Copying {EXE_NAME}...")
    shutil.copy2(exe_source, exe_latest)
    shutil.copy2(exe_source, exe_archive)

    # Update version.txt (SSOT)
    print(f"✍️  Writing version.txt: {BUILD_VERSION}")
    version_file.write_text(BUILD_VERSION, encoding='utf-8')

    print(f"\n✅ Deployed version {BUILD_VERSION}")
    print(f"   Latest: {exe_latest}")
    print(f"   Archive: {exe_archive}")
    print(f"   Version file: {version_file}")


def main():
    """Main build and deploy workflow."""
    print("=" * 60)
    print(f"CSV Plotter Release Builder - Version {BUILD_VERSION}")
    print("=" * 60)
    print()

    backup_path = None

    try:
        # Step 1: Freeze version
        backup_path = freeze_version_in_source()

        # Step 2: Build
        if not build_exe():
            print("\n❌ Build failed. Aborting deployment.")
            return 1

        # Step 3: Deploy
        deploy_to_smb()

        print()
        print("=" * 60)
        print(f"🎉 Release {BUILD_VERSION} completed successfully!")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    finally:
        # Always restore original version.py
        if backup_path and backup_path.exists():
            restore_version_source(backup_path)


if __name__ == "__main__":
    sys.exit(main())
