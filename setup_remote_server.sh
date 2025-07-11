#!/bin/bash
# Script to set up PostgreSQL on the remote server

echo "Remote Database Setup Helper"
echo "============================"
echo "This script will help you set up PostgreSQL on the remote server: 192.168.0.190"
echo ""
echo "Please run the following commands on the remote server (192.168.0.190):"
echo ""
echo "1. Install PostgreSQL:"
echo "   sudo apt update"
echo "   sudo apt install postgresql postgresql-contrib"
echo ""
echo "2. Start PostgreSQL service:"
echo "   sudo systemctl start postgresql"
echo "   sudo systemctl enable postgresql"
echo ""
echo "3. Configure PostgreSQL for remote connections:"
echo "   sudo -u postgres psql -c \"ALTER USER postgres PASSWORD '<your-password-here>';\""
echo ""
echo "4. Edit PostgreSQL configuration:"
echo "   sudo nano /etc/postgresql/*/main/postgresql.conf"
echo "   # Add or uncomment: listen_addresses = '*'"
echo ""
echo "5. Edit pg_hba.conf for authentication:"
echo "   sudo nano /etc/postgresql/*/main/pg_hba.conf"
echo "   # Add this line: host all all 0.0.0.0/0 md5"
echo ""
echo "6. Restart PostgreSQL:"
echo "   sudo systemctl restart postgresql"
echo ""
echo "7. Check if PostgreSQL is listening:"
echo "   sudo netstat -plntu | grep 5432"
echo ""
echo "Once you've completed these steps on the remote server, run this script again to test the connection."
echo ""

# Test if we can connect now
echo "Testing connection to 192.168.0.190:5432..."
if timeout 5 bash -c "</dev/tcp/192.168.0.190/5432" 2>/dev/null; then
    echo "✓ Port 5432 is open and accessible"
    echo "Now testing PostgreSQL connection..."
    cd /home/rishi/Documents/pykaftestapp
    /home/rishi/Documents/pykaftestapp/.venv/bin/python test_remote_db.py
else
    echo "✗ Port 5432 is not accessible"
    echo "Please ensure PostgreSQL is installed and configured on the remote server."
fi
