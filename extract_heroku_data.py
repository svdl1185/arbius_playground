#!/usr/bin/env python3
"""
Helper script to extract data from Heroku PostgreSQL database

To get your Heroku database URL:
1. Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
2. Login to Heroku: heroku login
3. Get your app name (replace 'your-app-name' below)
4. Run: heroku config:get DATABASE_URL --app your-app-name

Usage:
python extract_heroku_data.py --heroku-db-url "postgresql://user:pass@host:port/db"
"""

import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arbius_playground.settings')
django.setup()

from django.core.management import execute_from_command_line

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExample usage:")
        print("python extract_heroku_data.py --heroku-db-url \"postgresql://user:pass@host:port/db\"")
        print("\nOr for dry run (to see what would be imported):")
        print("python extract_heroku_data.py --heroku-db-url \"postgresql://user:pass@host:port/db\" --dry-run")
        sys.exit(1)
    
    # Run the management command
    execute_from_command_line(['extract_heroku_data.py', 'extract_heroku_data'] + sys.argv[1:]) 