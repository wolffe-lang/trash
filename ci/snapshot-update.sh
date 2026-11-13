#!/bin/sh
set -eu
apt-get update --snapshot "$1"
