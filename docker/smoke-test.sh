#!/bin/sh
set -eu

service_name="${1:-minipbx-bridge}"
web_port="${MINIPBX_SMOKE_WEB_PORT:-18080}"
ami_password="${MINIPBX_SMOKE_AMI_PASSWORD:-smoke-test-ami-secret}"

docker compose --profile bridge run --rm --entrypoint sh "$service_name" -c "
set -eu
log_file=/tmp/minipbx-smoke.log
MINIPBX_WEB_PORT=$web_port MINIPBX_AMI_PASSWORD=$ami_password /entrypoint.sh > \"\$log_file\" 2>&1 &
entrypoint_pid=\$!

cleanup() {
  kill \"\$entrypoint_pid\" 2>/dev/null || true
  wait \"\$entrypoint_pid\" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

sleep 7

ps -eo user,comm,args | grep -E '^[[:space:]]*asterisk[[:space:]]+asterisk[[:space:]]+asterisk -C /etc/asterisk/asterisk.conf -f' >/dev/null
ps -eo user,comm,args | grep -E '^[[:space:]]*asterisk[[:space:]]+uvicorn[[:space:]]+' >/dev/null

uid=\$(id -u asterisk)
gid=\$(id -g asterisk)
setpriv --reuid \"\$uid\" --regid \"\$gid\" --init-groups \
  asterisk -C /etc/asterisk/asterisk.conf -rx 'core show uptime' >> \"\$log_file\" 2>&1

if grep -E 'ERROR|WARNING|Unable|declined|failed|No .*config|Could not' \"\$log_file\"; then
  exit 1
fi

echo 'MiniPBX smoke test OK'
"
