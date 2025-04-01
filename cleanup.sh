#!/bin/bash

echo "Stopping all servers..."
pkill -f daphne
pkill -f run_forex_generator
pkill -f run_thinkorswim_generator

echo "Removing database..."
rm db.sqlite3

echo "Removing migration files..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc" -delete

echo "Making fresh migrations..."
python manage.py makemigrations forex
python manage.py makemigrations thinkorswim

echo "Applying migrations..."
python manage.py migrate

echo "Creating superuser..."
python manage.py createsuperuser

echo "Cleanup complete! You can now start the servers." 