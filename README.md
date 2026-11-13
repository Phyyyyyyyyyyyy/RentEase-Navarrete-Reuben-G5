# RentEase: Rental Management Platform

RentEase connects **property owners**, **tenants**, **staff**, and **administrators** in one web app. Owners list properties, tenants find and apply for rentals, and admins manage who can access what.

| Layer | Technology |
|---|---|
| Backend and frontend | **Django 6**, full stack: views and Django templates |
| Database | **PostgreSQL** hosted on **Supabase** |
| Styling | **Tailwind CSS v4** plus the original RentEase stylesheet |
| Authentication | Django's built-in auth (hashed passwords, sessions) |

> **Current phase: Project Development 1 (Account Feature).**
> Property, application, lease, and maintenance modules come in later phases. They appear as "Soon" in the sidebar.

---

## Account Feature

| Requirement | How it's done |
|---|---|
| **Registration** | `/register/` collects first and last name, username, email, contact number, account type, and a password with confirmation. Every field is required. Email format is validated. Username and email must be unique (case-insensitive). Passwords must match and pass Django's password validators. Success and error messages are shown. |
| **Hashed passwords** | Built on Django's `UserCreationForm` and `set_password()`, so passwords are stored as PBKDF2 hashes (`pbkdf2_sha256$...`) and never as plain text. |
| **Login / logout** | `/login/` accepts a username or an email. Invalid credentials show an error message. A **Sign out** button in the top bar and the sidebar ends the session (POST request with CSRF protection). |
| **Protected pages** | Dashboards and the profile pages use `@login_required` (directly or through `@role_required`). A logged-out visitor is sent to the login page. |
| **Role-based dashboards** | Four roles: **Admin**, **Property Owner**, **Tenant**, **Staff**. After login, each user goes to their own dashboard, with content and sidebar navigation for that role. Typing another role's dashboard URL sends the user back to their own dashboard with an error message. |
| **User profile** | Users view their own details at `/profile/` and update their name, email, contact number, and profile photo at `/profile/edit/`. The URL never contains a user ID, and the views always use the logged-in user, so nobody can view or edit another person's profile. |

Public registration offers only **Tenant** and **Property Owner**. **Admin** and **Staff** accounts are created by an admin from **Users & Access** (the Django admin).

### Pages

| URL | Who can open it | Purpose |
|---|---|---|
| `/register/` | Anyone | Create a Tenant or Property Owner account |
| `/login/` | Anyone | Sign in with username or email |
| `/dashboard/` | Logged in | Redirects to the dashboard for your role |
| `/dashboard/admin/` | Admin | User statistics, recent registrations, admin shortcuts |
| `/dashboard/owner/` | Property Owner | Owner workspace |
| `/dashboard/tenant/` | Tenant | Tenant workspace |
| `/dashboard/staff/` | Staff | Tenant and owner counts, staff workspace |
| `/profile/` | Logged in | View your own profile |
| `/profile/edit/` | Logged in | Edit your own profile and photo |
| `/django-admin/` | Admin | Manage users, roles, and active status |

---

## Getting Started (Windows / PowerShell)

### Prerequisites
- [Python 3](https://www.python.org/downloads/)
- A free [Supabase](https://supabase.com) account
- [Node.js](https://nodejs.org/), needed only if you change styles (see [Styling](#styling-tailwind-css))

### 1. Clone and install

```powershell
git clone https://github.com/Phyyyyyyyyyyyy/rentease-csit327.git
cd rentease-csit327
python -m venv venv
.\venv\Scripts\python -m pip install -r requirements.txt
```

### 2. Get your Supabase connection string

1. Create a project at [supabase.com](https://supabase.com) and write down the **database password**.
2. Click the green **Connect** button at the top of the project dashboard.
3. Choose **Direct** (Connection string), scroll to **Session pooler**, and copy the URI. It looks like this:
   ```
   postgresql://postgres.<project-ref>:[YOUR-PASSWORD]@aws-1-<region>.pooler.supabase.com:5432/postgres
   ```

### 3. Create `.env`

Copy `.env.example` to `.env` and fill it in:

```env
SECRET_KEY=<any long random string>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-1-<region>.pooler.supabase.com:5432/postgres
```

- Replace `[YOUR-PASSWORD]` **including the square brackets** with your real password.
- If the password contains special characters, URL-encode them: `#` → `%23`, `@` → `%40`, `/` → `%2F`, `:` → `%3A`. Alternatively, reset it in Supabase to letters and numbers only.
- To generate a secret key, run:
  `.\venv\Scripts\python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

> 🔒 `.env` holds your database password. It's listed in `.gitignore`. **Never commit it.**

### 4. Create the tables, seed accounts, and run

```powershell
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py seed_demo_users     # optional: one demo account per role
.\venv\Scripts\python manage.py runserver
```

Open **http://127.0.0.1:8000/**. Press `Ctrl+C` in the terminal to stop the server.

Next time, you only need the `runserver` command. The tables and accounts are already stored in Supabase.

> **Tip:** you can activate the virtual environment with `.\venv\Scripts\Activate.ps1` and then type just `python manage.py ...`. The prompt shows `(venv)` when it's active.

---

## Demo Accounts

`seed_demo_users` creates these accounts, all with the password **`RentEase@2026`**:

| Role | Username | Email |
|---|---|---|
| Admin | `admin` | admin@rentease.local |
| Property Owner | `owner` | owner@rentease.local |
| Tenant | `tenant` | tenant@rentease.local |
| Staff | `staff` | staff@rentease.local |

You can also run `python manage.py createsuperuser`. Superusers automatically get the Admin role.

---

## Checking That It Uses Supabase

**In Supabase:** open **Table Editor** → `accounts_user`. The accounts appear there, and the `password` column contains only `pbkdf2_sha256$...` hashes. Register a new user in the app, refresh the table, and the new row appears.

**From the terminal:**
```powershell
.\venv\Scripts\python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['HOST'])"
```
This should print `postgresql aws-1-<region>.pooler.supabase.com`.

---

## Styling (Tailwind CSS)

The site uses one stylesheet, `static/css/main.css`. It's **generated** from `static_src/` by the Tailwind CLI and committed, so the app runs without Node. To change styles:

```powershell
npm install          # one time
npm run tw:watch     # leave running in a second terminal next to runserver
```

- Use Tailwind classes directly in templates, for example `class="rounded-xl bg-brand px-4 py-2 text-white"`.
- Custom brand colors are `brand`, `brand-dark`, `navy`, and `line`. They're defined in `static_src/tailwind.css`.
- The original RentEase styles are in `static_src/legacy/`. They're in a lower CSS layer, so Tailwind classes win when both apply to the same element.
- Example component: `templates/accounts/dashboards/_account_panel.html` is built entirely with Tailwind.
- Before committing, run `npm run tw:build` to produce the minified `main.css`. Don't edit `main.css` by hand.

---

## Tests

```powershell
.\venv\Scripts\python manage.py test accounts
```

The 16 tests cover registration validation (required fields, email format, duplicates, password mismatch, role restriction), password hashing, login with username or email, invalid credentials, logout, login-required redirects, role isolation between dashboards, and profile ownership.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'dj_database_url'` (or `django`) | You're using the global Python instead of the venv. Run commands as `.\venv\Scripts\python manage.py ...`, or activate the venv first. |
| `running scripts is disabled on this system` when activating | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or skip activation and use `.\venv\Scripts\python`. |
| `Missing environment variable DATABASE_URL` | `.env` is missing or empty. See [step 3](#3-create-env). |
| `This string is not a valid url` | The password in `DATABASE_URL` still has `[ ]` around it or contains unencoded special characters such as `#`. See [step 3](#3-create-env). |
| Connection timeout | Use the **Session pooler** string, not "Direct connection" (which needs IPv6). |
| Styles look outdated | Hard-refresh with `Ctrl+F5`. If you edited templates with new Tailwind classes, run `npm run tw:build`. |

---

## Project Structure

```
├── config/                 # Django settings (reads .env) and root URLs
├── accounts/               # Account feature app
│   ├── models.py           # Custom User: role, phone, profile_photo
│   ├── forms.py            # Registration, login, and profile forms
│   ├── views.py            # Auth, role dashboards, and profile views
│   ├── decorators.py       # @role_required
│   ├── backends.py         # Log in with username or email
│   ├── templatetags/       # Icon and sidebar-menu template tags
│   ├── management/commands/seed_demo_users.py
│   └── tests.py
├── templates/              # Base layout, auth pages, dashboards, and profile pages
├── static_src/             # Tailwind source (tailwind.css) and original styles (legacy/)
├── static/css/main.css     # Generated stylesheet (npm run tw:build)
├── package.json            # Tailwind CLI scripts (build tooling only)
├── .env.example            # Template for your local .env
└── requirements.txt        # Python dependencies
```

---

## Roadmap

- [x] **Project Development 1:** Account Feature (registration, login and logout, role dashboards, profile)
- [ ] Property and unit management
- [ ] Rental applications
- [ ] Lease and payment management
- [ ] Tenant portal and maintenance
