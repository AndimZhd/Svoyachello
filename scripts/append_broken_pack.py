#!/usr/bin/env python3
"""
Append pack themes that contain between one and five questions.

Usage:
    python scripts/append_broken_pack.py <pack_short_name> <json_file_path>
    python scripts/append_broken_pack.py <pack_short_name> <json_file_path> --name "Pack Name"
"""

import asyncio

from append_pack import main


if __name__ == '__main__':
    asyncio.run(main(allow_incomplete_themes=True))
