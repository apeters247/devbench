#!/bin/bash
# Devbench nginx setup for naxiai.com
# Run: bash /var/www/devbench/scripts/deploy_nginx.sh

set -e

echo "=== Devbench nginx deployment ==="

# 1. Copy the nginx config with Devbench location blocks
echo "→ Installing nginx config..."
sudo cp /tmp/naxiai_nginx_new.conf /etc/nginx/sites-available/naxiai.com

# 2. Test the config
echo "→ Testing nginx config..."
sudo nginx -t

# 3. Reload nginx
echo "→ Reloading nginx..."
sudo systemctl reload nginx

# 4. Verify
echo "→ Verifying..."
curl -s -o /dev/null -w "HTTP %{http_code}" https://naxiai.com/tools/devbench/
echo ""
echo "✅ Devbench landing page should be live at https://naxiai.com/tools/devbench/"