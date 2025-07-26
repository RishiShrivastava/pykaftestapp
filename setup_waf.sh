#!/bin/bash
set -e

# Wait for services to be ready
sleep 5

# Create a custom proxy_backend.conf file
cat > /tmp/proxy_backend.conf << EOF
proxy_set_header Host \$host;    
proxy_set_header Proxy "";
proxy_set_header Upgrade \$http_upgrade;
proxy_set_header Connection \$connection_upgrade;
proxy_set_header X-REAL-IP \$remote_addr;
proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Port \$server_port;
proxy_set_header X-Forwarded-Proto \$scheme;

proxy_http_version 1.1;
proxy_buffering off;
proxy_connect_timeout 60s;
proxy_read_timeout 36000s;
proxy_redirect off;

proxy_pass_header Authorization;
proxy_pass http://enhanced-extract-service:8000;

set_real_ip_from 127.0.0.1;

real_ip_header X-REAL-IP;
real_ip_recursive on;
EOF

# Start nginx-waf container
docker-compose -f docker-compose.prod.yml up -d nginx-waf

# Wait for container to start
sleep 5

# Copy the custom configuration into the container
docker cp /tmp/proxy_backend.conf nginx_waf:/etc/nginx/includes/proxy_backend.conf

# Restart nginx inside the container
docker exec nginx_waf nginx -s reload

echo "WAF configured with HTTP backend successfully"
