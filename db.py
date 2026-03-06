"""
Al-Qur'an Global Institute — Database Layer
Supabase PostgreSQL via psycopg2
"""
import os
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

load_dotenv()

_DATABASE_URL = os.environ.get('DATABASE_URL', '')
# Vercel may deliver env vars as bytes; normalise to str
if isinstance(_DATABASE_URL, bytes):
    _DATABASE_URL = _DATABASE_URL.decode('utf-8')
DATABASE_URL = _DATABASE_URL


# ─────────────────────────────────────────────────────────────
#  Connection helper
#  - Guards against empty DATABASE_URL (env var not configured)
#  - PRIMARY: passes the URI directly to psycopg2 which has its
#    own RFC-3986 parser and handles %xx-encoded passwords.
#  - FALLBACK: manual rsplit('@', 1) for literal-@ passwords.
# ─────────────────────────────────────────────────────────────
def get_conn():
    raw = (DATABASE_URL or '').strip()
    if not raw:
        raise RuntimeError(
            "DATABASE_URL is not set. "
            "Add it in Vercel → Project Settings → Environment Variables."
        )

    # Ensure sslmode=require is present in the URI
    db_url = raw
    if 'sslmode=' not in db_url:
        db_url += ('&' if '?' in db_url else '?') + 'sslmode=require'

    # PRIMARY: psycopg2 native URI parser (handles %xx-encoding correctly)
    try:
        return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.RealDictCursor)
    except Exception:
        pass  # fall through to manual parser

    # FALLBACK: manual rsplit for literal-@ passwords that confuse URI parsers
    rest = raw.split('://', 1)[-1]
    if '?' in rest:
        rest = rest.split('?', 1)[0]
    userinfo, hostinfo = rest.rsplit('@', 1)
    user, password     = userinfo.split(':', 1)
    host_port, dbname  = hostinfo.split('/', 1)
    if ':' in host_port:
        host, port_str = host_port.rsplit(':', 1)
        port = int(port_str)
    else:
        host, port = host_port, 5432
    return psycopg2.connect(
        host     = host,
        port     = port,
        dbname   = dbname,
        user     = unquote(user),
        password = unquote(password),
        sslmode  = 'require',
        cursor_factory = psycopg2.extras.RealDictCursor,
    )


# ─────────────────────────────────────────────────────────────
#  Schema initialisation
# ─────────────────────────────────────────────────────────────
def init_db():
    conn = get_conn()
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id           SERIAL PRIMARY KEY,
            title        TEXT NOT NULL,
            category     TEXT NOT NULL DEFAULT 'Quranic Studies',
            description  TEXT,
            date_display TEXT,
            status       TEXT NOT NULL DEFAULT 'upcoming',
            location     TEXT DEFAULT 'Online — Worldwide',
            age_group    TEXT DEFAULT 'All Ages',
            prize        TEXT,
            tags         TEXT[],
            icon         TEXT DEFAULT '🏆',
            color_theme  TEXT DEFAULT 'teal',
            image_url    TEXT,
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            updated_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id                 SERIAL PRIMARY KEY,
            competition_id     INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
            competition_title  TEXT,
            name               TEXT NOT NULL,
            email              TEXT NOT NULL,
            phone              TEXT,
            age                TEXT,
            country            TEXT,
            experience         TEXT,
            notes              TEXT,
            created_at         TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id          SERIAL PRIMARY KEY,
            name        TEXT NOT NULL,
            location    TEXT,
            course      TEXT,
            rating      INTEGER NOT NULL DEFAULT 5 CHECK (rating BETWEEN 1 AND 5),
            review_text TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Seed data (runs only when competitions table is empty)
# ─────────────────────────────────────────────────────────────
_SEED = [
    {
        'title': 'International Qirat Competition',
        'category': 'Quranic Studies',
        'description': "Showcase mastery of the authentic recitation styles (Qira'at) before a panel of certified scholars. Open to students pursuing Ijazah and advanced recitation pathways.",
        'date_display': 'April 20, 2026',
        'status': 'upcoming',
        'location': 'Online — Worldwide',
        'age_group': 'Ages 12 & Above',
        'prize': 'Certificate & Cash Prize',
        'tags': ['Recitation', 'Advanced', 'Ijazah Path'],
        'icon': '🎤',
        'color_theme': 'teal',
    },
    {
        'title': 'Islamic Quiz Championship',
        'category': 'Islamic Knowledge',
        'description': 'A multi-round quiz competition covering Fiqh, Seerah, Hadith, and Quranic knowledge. Compete individually or as a team and prove your Islamic scholarship.',
        'date_display': 'May 10, 2026',
        'status': 'upcoming',
        'location': 'Online — Worldwide',
        'age_group': 'All Ages',
        'prize': 'Trophy & Certificate',
        'tags': ['Quiz', 'Teams & Individual', 'All Levels'],
        'icon': '📚',
        'color_theme': 'gold',
    },
    {
        'title': 'Tajweed Excellence Competition',
        'category': 'Quranic Studies',
        'description': 'Demonstrate precision in Makhraj, Sifaat, and Madd rules in this prestigious Tajweed competition. Our expert panel assesses correctness, fluency, and beauty of recitation.',
        'date_display': 'Mar 1 – Apr 30, 2026',
        'status': 'ongoing',
        'location': 'Online — Worldwide',
        'age_group': 'Ages 8 & Above',
        'prize': 'Ijazah Certificate',
        'tags': ['Tajweed', 'All Levels', 'Certificate'],
        'icon': '🔔',
        'color_theme': 'green',
    },
    {
        'title': 'Hifz Memorization Contest',
        'category': 'Quran Memorization',
        'description': "A test of memory, precision, and devotion — students are assessed on their memorization of selected Juz' with proper Tajweed. Categories from Juz Amma to Full Quran.",
        'date_display': 'June 14, 2026',
        'status': 'upcoming',
        'location': 'Online — Worldwide',
        'age_group': 'All Ages',
        'prize': 'Hifz Shield & Prize',
        'tags': ['Hifz', 'Multiple Categories', 'All Ages'],
        'icon': '✨',
        'color_theme': 'teal',
    },
    {
        'title': 'Arabic Calligraphy Competition',
        'category': 'Arabic Language',
        'description': "Express Islamic art through the beauty of Arabic script. Submit your calligraphy artwork — Naskh, Thuluth, or Ruq'ah — and be judged on elegance, precision, and creativity.",
        'date_display': 'Submissions: Mar – Apr 2026',
        'status': 'ongoing',
        'location': 'Submit Online',
        'age_group': 'All Ages',
        'prize': 'Art Kit & Certificate',
        'tags': ['Arabic', 'Art', 'Creative'],
        'icon': '✏️',
        'color_theme': 'gold',
    },
    {
        'title': 'Islamic Essay Writing Competition',
        'category': 'Islamic Writing',
        'description': 'Students wrote inspiring essays on topics like "The Quran as a Guide for Modern Life" and "Lessons from the Seerah." Winners received prizes and published on our platform.',
        'date_display': 'January 2026 — Concluded',
        'status': 'completed',
        'location': 'Online Submission',
        'age_group': 'Ages 12 & Above',
        'prize': 'Published & Awarded',
        'tags': ['Essay', 'Writing', 'Published Winners'],
        'icon': '📝',
        'color_theme': 'grey',
    },
]


def seed_competitions():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM competitions")
    if cur.fetchone()['cnt'] == 0:
        for c in _SEED:
            cur.execute(
                """INSERT INTO competitions
                   (title,category,description,date_display,status,location,age_group,prize,tags,icon,color_theme)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (c['title'], c['category'], c['description'], c['date_display'],
                 c['status'], c['location'], c['age_group'], c['prize'],
                 c['tags'], c['icon'], c['color_theme'])
            )
    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Competitions CRUD
# ─────────────────────────────────────────────────────────────
def get_all_competitions():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM competitions ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_competition(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM competitions WHERE id = %s", (cid,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def create_competition(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO competitions
           (title,category,description,date_display,status,location,age_group,prize,tags,icon,color_theme,image_url)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (data['title'], data['category'], data.get('description'), data.get('date_display'),
         data.get('status','upcoming'), data.get('location','Online — Worldwide'),
         data.get('age_group','All Ages'), data.get('prize'),
         data.get('tags',[]), data.get('icon','🏆'),
         data.get('color_theme','teal'), data.get('image_url'))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_competition(cid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE competitions SET
           title=%s, category=%s, description=%s, date_display=%s,
           status=%s, location=%s, age_group=%s, prize=%s,
           tags=%s, icon=%s, color_theme=%s, image_url=%s,
           updated_at=NOW()
           WHERE id=%s""",
        (data['title'], data['category'], data.get('description'), data.get('date_display'),
         data.get('status','upcoming'), data.get('location','Online — Worldwide'),
         data.get('age_group','All Ages'), data.get('prize'),
         data.get('tags',[]), data.get('icon','🏆'),
         data.get('color_theme','teal'), data.get('image_url'), cid)
    )
    conn.commit(); cur.close(); conn.close()


def update_competition_status(cid, status):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE competitions SET status=%s, updated_at=NOW() WHERE id=%s", (status, cid))
    conn.commit(); cur.close(); conn.close()


def delete_competition(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM competitions WHERE id=%s", (cid,))
    conn.commit(); cur.close(); conn.close()


# ─────────────────────────────────────────────────────────────
#  Registrations CRUD
# ─────────────────────────────────────────────────────────────
def create_registration(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO registrations
           (competition_id,competition_title,name,email,phone,age,country,experience,notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (data['competition_id'], data.get('competition_title'),
         data['name'], data['email'], data.get('phone'),
         data.get('age'), data.get('country'),
         data.get('experience'), data.get('notes'))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def get_all_registrations(competition_id=None):
    conn = get_conn()
    cur  = conn.cursor()
    if competition_id:
        cur.execute(
            "SELECT * FROM registrations WHERE competition_id=%s ORDER BY created_at DESC",
            (competition_id,)
        )
    else:
        cur.execute("SELECT * FROM registrations ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_registration_count(competition_id):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM registrations WHERE competition_id=%s", (competition_id,))
    cnt = cur.fetchone()['cnt']
    cur.close(); conn.close()
    return cnt


# ─────────────────────────────────────────────────────────────
#  Reviews
# ─────────────────────────────────────────────────────────────
def create_review(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO reviews (name, location, course, rating, review_text)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (data['name'], data.get('location', ''), data.get('course', ''),
         int(data.get('rating', 5)), data['review_text'])
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def get_approved_reviews():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM reviews WHERE status='approved' ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_all_reviews():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM reviews ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def update_review_status(review_id, status):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE reviews SET status=%s WHERE id=%s", (status, review_id))
    conn.commit(); cur.close(); conn.close()


def delete_review(review_id):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM reviews WHERE id=%s", (review_id,))
    conn.commit(); cur.close(); conn.close()
