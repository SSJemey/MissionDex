# MissionDex

MissionDex is a web application for tracking and managing space missions, astronauts, payloads, launch sites, agencies, and related events. It provides CRUD-style admin pages, mission dashboards, user authentication, bookmarking, and analytics pages for mission statistics.

**Key Features**
- **User accounts & auth:** register, login, role-based access (admin vs user).
- **Mission management:** create, view, and list missions with details, launch dates and associated entities.
- **Entities:** manage agencies, spacecraft, payloads, launch sites, events, and astronauts.
- **Assignments:** link agencies, spacecraft, payloads, crew and launch sites to missions.
- **Bookmarks & dashboard:** users can bookmark missions and view a personalized dashboard.
- **Analytics:** mission statistics and reports (success rates, top astronauts, launch site usage).

**Used Tech**
- `Frontend`: HTML, CSS and Jinja2 templates (templates/ and static/)
- `Backend`: Python 3.8+, Flask, Werkzeug
- `Database`: MySQL (accessed via `mysql-connector-python`)
- `Environment`: `python-dotenv` for loading `.env` variables
- `Optional / Deployment`: Docker and `docker-compose`

**Repository layout (key files)**
- `app.py` - Flask application and routes
- `requirements.txt` - pinned Python dependencies
- `database/schema.sql` - database schema and table definitions
- `templates/` - Jinja2 HTML templates
- `static/` - CSS and static assets
- `Dockerfile`, `docker-compose.yml` - containerization

Getting started (local, recommended)
1. Clone the repository:

```powershell
git clone https://github.com/SSJemey/MissionDex.git
cd MissionDex
```

2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Create a `.env` file in the project root and set environment variables (DO NOT commit this file):

```
FLASK_SECRET_KEY=your_secure_secret_here
DB_HOST=localhost
DB_USER=your_db_user
DB_PASS=your_db_password
DB_NAME=missiondex
```

5. Create the database and tables (MySQL):

```powershell
mysql -u root -p < database/schema.sql
```

6. Run the app (development):

```powershell
python app.py
```

The app will be available at `http://127.0.0.1:5000` by default.

Running with Docker (alternative)

```powershell
docker-compose up --build
```

Notes & best practices
- Keep `.env` out of version control; add it to `.gitignore`.
- Use a strong `FLASK_SECRET_KEY` in production — do not rely on development fallbacks.
- Secure your database (do not use root in production) and configure appropriate user privileges.
- If you want help trimming `requirements.txt` to only used packages, I can analyze imports and produce a minimized file.

License
- No license specified for this repository.

Contributions
- Frontend (HTML/CSS and template work): `SSJemey`
- Backend, database schema and Python code: `MusannaMohian`

If you'd like to contribute, please open an issue or submit a pull request describing your changes.

Enjoy exploring and extending MissionDex!
