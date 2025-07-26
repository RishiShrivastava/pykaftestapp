#!/bin/bash
# verify-https.sh
# Created by Rishi on July 27, 2025
# Script to verify HTTPS-only access to the application

echo "Testing direct HTTP access (should redirect to HTTPS)..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -L http://localhost/health)
echo "HTTP Response Code: $HTTP_RESPONSE"

echo ""
echo "Testing HTTPS access..."
HTTPS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -k https://localhost/health)
echo "HTTPS Response Code: $HTTPS_RESPONSE"

echo ""
echo "Testing direct access to extract service (should fail)..."
DIRECT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>&1 || echo "Connection refused")
echo "Direct Access Response: $DIRECT_RESPONSE"

echo ""
echo "Summary:"
if [ "$HTTPS_RESPONSE" == "200" ]; then
    echo "✅ HTTPS access is working properly"
else
    echo "❌ HTTPS access is not working"
fi

if [ "$HTTP_RESPONSE" == "301" ] || [ "$HTTP_RESPONSE" == "302" ]; then
    echo "✅ HTTP access redirects to HTTPS"
elif [ "$HTTP_RESPONSE" == "200" ]; then
    echo "⚠️ HTTP access works but doesn't redirect to HTTPS"
else
    echo "❌ HTTP access is not working properly"
fi

if [[ "$DIRECT_RESPONSE" == *"Connection refused"* ]]; then
    echo "✅ Direct access to extract service is blocked (good!)"
else
    echo "❌ Direct access to extract service is still possible (security issue!)"
fi
