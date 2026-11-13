# RentEase: Rental Management Platform

RentEase connects **property owners**, **tenants**, **staff**, and **administrators** in one web app. This is a full-stack Django project: Django serves both the backend and the HTML pages through Django templates. Data is stored in PostgreSQL on Supabase.

> **Current phase: Project Development 1 (Account Feature).**
> Property, application, lease, and maintenance modules come in later phases. They appear as "Soon" in the sidebar.

## Account Feature

| Requirement | How it's done |
|---|---|
| **Registration** | `/register/` collects first and last name, username, email, contact number, account type, and a password with confirmation. Every field is required. Email format is validated. Username and email must be unique (case-insensitive). Passwords must match and pass Django's password validators. |
| **Hashed passwords** | Built on Django's `UserCreationForm` and `set_password()`, so passwords are stored as PBKDF2 hashes and never as plain text. |
| **Login / logout** | `/login/` accepts a username or an email. Invalid credentials show an error message. **Sign out** ends the session (POST request with CSRF protection). |
| **Protected pages** | Dashboards and the profile pages use `@login_required` (directly or through `@role_required`). A logged-out visitor is sent to the login page. |
| **Role-based dashboards** | Four roles: **Admin**, **Property Owner**, **Tenant**, **Staff**. After login, `/dashboard/` sends each user to their own dashboard (`/dashboard/admin/`, `/owner/`, `/tenant/`, `/staff/`), each with its own content and sidebar. Typing another role's dashboard URL sends the user back to their own dashboard with an error message. |
| **Profile** | `/profile/` shows your own details. `/profile/edit/` updates your name, email, contact number, and profile photo. The URL never contains a user ID; the views always use the logged-in user, so nobody can view or edit another person's profile. |
| **Messages** | Success and error messages use Django's messages framework. |

Public registration offers only **Tenant** and **Property Owner**. **Admin** and **Staff** accounts are created by an admin from **Users & Access** (the Django admin at `/django-admin/`).

## Tech Stack

- Python 3 and Django 6
- PostgreSQL (Supabase) through `psycopg`
- Django templates and plain CSS (`static/css/`)
- `python-dotenv` and `dj-database-url` for reading settings from `.env`
- Pillow for profile photo uploads

## Getting Started

### 1. Clone and install

```powershell
git clone https://github.com/Phyyyyyyyyyyyy/rentease-csit327.git
cd rentease-csit327
python -m venv venv
.\venv\Scripts\Activate.ps1        # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Create a Supabase database

1. Create a free project at [supabase.com](https://supabase.com).
2. Click **Connect** at the top of the project dashboard and copy the **Session pooler** connection string (URI).
3. Replace `[YOUR-PASSWORD]` in it with your database password.

### 3. Configure `.env`

Copy `.env.example` to `.env` and fill it in:

```env
SECRET_KEY=<any long random string>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

To generate a secret key, run:
`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

> `.env` is listed in `.gitignore`. Never commit it.

### 4. Migrate, seed, and run

```powershell
python manage.py migrate
python manage.py seed_demo_users     # optional: one demo account per role
python manage.py runserver
```

Open http://127.0.0.1:8000/.

## Demo Accounts

`seed_demo_users` creates these accounts, all with the password `RentEase@2026`:

| Role | Username | Email |
|---|---|---|
| Admin | `admin` | admin@rentease.local |
| Property Owner | `owner` | owner@rentease.local |
| Tenant | `tenant` | tenant@rentease.local |
| Staff | `staff` | staff@rentease.local |

You can also run `python manage.py createsuperuser`. Superusers automatically get the Admin role.

## Tests

```powershell
python manage.py test accounts
```

The tests cover registration validation, password hashing, login and logout, redirects for protected pages, role isolation between dashboards, and profile ownership.

## Project Structure

```
├── config/                 # Django project settings and root URLs
├── accounts/               # Account feature app
│   ├── models.py           # Custom User (role, phone, profile_photo)
│   ├── forms.py            # Registration, login, and profile forms
│   ├── views.py            # Auth, role dashboards, and profile views
│   ├── decorators.py       # @role_required
│   ├── backends.py         # Login with username or email
│   ├── templatetags/       # Icon and sidebar-menu template tags
│   ├── management/commands/seed_demo_users.py
│   └── tests.py
├── templates/              # Base layout, auth pages, dashboards, and profile pages
├── static/css/             # styles.css (ported from the React prototype) and app.css
├── .env.example
└── requirements.txt
```

## Roadmap

- [x] Account Feature: registration, login and logout, role dashboards, profile
- [ ] Property and unit management
- [ ] Rental applications
- [ ] Lease and payment management
- [ ] Tenant portal and maintenance
