#!/usr/bin/env bash

python3 -c "
import secrets, re, pathlib, sys
env = pathlib.Path('.env')
text = env.read_text() if env.exists() else ''
if 'SECRET_KEY=' in text:
    print('ERROR: SECRET_KEY already exists in .env — aborting to avoid invalidating sessions.')
    print('Delete the existing SECRET_KEY line manually if you really want to regenerate it.')
    sys.exit(1)
new_line = 'SECRET_KEY=' + secrets.token_hex(32)
text = text.rstrip('\n') + '\n' + new_line + '\n'
env.write_text(text)
print('Secret key written to .env')
"