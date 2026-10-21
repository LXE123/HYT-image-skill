# Cross-platform runtime bootstrap

Package initialization itself uses only the Python standard library. Use the bootstrapper before image-processing operations when the active Python lacks NumPy and Pillow. It creates or refreshes only `<system Desktop>/ProductVisualWorkspace/products/<product_id>/<version>/.runtime/`.

- macOS/Linux: `sh scripts/bootstrap_runtime.sh <package-root>`
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/bootstrap_runtime.ps1 -PackageRoot <package-root>`

If Python 3.10+ is absent, ask for authorization before adding `--install-python` on macOS/Linux or `-InstallPython` on Windows. The launchers use only an existing package manager: Homebrew on macOS; apt, dnf, yum, or pacman on Linux; winget, Chocolatey, or Scoop on Windows. Otherwise they stop and direct the user to the official Python installer.
