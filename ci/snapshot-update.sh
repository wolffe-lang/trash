#!/bin/sh
set -eu
if ! apt-get -o APT::Update::Error-Mode=any update --snapshot "$1"; then
    printf '%s\n' 'FAIL snapshot-index: snapshot package index update failed' >&2
    exit 1
fi
