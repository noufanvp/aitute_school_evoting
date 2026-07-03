# School E-Voting Kiosk (Django)

This project is a supervised school voting kiosk with:

- Django backend + admin
- PostgreSQL-ready database setup
- One staff/operator login
- Anonymous ballots only
- Kiosk flow for one student at a time

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_election
python manage.py runserver
```

Open http://127.0.0.1:8000 and login as operator.

## Final verification checklist

- [ ] Operator can login/logout.
- [ ] Start session works only when election is open.
- [ ] Student can select exactly one candidate per position.
- [ ] Submit succeeds only when all positions are voted.
- [ ] Ballot submit cannot be replayed.
- [ ] Receipt token appears after successful submit.
- [ ] App returns to waiting mode for next voter.
- [ ] Admin can manage election/positions/candidates.
- [ ] Votes are anonymous (no student identity fields).

See [docs/deployment.md](docs/deployment.md) and [docs/security-checklist.md](docs/security-checklist.md).
