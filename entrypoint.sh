#!/bin/bash

set -e -x

exec ./tlstester.py -v \
	--base-port 4300 --sequential \
	--listen 0.0.0.0 \
	--hostname "${TLSTEST_DOMAIN:-localhost.localdomain}"