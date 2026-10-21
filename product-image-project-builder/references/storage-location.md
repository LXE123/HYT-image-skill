# Desktop storage location

Product packages use one deterministic, designer-visible root:

```text
<system Desktop>/ProductVisualWorkspace/products/<product_id>/<version>/
```

`initialize_package.py` and `resolve_package_path.py` calculate this path. Do not derive it from the shell working directory and do not ask the designer to browse for a folder during ordinary intake.

On macOS, the desktop is the current user's `~/Desktop`; Finder localization does not change the underlying path. On Windows, resolve the Desktop Known Folder through the system API, which supports Unicode user names, localized installations, domain profiles, and redirected or OneDrive-managed desktops. Do not build a Windows desktop path by concatenating `C:\Users\<name>\Desktop`.

Folder segments accept Unicode but reject path separators, control characters, Windows-invalid characters, trailing dots/spaces, and reserved device names. This prevents a product ID or version from escaping the fixed workspace.

Use `--desktop-root` only when the user explicitly requests another desktop root or for isolated testing. All three product skills must keep using the exact package path returned by the initializer or resolver.

## Existing-folder policy

- An existing `ProductVisualWorkspace` or `products` directory is normal; reuse it.
- Different product IDs and versions remain isolated and may coexist.
- When the exact product/version directory contains a valid `index.json` and `PRODUCT_STATE.json` matching all initialization parameters, report `RESUME` and do not overwrite either file.
- An empty directory, or a directory containing only the expected empty input scaffold, may be completed after an interrupted setup.
- If only one control file exists, either control file is invalid, identity/mode/scope differs, the target is a regular file, or unrecognized content exists before initialization, stop without overwriting or adopting it.
- Never choose a new suffix automatically. A collision needs an explicit new version or a deliberate repair of the existing package.
