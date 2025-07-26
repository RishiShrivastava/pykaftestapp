# Use the official OWASP ModSecurity CRS Nginx as base
FROM owasp/modsecurity-crs:nginx

# Copy our custom configuration as a template
COPY nginx-waf.conf /etc/nginx/templates/conf.d/default.conf.template

# The entrypoint script will process this template and place it in the right location
