#!/usr/bin/env python3
"""Wrap the built board as a complete HTML document for sharing or hosting.

    python3 scripts/standalone.py board.html board.standalone.html

The board itself is a fragment meant to be embedded. Sending that fragment
directly costs you the charset and, more importantly, the viewport tag - without
which the wide tables render at desktop width on a phone.
"""
import sys

if len(sys.argv) != 3:
    sys.exit(__doc__)
src, dst = sys.argv[1], sys.argv[2]
body = open(src).read()
open(dst, "w").write(
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    '<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    '<meta name="robots" content="noindex">\n'
    '<title>Riftbound Case Board</title>\n'
    '<style>html,body{margin:0;padding:0;background:#F7F8FC;}</style>\n'
    '</head>\n<body>\n' + body + '\n</body>\n</html>\n'
)
print(f"wrote {dst}")
