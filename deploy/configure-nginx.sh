#!/bin/sh
set -eu
test ! -e /etc/nginx/sites-available/akimai-ip
test ! -e /etc/nginx/sites-enabled/akimai-ip
umask 077
openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
    -subj /CN=95.216.156.245 \
    -addext subjectAltName=IP:95.216.156.245 \
    -keyout /etc/nginx/akimai-ip.key \
    -out /etc/nginx/akimai-ip.crt >/dev/null 2>&1
password="$(openssl rand -hex 12)"
hash="$(openssl passwd -apr1 "$password")"
printf 'viewer:%s\n' "$hash" > /etc/nginx/akimai.htpasswd
chmod 600 /etc/nginx/akimai-ip.key
chown root:www-data /etc/nginx/akimai.htpasswd
chmod 640 /etc/nginx/akimai.htpasswd
install -m 644 /opt/akimai/deploy/nginx-ip.conf /etc/nginx/sites-available/akimai-ip
ln -s /etc/nginx/sites-available/akimai-ip /etc/nginx/sites-enabled/akimai-ip
nginx -t
systemctl reload nginx
printf '\nDEMO_USER=viewer\nDEMO_PASSWORD=%s\n' "$password"
