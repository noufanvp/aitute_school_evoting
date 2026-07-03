# Deployment Guide (Django + PostgreSQL)

## 1) Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Run migrations and create operator account:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_election
```

Run server:

```bash
python manage.py runserver
```

## 2) Production environment variables

Set these in your host panel:

- DJANGO_ENV=prod
- DJANGO_SECRET_KEY=<strong-random-value>
- DJANGO_DEBUG=0
- DJANGO_ALLOWED_HOSTS=<your-domain>,<your-hostname>
- DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-domain>
- DATABASE_URL=postgres://<user>:<password>@<host>:<port>/<db>
- DATABASE_SSL_REQUIRE=1

## 3) Deploy steps

1. Provision PostgreSQL.
2. Configure environment variables.
3. Deploy application code.
4. Run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py seed_election
```

5. Start with Gunicorn:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

## 4) HTTPS and domain checklist

- Map domain to app.
- Enable TLS certificate.
- Keep SECURE_SSL_REDIRECT enabled (prod settings).
- Add domain to ALLOWED_HOSTS and CSRF trusted origins.

## 5) Kiosk day operations

1. Staff logs in once on kiosk.
2. Staff manually verifies student offline.
3. Staff clicks `Start New Voter Session`.
4. Student votes and submits.
5. Receipt is displayed.
6. App auto-resets for next student.
