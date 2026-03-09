#!/bin/bash

python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" >> .env
echo "Secret key written to .env"