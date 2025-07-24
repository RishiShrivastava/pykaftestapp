# SSL Certificates for NGINX WAF

Place your SSL certificate and private key here:
- cert.pem  (public certificate)
- key.pem   (private key)

For testing, you can generate a self-signed certificate with:

openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem -subj "/CN=localhost"

In production, use certificates from a trusted CA.
