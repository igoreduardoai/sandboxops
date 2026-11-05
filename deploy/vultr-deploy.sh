#!/usr/bin/env bash
# One-command deploy on a fresh Vultr Cloud Compute Ubuntu 22.04/24.04 VM (run as root):
#   git clone https://github.com/igoreduardoai/sandboxops && cd sandboxops && \
#   VULTR_INFERENCE_API_KEY=xxx bash deploy/vultr-deploy.sh
# Result: app on http://<VM_PUBLIC_IP>/ (port 80), health at /health.
set -euo pipefail
SRC="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update -y
apt-get install -y python3 docker.io ufw
systemctl enable --now docker
docker pull python:3.12-slim
id sandboxops >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin sandboxops
usermod -aG docker sandboxops
mkdir -p /opt/sandboxops
if [ "$SRC" != "/opt/sandboxops" ]; then cp -r "$SRC"/*.py "$SRC"/static /opt/sandboxops/; fi
umask 077
{ echo "VULTR_INFERENCE_API_KEY=${VULTR_INFERENCE_API_KEY:-}"
  echo "VULTR_INFERENCE_MODEL=${VULTR_INFERENCE_MODEL:-glm-5.3}"; } > /etc/sandboxops.env
cp "$SRC/deploy/sandboxops.service" /etc/systemd/system/sandboxops.service
systemctl daemon-reload && systemctl enable --now sandboxops
ufw allow OpenSSH && ufw allow 80/tcp && ufw --force enable
sleep 2; curl -fsS http://127.0.0.1/health && echo
echo "SandboxOps live: http://$(curl -fsS https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')/"
