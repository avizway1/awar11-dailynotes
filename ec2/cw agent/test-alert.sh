#!/usr/bin/env bash
# Demo: generate real Apache errors so the CloudWatch alarms fire.
# Run on the instance:   sudo ./test-alert.sh

# a page nobody can read  -> 403
echo secret > /var/www/html/secret.html
chmod 755 /var/www/html/secret.html

# a CGI that fails -> 500, and its stderr becomes an ERROR line in error_log
mkdir -p /var/www/cgi-bin
cat > /var/www/cgi-bin/fail.cgi <<'CGI'
#!/bin/bash
echo "ERROR: payment service unavailable" >&2
exit 1
CGI
chmod 755 /var/www/cgi-bin/fail.cgi

echo "generating errors..."
for i in $(seq 1 8);  do curl -s -o /dev/null http://127.0.0.1/cgi-bin/fail.cgi; done
for i in $(seq 1 10); do curl -s -o /dev/null http://127.0.0.1/secret.html; done
for i in $(seq 1 25); do curl -s -o /dev/null http://127.0.0.1/nopage-$i; done

echo
echo "--- error_log ---";  tail -5 /var/log/httpd/error_log
echo
echo "--- access_log ---"; tail -5 /var/log/httpd/access_log
echo
echo "Wait ~2 min, then check CloudWatch > Alarms and your email."
