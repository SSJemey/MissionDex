from flask import Flask, abort, redirect, render_template, request, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os

# load environment variables from a .env file
load_dotenv()

app = Flask(__name__)
# use FLASK_SECRET_KEY if set, otherwise fallback to a secure random key for development
app.secret_key = os.getenv("FLASK_SECRET_KEY") or os.urandom(24)

def connect_db():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME")
        )
        print(">>> Database connection successful!")
        return connection
    except mysql.connector.Error as err:
        print(f">>> Error connecting to database: {err}")
        return None

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        conn = connect_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user :
            if check_password_hash(user['password_hash'], password):
                print("✅ Login successful for:", user['username'])
                session['user_id'] = user['user_id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                if user['role'] == 'admin':
                    return redirect(url_for("admin_panel"))
                else:
                    return redirect(url_for("dashboard"))

            else:
                print("❌ Password incorrect for:", user['username'])
                return "🔒 Incorrect password."
        else:
            print("❌ No user found with that username.")
            return "🔒 User not found."

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        role = "user"

        hashed_pw = generate_password_hash(password)

        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return "❌ Username already taken."

        cursor.execute("""
            INSERT INTO Users (username, password_hash, role)
            VALUES (%s, %s, %s)
        """, (username, hashed_pw, role))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))
    
    return render_template("register.html")

@app.route('/dashboard')
def dashboard():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)

    # Quick stats
    cur.execute("SELECT COUNT(*) AS total_bookmarks FROM bookmarks WHERE user_id=%s", (session['user_id'],))
    total_bookmarks = cur.fetchone()['total_bookmarks']

    # Bookmarked missions
    cur.execute("""
      SELECT m.mission_id, m.mission_name, m.status
      FROM bookmarks b
      JOIN missions m ON b.mission_id = m.mission_id
      WHERE b.user_id = %s
      ORDER BY m.launch_date DESC
    """, (session['user_id'],))
    bookmarks = cur.fetchall()

    cur.close(); conn.close()

    stats = {
      'total_bookmarks': total_bookmarks,
    }

    return render_template(
      'dashboard.html',
      stats=stats,
      bookmarks=bookmarks
    )


@app.route("/admin")
def admin_panel():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if session.get("role") != "admin":
        return "⛔ Access denied. Admins only."
    return render_template("admin.html", username=session["username"])

@app.route("/admin_users")
def admin_users():
    if "user_id" not in session or session.get("role") != "admin":
        return "⛔ Access denied."

    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, username, role FROM Users ORDER BY user_id")
    users = cursor.fetchall()
    conn.close()

    return render_template("admin_users.html", users=users)

@app.route('/missions')
def view_missions():
    mission_type = request.args.get('type')
    status = request.args.get('status')
    destination = request.args.get('destination')

    query = "SELECT mission_id, mission_name, mission_type, destination, launch_date, status FROM missions WHERE 1=1"
    params = []

    if mission_type:
        query += " AND mission_type = %s"
        params.append(mission_type)
    if status:
        query += " AND status = %s"
        params.append(status)
    if destination:
        query += " AND destination = %s"
        params.append(destination)

    query += " ORDER BY launch_date DESC"

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, tuple(params))
    missions = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('missions.html', missions=missions)

# Enhance Mission Detail Route
@app.route('/missions/<int:mission_id>')
def mission_detail(mission_id):
    if 'user_id' not in session:
        return redirect('/login')

    # 1. Open DB connection
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    # 2. Fetch base mission record
    cur.execute(
        "SELECT * FROM missions WHERE mission_id = %s",
        (mission_id,)
    )
    mission = cur.fetchone()

    # 3. Fetch participating agencies
    cur.execute("""
        SELECT a.agency_id, a.name, a.country
        FROM mission_agencies ma
        JOIN agencies a ON ma.agency_id = a.agency_id
        WHERE ma.mission_id = %s
    """, (mission_id,))
    agencies = cur.fetchall()

    # 4. Fetch spacecraft used
    cur.execute("""
        SELECT s.spacecraft_id, s.name, s.type
        FROM mission_spacecraft ms
        JOIN spacecraft s ON ms.spacecraft_id = s.spacecraft_id
        WHERE ms.mission_id = %s
    """, (mission_id,))
    crafts = cur.fetchall()

    # 5. Fetch payloads on this mission
    cur.execute("""
        SELECT p.payload_id, p.name, p.type, p.weight_kg
        FROM mission_payloads mp
        JOIN payloads p ON mp.payload_id = p.payload_id
        WHERE mp.mission_id = %s
    """, (mission_id,))
    payloads = cur.fetchall()

    # Events
    cur.execute("""
      SELECT e.event_id, e.name, e.category, e.date
      FROM mission_events me
      JOIN events e ON me.event_id=e.event_id
      WHERE me.mission_id=%s
      ORDER BY e.date DESC
    """, (mission_id,))
    events = cur.fetchall()

    # launch sites
    cur.execute("""
      SELECT ls.launchsite_id, ls.name, ls.country
      FROM mission_launchsites ml
      JOIN launchsites ls ON ml.launchsite_id=ls.launchsite_id
      WHERE ml.mission_id=%s
    """, (mission_id,))
    launchsites = cur.fetchall()

    # 6. Clean up and render
    cur.close()
    conn.close()

    return render_template(
        'mission_detail.html',
        mission=mission,
        agencies=agencies,
        crafts=crafts,
        payloads=payloads,
        events=events,
        launchsites=launchsites
    )


@app.route('/admin/add_mission', methods=['GET', 'POST'])
def add_mission():
    if session.get('role') != 'admin':
        return redirect('/login')  # Protect route

    conn = connect_db()
    cur = conn.cursor()

    if request.method == 'POST':
        mission_name = request.form['mission_name']
        mission_type = request.form['mission_type']
        destination = request.form['destination']
        launch_date = request.form['launch_date']
        duration = request.form['duration']
        status = request.form['status']
        description = request.form['description']

        cur.execute("""
            INSERT INTO missions (mission_name, mission_type, destination, launch_date, duration, status, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (mission_name, mission_type, destination, launch_date, duration, status, description))
        conn.commit()

        return redirect('/missions')  # After successful insert

    cur.close()
    conn.close()
    return render_template('admin_add_mission.html')

@app.route('/bookmark/<int:mission_id>', methods=['POST'])
def bookmark_mission(mission_id):
    if 'user_id' not in session:
        return redirect('/login')

    user_id = session['user_id']
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM bookmarks WHERE user_id=%s AND mission_id=%s", (user_id, mission_id))
    if not cur.fetchone():
        cur.execute("INSERT INTO bookmarks (user_id, mission_id) VALUES (%s, %s)", (user_id, mission_id))
        conn.commit()
    cur.close()
    conn.close()
    return redirect('/missions')

@app.route('/mission_stats')
def mission_stats():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)

    # 1. Average Astronaut Participation
    cur.execute("""
        SELECT ROUND(AVG(count)) AS avg_astronauts
        FROM (
            SELECT COUNT(*) AS count
            FROM missioncrew
            GROUP BY mission_id
        ) AS counts
    """)
    avg_astronauts = cur.fetchone()['avg_astronauts']

    # 2. Spacecraft Success Rate
    cur.execute("""
        SELECT s.name,
               ROUND(SUM(m.status='Completed') / COUNT(*) * 100, 2) AS success_rate
        FROM mission_spacecraft ms
        JOIN spacecraft s ON ms.spacecraft_id = s.spacecraft_id
        JOIN missions m ON ms.mission_id = m.mission_id
        GROUP BY s.spacecraft_id
    """)
    spacecraft_stats = cur.fetchall()

    # 3. Monthly Mission Count per Agency
    cur.execute("""
        SELECT a.name AS agency, MONTH(m.launch_date) AS month,
               COUNT(*) AS mission_count
        FROM mission_agencies ma
        JOIN agencies a ON ma.agency_id = a.agency_id
        JOIN missions m ON ma.mission_id = m.mission_id
        GROUP BY a.agency_id, MONTH(m.launch_date)
    """)
    agency_mission_monthly = cur.fetchall()

    # 4. Astronaut Mission Success
    cur.execute("""
        SELECT ac.full_name, m.mission_name,
               COUNT(*) AS total_missions,
               SUM(m.status='Completed') AS successful
        FROM missioncrew mc
        JOIN astronauts ac ON mc.astronaut_id = ac.astronaut_id
        JOIN missions m ON mc.mission_id = m.mission_id
        GROUP BY ac.astronaut_id, m.mission_id
    """)
    astronaut_performance = cur.fetchall()

    # 5. Launch Site Popularity
    cur.execute("""
        SELECT l.name, COUNT(*) AS launch_count
        FROM mission_launchsites ml
        JOIN launchsites l ON ml.launchsite_id = l.launchsite_id
        GROUP BY l.launchsite_id
        ORDER BY launch_count DESC
    """)
    launchsite_usage = cur.fetchall()

    # 6. Payloads per Agency
    cur.execute("""
        SELECT a.name AS agency, COUNT(p.payload_id) AS payloads_launched
        FROM mission_payloads mp
        JOIN payloads p ON mp.payload_id = p.payload_id
        JOIN mission_agencies ma ON mp.mission_id = ma.mission_id
        JOIN agencies a ON ma.agency_id = a.agency_id
        GROUP BY a.agency_id
    """)
    payloads_by_agency = cur.fetchall()

    # 7. Mission Event Success by Spacecraft
    cur.execute("""
        SELECT s.name,
               ROUND(SUM(e.category IN ('Docking','Landing','Launch')) / COUNT(*) * 100, 2) AS event_success_rate
        FROM mission_events me
        JOIN events e ON me.event_id = e.event_id
        JOIN mission_spacecraft ms ON me.mission_id = ms.mission_id
        JOIN spacecraft s ON ms.spacecraft_id = s.spacecraft_id
        GROUP BY s.spacecraft_id
    """)
    event_success_by_spacecraft = cur.fetchall()

    # 8. Most Active Astronauts by Duration
    cur.execute("""
        SELECT a.full_name,
               SUM(m.duration) AS total_duration
        FROM missioncrew mc
        JOIN astronauts a ON mc.astronaut_id = a.astronaut_id
        JOIN missions m ON mc.mission_id = m.mission_id
        GROUP BY a.astronaut_id
        ORDER BY total_duration DESC
        LIMIT 10
    """)
    active_astronauts_by_duration = cur.fetchall()

    # 9. Payload-Mission Efficiency by Spacecraft
    cur.execute("""
        SELECT s.name,
               ROUND(AVG(CASE WHEN m.status='Completed' THEN 1 ELSE 0 END) * 100, 2) AS success_rate
        FROM missions m
        JOIN mission_spacecraft ms ON m.mission_id = ms.mission_id
        JOIN spacecraft s ON ms.spacecraft_id = s.spacecraft_id
        JOIN mission_payloads mp ON m.mission_id = mp.mission_id
        GROUP BY s.spacecraft_id
    """)
    efficiency_by_payload_spacecraft = cur.fetchall()

    # 10. Top Astronauts in Year
    year = 2023  # or make it dynamic with query param
    cur.execute("""
        SELECT a.full_name, COUNT(*) AS mission_count
        FROM missioncrew mc
        JOIN astronauts a ON mc.astronaut_id = a.astronaut_id
        JOIN missions m ON mc.mission_id = m.mission_id
        WHERE YEAR(m.launch_date) = %s
        GROUP BY a.astronaut_id
        ORDER BY mission_count DESC
        LIMIT 5
    """, (year,))
    top_astronauts_year = cur.fetchall()

    cur.close(); conn.close()
    return render_template('mission_stats.html',
        avg_astronauts=avg_astronauts,
        spacecraft_stats=spacecraft_stats,
        agency_mission_monthly=agency_mission_monthly,
        astronaut_performance=astronaut_performance,
        launchsite_usage=launchsite_usage,
        payloads_by_agency=payloads_by_agency,
        event_success_by_spacecraft=event_success_by_spacecraft,
        active_astronauts_by_duration=active_astronauts_by_duration,
        efficiency_by_payload_spacecraft=efficiency_by_payload_spacecraft,
        top_astronauts_year=top_astronauts_year
    )

@app.route('/astronauts')
def view_astronauts():
    if 'user_id' not in session:
        return redirect('/login')

    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM astronauts")
    astronauts = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('astronauts.html', astronauts=astronauts)

@app.route('/astronaut/<int:astronaut_id>')
def astronaut_profile(astronaut_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    # 1. Core astronaut data
    cur.execute("""
      SELECT *
      FROM astronauts
      WHERE astronaut_id = %s
    """, (astronaut_id,))
    astronaut = cur.fetchone()

    # 2. Summary stats: total missions, successful missions, success rate
    cur.execute("""
      SELECT
        COUNT(*)                  AS total_missions,
        SUM(m.status = 'Completed') AS successful_missions,
        IF(COUNT(*) > 0,
           ROUND(SUM(m.status = 'Completed')/COUNT(*)*100,2),
           0
        )                          AS success_rate
      FROM missioncrew mc
      JOIN missions m ON mc.mission_id = m.mission_id
      WHERE mc.astronaut_id = %s
    """, (astronaut_id,))
    stats = cur.fetchone()

    # 3. Detailed mission history
    cur.execute("""
      SELECT
        m.mission_id,
        m.mission_name,
        m.launch_date,
        m.destination,
        m.duration,
        m.status,
        mc.role,
        GROUP_CONCAT(DISTINCT s.name ORDER BY s.name SEPARATOR ', ')
          AS spacecraft_list
      FROM missioncrew mc
      JOIN missions m ON mc.mission_id = m.mission_id
      LEFT JOIN mission_spacecraft ms
        ON m.mission_id = ms.mission_id
      LEFT JOIN spacecraft s
        ON ms.spacecraft_id = s.spacecraft_id
      WHERE mc.astronaut_id = %s
      GROUP BY m.mission_id
      ORDER BY m.launch_date DESC
    """, (astronaut_id,))
    missions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
      'astronaut_profile.html',
      astronaut=astronaut,
      stats=stats,
      missions=missions
    )

@app.route('/admin/add_astronaut', methods=['GET', 'POST'])
def add_astronaut():
    if 'role' not in session or session['role'] != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        data = (
            request.form['full_name'],
            request.form['rank'],
            request.form['nationality'],
            request.form['specialty'],
            request.form['total_flight_hr'],
            bool(int(request.form['active_status']))
        )
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO astronauts (full_name, rank, nationality, specialty, total_flight_hr, active_status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, data)
        conn.commit()
        cur.close()
        conn.close()
        return redirect('/astronauts')
    return render_template('add_astronaut.html')

@app.route('/admin/assign_crew', methods=['GET','POST'])
def assign_crew():
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mission_id   = request.form['mission_id']
        astronaut_id = request.form['astronaut_id']
        role         = request.form['role']

        # prevent duplicate assignments
        cur.execute("""
          SELECT 1 FROM missioncrew
           WHERE mission_id=%s AND astronaut_id=%s
        """, (mission_id, astronaut_id))
        if not cur.fetchone():
            cur.execute("""
              INSERT INTO missioncrew (mission_id,astronaut_id,role)
              VALUES (%s,%s,%s)
            """, (mission_id, astronaut_id, role))
            conn.commit()

        cur.close(); conn.close()
        return redirect(f'/missions/{mission_id}')

    # GET: fetch missions + astronauts for dropdowns
    cur.execute("SELECT mission_id, mission_name FROM missions ORDER BY launch_date DESC")
    missions = cur.fetchall()

    cur.execute("SELECT astronaut_id, full_name FROM astronauts ORDER BY full_name")
    astronauts = cur.fetchall()

    cur.close(); conn.close()
    return render_template(
      'assign_crew.html',
      missions=missions,
      astronauts=astronauts
    )

# View all agencies
@app.route('/agencies')
def view_agencies():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM agencies ORDER BY name")
    agencies = cur.fetchall()
    cur.close(); conn.close()
    return render_template('agencies.html', agencies=agencies)

# Agency profile + its missions
@app.route('/agency/<int:agency_id>')
def agency_profile(agency_id):
    if 'user_id' not in session:
        return redirect('/login')
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM agencies WHERE agency_id=%s", (agency_id,))
    agency = cur.fetchone()
    cur.execute("""
      SELECT m.* 
      FROM mission_agencies ma
      JOIN missions m ON ma.mission_id=m.mission_id
      WHERE ma.agency_id=%s
      ORDER BY m.launch_date DESC
    """, (agency_id,))
    missions = cur.fetchall()
    cur.close(); conn.close()
    return render_template('agency_profile.html',
                           agency=agency,
                           missions=missions)

# View all spacecraft
@app.route('/spacecraft')
def view_spacecraft():
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM spacecraft ORDER BY name")
    crafts = cur.fetchall()
    cur.close(); conn.close()
    return render_template('spacecraft.html', crafts=crafts)

# Spacecraft profile + its missions
@app.route('/spacecraft/<int:spacecraft_id>')
def spacecraft_profile(spacecraft_id):
    if 'user_id' not in session:
        return redirect('/login')
    conn = connect_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM spacecraft WHERE spacecraft_id=%s",
                (spacecraft_id,))
    craft = cur.fetchone()
    cur.execute("""
      SELECT m.* 
      FROM mission_spacecraft ms
      JOIN missions m ON ms.mission_id=m.mission_id
      WHERE ms.spacecraft_id=%s
      ORDER BY m.launch_date DESC
    """, (spacecraft_id,))
    missions = cur.fetchall()
    cur.close(); conn.close()
    return render_template('spacecraft_profile.html',
                           craft=craft,
                           missions=missions)

# Add Agency (admin only)
@app.route('/admin/add_agency', methods=['GET', 'POST'])
def add_agency():
    if session.get('role') != 'admin':
        return redirect('/login')
    if request.method == 'POST':
        data = (
            request.form['name'],
            request.form['country'],
            request.form['founded_year'],
            request.form['headquarters'],
            request.form['type']
        )
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO agencies
              (name, country, founded_year, headquarters, type)
            VALUES (%s, %s, %s, %s, %s)
        """, data)
        conn.commit()
        cur.close(); conn.close()
        return redirect('/agencies')
    return render_template('add_agency.html')


# Add Spacecraft (admin only)
@app.route('/admin/add_spacecraft', methods=['GET', 'POST'])
def add_spacecraft():
    if session.get('role') != 'admin':
        return redirect('/login')
    if request.method == 'POST':
        data = (
            request.form['name'],
            request.form['type'],
            request.form['manufacturer'],
            request.form['first_flight'],
            request.form['capacity']
        )
        conn = connect_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO spacecraft
              (name, type, manufacturer, first_flight, capacity)
            VALUES (%s, %s, %s, %s, %s)
        """, data)
        conn.commit()
        cur.close(); conn.close()
        return redirect('/spacecraft')
    return render_template('add_spacecraft.html')

# 1. Assign Agency to Mission
@app.route('/admin/assign_agency', methods=['GET', 'POST'])
def assign_agency():
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mission_id = request.form['mission_id']
        agency_id  = request.form['agency_id']
        # prevent duplicates
        cur.execute("""
            SELECT 1 FROM mission_agencies
             WHERE mission_id=%s AND agency_id=%s
        """, (mission_id, agency_id))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO mission_agencies (mission_id, agency_id)
                 VALUES (%s, %s)
            """, (mission_id, agency_id))
            conn.commit()
        return redirect('/admin')

    # GET: fetch lists for dropdowns
    cur.execute("SELECT mission_id, mission_name FROM missions ORDER BY mission_name")
    missions = cur.fetchall()
    cur.execute("SELECT agency_id, name FROM agencies ORDER BY name")
    agencies = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
      'assign_agency.html',
      missions=missions,
      agencies=agencies
    )


# 2. Assign Spacecraft to Mission
@app.route('/admin/assign_spacecraft', methods=['GET', 'POST'])
def assign_spacecraft():
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mission_id     = request.form['mission_id']
        spacecraft_id  = request.form['spacecraft_id']
        # prevent duplicates
        cur.execute("""
            SELECT 1 FROM mission_spacecraft
             WHERE mission_id=%s AND spacecraft_id=%s
        """, (mission_id, spacecraft_id))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO mission_spacecraft (mission_id, spacecraft_id)
                 VALUES (%s, %s)
            """, (mission_id, spacecraft_id))
            conn.commit()
        return redirect('/admin')

    # GET: fetch lists for dropdowns
    cur.execute("SELECT mission_id, mission_name FROM missions ORDER BY mission_name")
    missions   = cur.fetchall()
    cur.execute("SELECT spacecraft_id, name FROM spacecraft ORDER BY name")
    crafts     = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
      'assign_spacecraft.html',
      missions=missions,
      crafts=crafts
    )

# View all payloads
@app.route('/payloads')
def view_payloads():
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM payloads ORDER BY name")
    payloads = cur.fetchall()
    cur.close(); conn.close()
    return render_template('payloads.html', payloads=payloads)

# Payload profile + linked missions
@app.route('/payload/<int:payload_id>')
def payload_profile(payload_id):
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM payloads WHERE payload_id=%s", (payload_id,))
    payload = cur.fetchone()
    cur.execute("""
      SELECT m.mission_id, m.mission_name, m.launch_date, m.status
      FROM mission_payloads mp
      JOIN missions m ON mp.mission_id=m.mission_id
      WHERE mp.payload_id=%s
      ORDER BY m.launch_date DESC
    """, (payload_id,))
    missions = cur.fetchall()
    cur.close(); conn.close()
    return render_template(
      'payload_profile.html',
      payload=payload,
      missions=missions
    )

# Admin: Add new payload
@app.route('/admin/add_payload', methods=['GET','POST'])
def add_payload():
    if session.get('role') != 'admin':
        return redirect('/login')
    if request.method == 'POST':
        data = (
          request.form['name'],
          request.form['type'],
          request.form['weight_kg'],
          request.form['manufacturer'],
          request.form['description']
        )
        conn = connect_db()
        cur  = conn.cursor()
        cur.execute("""
          INSERT INTO payloads (name,type,weight_kg,manufacturer,description)
          VALUES (%s,%s,%s,%s,%s)
        """, data)
        conn.commit()
        cur.close(); conn.close()
        return redirect('/payloads')
    return render_template('add_payload.html')

# Admin: Assign payload to mission
@app.route('/admin/assign_payload', methods=['GET','POST'])
def assign_payload():
    if session.get('role') != 'admin':
        return redirect('/login')
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mission_id = request.form['mission_id']
        payload_id = request.form['payload_id']
        # prevent duplicate
        cur.execute("""
          SELECT 1 FROM mission_payloads
           WHERE mission_id=%s AND payload_id=%s
        """, (mission_id, payload_id))
        if not cur.fetchone():
            cur.execute("""
              INSERT INTO mission_payloads (mission_id,payload_id)
              VALUES (%s,%s)
            """, (mission_id, payload_id))
            conn.commit()
        cur.close(); conn.close()
        return redirect('/admin')

    # GET: fetch missions + payloads for dropdowns
    cur.execute("SELECT mission_id, mission_name FROM missions ORDER BY mission_name")
    missions = cur.fetchall()
    cur.execute("SELECT payload_id, name FROM payloads ORDER BY name")
    payloads = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
      'assign_payload.html',
      missions=missions,
      payloads=payloads
    )

# 2.1 View all events
@app.route('/events')
def view_events():
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM events ORDER BY date DESC")
    events = cur.fetchall()
    cur.close(); conn.close()
    return render_template('events.html', events=events)

# 2.2 Event profile + linked missions
@app.route('/event/<int:event_id>')
def event_profile(event_id):
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM events WHERE event_id=%s", (event_id,))
    event = cur.fetchone()
    cur.execute("""
      SELECT m.mission_id, m.mission_name, m.launch_date, m.status
      FROM mission_events me
      JOIN missions m ON me.mission_id=m.mission_id
      WHERE me.event_id=%s
      ORDER BY m.launch_date DESC
    """, (event_id,))
    missions = cur.fetchall()
    cur.close(); conn.close()
    return render_template(
      'event_profile.html',
      event=event,
      missions=missions
    )

# 2.3 Admin: Add new event
@app.route('/admin/add_event', methods=['GET','POST'])
def add_event():
    if session.get('role') != 'admin':
        return redirect('/login')
    if request.method == 'POST':
        data = (
          request.form['name'],
          request.form['category'],
          request.form['date'],
          request.form['location'],
          request.form['description']
        )
        conn = connect_db()
        cur  = conn.cursor()
        cur.execute("""
          INSERT INTO events
            (name, category, date, location, description)
          VALUES (%s,%s,%s,%s,%s)
        """, data)
        conn.commit()
        cur.close(); conn.close()
        return redirect('/events')
    return render_template('add_event.html')

# 2.4 Admin: Assign event to mission
@app.route('/admin/assign_event', methods=['GET','POST'])
def assign_event():
    if session.get('role') != 'admin':
        return redirect('/login')
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    if request.method == 'POST':
        mission_id = request.form['mission_id']
        event_id   = request.form['event_id']
        cur.execute("""
          SELECT 1 FROM mission_events
           WHERE mission_id=%s AND event_id=%s
        """, (mission_id, event_id))
        if not cur.fetchone():
            cur.execute("""
              INSERT INTO mission_events (mission_id,event_id)
              VALUES (%s,%s)
            """, (mission_id, event_id))
            conn.commit()
        cur.close(); conn.close()
        return redirect('/admin')
    cur.execute("SELECT mission_id,mission_name FROM missions ORDER BY mission_name")
    missions = cur.fetchall()
    cur.execute("SELECT event_id,name FROM events ORDER BY date DESC")
    events   = cur.fetchall()
    cur.close(); conn.close()
    return render_template(
      'assign_event.html',
      missions=missions,
      events=events
    )

# 2.1 View all launch sites
@app.route('/launchsites')
def view_launchsites():
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM launchsites ORDER BY name")
    sites = cur.fetchall()
    cur.close(); conn.close()
    return render_template('launchsites.html', sites=sites)

# 2.2 Launch site profile + linked missions
@app.route('/launchsite/<int:launchsite_id>')
def launchsite_profile(launchsite_id):
    if 'user_id' not in session:
        return redirect('/login')
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM launchsites WHERE launchsite_id=%s",
                (launchsite_id,))
    site = cur.fetchone()
    cur.execute("""
      SELECT m.mission_id, m.mission_name, m.launch_date, m.status
      FROM mission_launchsites ml
      JOIN missions m ON ml.mission_id=m.mission_id
      WHERE ml.launchsite_id=%s
      ORDER BY m.launch_date DESC
    """, (launchsite_id,))
    missions = cur.fetchall()
    cur.close(); conn.close()
    return render_template(
      'launchsite_profile.html',
      site=site,
      missions=missions
    )

# 2.3 Add Launch Site (admin only)
@app.route('/admin/add_launchsite', methods=['GET','POST'])
def add_launchsite():
    if session.get('role') != 'admin':
        return abort(403)
    if request.method == 'POST':
        data = (
          request.form['name'],
          request.form['country'],
          request.form['latitude'],
          request.form['longitude'],
          request.form['established_year'],
          request.form['status'],
          request.form['description']
        )
        conn = connect_db()
        cur  = conn.cursor()
        cur.execute("""
          INSERT INTO launchsites
            (name,country,latitude,longitude,established_year,status,description)
          VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, data)
        conn.commit()
        cur.close(); conn.close()
        return redirect('/launchsites')
    return render_template('add_launchsite.html')

# 2.4 Assign Launch Site → Mission (admin only)
@app.route('/admin/assign_launchsite', methods=['GET','POST'])
def assign_launchsite():
    if session.get('role') != 'admin':
        return abort(403)
    conn = connect_db()
    cur  = conn.cursor(dictionary=True)

    if request.method == 'POST':
        mission_id    = request.form['mission_id']
        launchsite_id = request.form['launchsite_id']
        # prevent duplicates
        cur.execute("""
          SELECT 1 FROM mission_launchsites
           WHERE mission_id=%s AND launchsite_id=%s
        """, (mission_id, launchsite_id))
        if not cur.fetchone():
            cur.execute("""
              INSERT INTO mission_launchsites (mission_id,launchsite_id)
              VALUES (%s,%s)
            """, (mission_id, launchsite_id))
            conn.commit()
        cur.close(); conn.close()
        return redirect(f'/admin/assign_launchsite')

    # GET: fetch dropdown data
    cur.execute("SELECT mission_id, mission_name FROM missions ORDER BY mission_name")
    missions = cur.fetchall()
    cur.execute("SELECT launchsite_id, name FROM launchsites ORDER BY name")
    sites     = cur.fetchall()
    cur.close(); conn.close()

    return render_template(
      'assign_launchsite.html',
      missions=missions,
      sites=sites
    )


if __name__ == "__main__":
    app.run(debug=True)
