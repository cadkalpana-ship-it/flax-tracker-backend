# Flax Availability Tracker

Tracks Flax items by a unique `flax_id`, with status `AVAILABLE` / `IN_USE`.

## Backend (Django + DRF, SQLite by default)

```
cd flax_backend
python -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver 0.0.0.0:8000
```

API (tested end-to-end):
- `GET    /api/flaxes/`                        list all (supports `?status=AVAILABLE`)
- `POST   /api/flaxes/`                        create `{"flax_id": "FLX-001", "name": "..."}`
- `GET    /api/flaxes/<flax_id>/`               retrieve one
- `PATCH  /api/flaxes/<flax_id>/`               partial update
- `PATCH  /api/flaxes/<flax_id>/set_status/`    body `{"status": "IN_USE"}`
- `PATCH  /api/flaxes/<flax_id>/toggle_status/` flips Available <-> In Use
- `DELETE /api/flaxes/<flax_id>/`               delete
- `/admin/`                                     Django admin UI for the Flax table

To switch from SQLite to Postgres/MySQL: edit `DATABASES` in
`flax_backend/flax_backend/settings.py` — no other code changes needed.

## Frontend (Flutter)

```
cd flax_app
flutter pub get
flutter run
```

Before running, set the correct backend URL in
`lib/services/api_service.dart` (`ApiService.baseUrl`):
- Android emulator → `http://10.0.2.2:8000/api` (already set)
- iOS simulator / web / desktop → `http://127.0.0.1:8000/api`
- Physical device → `http://<your-computer-LAN-IP>:8000/api`

The app lists all flaxes, lets you add one (ID + optional name), and tap
the status chip to toggle Available/In Use — calling `toggle_status` on
the backend and refreshing.
