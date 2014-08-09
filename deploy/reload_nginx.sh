#!/bin/sh

# install: sudo cp reload_nginx.sh /usr/local/bin/reload_nginx

# SUDO: d ALL=NOPASSWD: /usr/local/bin/reload_nginx

kill -HUP $( cat /var/run/nginx.pid )