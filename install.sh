#!/bin/sh
set -eu

if [ ! -f .env ]; then
  cp .env.example .env
fi

secret="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
ami_password="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"

tmp_file="$(mktemp)"
awk -v secret="$secret" -v ami_password="$ami_password" '
  BEGIN {
    insecure[""] = 1
    insecure["change-me"] = 1
    insecure["change-me-generate-with-install-sh"] = 1
  }
  /^MINIPBX_SECRET_KEY=/ {
    value = substr($0, index($0, "=") + 1)
    if (value in insecure) {
      print "MINIPBX_SECRET_KEY=" secret
    } else {
      print
    }
    found=1
    next
  }
  /^MINIPBX_AMI_PASSWORD=/ {
    value = substr($0, index($0, "=") + 1)
    if (value in insecure) {
      print "MINIPBX_AMI_PASSWORD=" ami_password
    } else {
      print
    }
    ami_found=1
    next
  }
  { print }
  END { if (!found) print "MINIPBX_SECRET_KEY=" secret }
  END { if (!ami_found) print "MINIPBX_AMI_PASSWORD=" ami_password }
' .env > "$tmp_file"
mv "$tmp_file" .env

mkdir -p data

echo "MiniPBX est prepare."
echo "Demarrage recommande sur Linux: docker compose up -d"
echo "Profil bridge de developpement: docker compose --profile bridge up -d minipbx-bridge"
echo "Interface web: http://IP_DU_SERVEUR:8080"
