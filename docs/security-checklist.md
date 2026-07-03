# Security Checklist

- [ ] Staff/admin authentication enabled.
- [ ] Student identities are never stored in ballots.
- [ ] CSRF enabled for all POST endpoints.
- [ ] Session and CSRF cookies secure in production.
- [ ] HTTPS enabled on public domain.
- [ ] DATABASE_URL points to PostgreSQL in production.
- [ ] DJANGO_SECRET_KEY set from environment.
- [ ] Election is opened/closed only from admin panel.
- [ ] Duplicate ballot submit is blocked server-side.
- [ ] Rate limits active for start/save/submit endpoints.
- [ ] Static files collected before go-live.
- [ ] Superuser password rotated before election day.
