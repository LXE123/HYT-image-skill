#!/usr/bin/env python3
"""Print the deterministic desktop path for one product package."""

import argparse
from pathlib import Path

from desktop_location import product_package_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--require-existing", action="store_true")
    parser.add_argument("--desktop-root", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        package = product_package_path(args.product_id, args.version, args.desktop_root)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.require_existing and not (package / "index.json").is_file():
        parser.error(f"产品包不存在或尚未初始化：{package}")
    print(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
