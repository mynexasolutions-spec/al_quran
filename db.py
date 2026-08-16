"""
Al-Qur'an Global Institute — Database Layer
Supabase PostgreSQL via psycopg2
"""
import os
import json
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
            display_order INTEGER DEFAULT 0,
            profile_image TEXT,
            is_visible  BOOLEAN DEFAULT TRUE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Non-destructive migrations for existing reviews table
    cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;")
    cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS profile_image TEXT;")
    cur.execute("ALTER TABLE reviews ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT TRUE;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS homepage_settings (
            section_key  VARCHAR(100) PRIMARY KEY,
            data         JSONB NOT NULL,
            is_visible   BOOLEAN DEFAULT TRUE,
            updated_at   TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id            SERIAL PRIMARY KEY,
            title         TEXT NOT NULL,
            slug          TEXT,
            category      TEXT NOT NULL DEFAULT 'Quranic Studies',
            description   TEXT,
            image_url     TEXT,
            badges        TEXT[],
            link_url      TEXT,
            seo_title     TEXT,
            seo_description TEXT,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Non-destructive migrations for existing courses table
    cur.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS seo_title TEXT;")
    cur.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS seo_description TEXT;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            role_label    TEXT,
            subject       TEXT,
            education     TEXT,
            image_url     TEXT,
            is_director   BOOLEAN DEFAULT FALSE,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS academic_subjects (
            id            SERIAL PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT,
            icon_or_image TEXT,
            badges        TEXT[],
            cta_text      TEXT,
            cta_url       TEXT,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS homepage_statistics (
            id            SERIAL PRIMARY KEY,
            value         TEXT NOT NULL,
            label         TEXT NOT NULL,
            icon          TEXT,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS homepage_features (
            id            SERIAL PRIMARY KEY,
            title         TEXT NOT NULL,
            description   TEXT,
            image_url     TEXT,
            icon          TEXT,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS homepage_faqs (
            id            SERIAL PRIMARY KEY,
            question      TEXT NOT NULL,
            answer        TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            is_visible    BOOLEAN DEFAULT TRUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_enquiries (
            id            SERIAL PRIMARY KEY,
            name          TEXT NOT NULL,
            phone         TEXT NOT NULL,
            email         TEXT,
            course        TEXT,
            age           TEXT,
            address       TEXT,
            message       TEXT,
            status        TEXT NOT NULL DEFAULT 'new',
            created_at    TIMESTAMPTZ DEFAULT NOW()
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


def delete_registration(rid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM registrations WHERE id=%s", (rid,))
    conn.commit(); cur.close(); conn.close()


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


def update_review(rid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE reviews SET
           name=%s, location=%s, course=%s, rating=%s, review_text=%s,
           status=%s, profile_image=%s, is_visible=%s, display_order=%s
           WHERE id=%s""",
        (data['name'], data.get('location', ''), data.get('course', ''),
         int(data.get('rating', 5)), data['review_text'],
         data.get('status', 'approved'), data.get('profile_image'),
         data.get('is_visible', True), int(data.get('display_order', 0)), rid)
    )
    conn.commit(); cur.close(); conn.close()


# ─────────────────────────────────────────────────────────────
#  Homepage CMS Helper Functions & In-Memory Caching
# ─────────────────────────────────────────────────────────────
import time

_CMS_CACHE = {}
_CMS_CACHE_TIME = 0
_CACHE_TTL_SECONDS = 60


def clear_cms_cache():
    global _CMS_CACHE, _CMS_CACHE_TIME
    _CMS_CACHE = {}
    _CMS_CACHE_TIME = 0


def get_all_homepage_cms_data(force_refresh=False):
    global _CMS_CACHE, _CMS_CACHE_TIME
    now = time.time()
    if not force_refresh and _CMS_CACHE and (now - _CMS_CACHE_TIME < _CACHE_TTL_SECONDS):
        return _CMS_CACHE

    conn = get_conn()
    cur  = conn.cursor()

    # 1. Settings
    cur.execute("SELECT * FROM homepage_settings")
    settings_rows = cur.fetchall()
    settings_dict = {}
    for r in settings_rows:
        res = dict(r)
        if isinstance(res.get('data'), str):
            try:
                res['data'] = json.loads(res['data'])
            except Exception:
                pass
        settings_dict[res['section_key']] = res

    # 2. Courses
    cur.execute("SELECT * FROM courses ORDER BY display_order ASC, created_at ASC")
    courses = [dict(r) for r in cur.fetchall()]

    # 3. Academic Subjects
    cur.execute("SELECT * FROM academic_subjects ORDER BY display_order ASC, id ASC")
    academic_subjects = [dict(r) for r in cur.fetchall()]

    # 4. Statistics
    cur.execute("SELECT * FROM homepage_statistics ORDER BY display_order ASC, id ASC")
    stats = [dict(r) for r in cur.fetchall()]

    # 5. Features
    cur.execute("SELECT * FROM homepage_features ORDER BY display_order ASC, id ASC")
    features = [dict(r) for r in cur.fetchall()]

    # 6. FAQs
    cur.execute("SELECT * FROM homepage_faqs ORDER BY display_order ASC, id ASC")
    faqs = [dict(r) for r in cur.fetchall()]

    # 7. Reviews
    cur.execute("SELECT * FROM reviews ORDER BY created_at DESC")
    all_reviews = [dict(r) for r in cur.fetchall()]

    # 8. Team Members
    cur.execute("SELECT * FROM team_members ORDER BY is_director DESC, display_order ASC, id ASC")
    team_members = [dict(r) for r in cur.fetchall()]

    # 9. Contact Enquiries
    cur.execute("SELECT * FROM contact_enquiries ORDER BY created_at DESC, id DESC")
    enquiries = [dict(r) for r in cur.fetchall()]

    cur.close(); conn.close()

    cms_data = {
        'settings': settings_dict,
        'courses': courses,
        'academic_subjects': academic_subjects,
        'stats': stats,
        'features': features,
        'faqs': faqs,
        'all_reviews': all_reviews,
        'team_members': team_members,
        'enquiries': enquiries
    }
    _CMS_CACHE = cms_data
    _CMS_CACHE_TIME = now
    return cms_data




def get_homepage_setting(key, default=None):
    all_data = get_all_homepage_cms_data()
    return all_data['settings'].get(key, default or {})


def save_homepage_setting(key, data, is_visible=True):
    conn = get_conn()
    cur  = conn.cursor()
    data_json = json.dumps(data) if isinstance(data, dict) or isinstance(data, list) else data
    cur.execute(
        """INSERT INTO homepage_settings (section_key, data, is_visible, updated_at)
           VALUES (%s, %s, %s, NOW())
           ON CONFLICT (section_key) DO UPDATE SET
           data = EXCLUDED.data, is_visible = EXCLUDED.is_visible, updated_at = NOW()""",
        (key, data_json, is_visible)
    )
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()



# ── Courses CRUD ──
def get_all_courses(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM courses"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY display_order ASC, created_at ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_course(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM courses WHERE id = %s", (cid,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def create_course(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO courses (title, slug, category, description, image_url, badges, link_url, seo_title, seo_description, display_order, is_visible)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (data['title'], data.get('slug', ''), data.get('category', 'Quranic Studies'),
         data.get('description'), data.get('image_url'), data.get('badges', []),
         data.get('link_url', ''), data.get('seo_title'), data.get('seo_description'),
         int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()
    return new_id


def update_course(cid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE courses SET
           title=%s, slug=%s, category=%s, description=%s, image_url=%s,
           badges=%s, link_url=%s, seo_title=%s, seo_description=%s, display_order=%s, is_visible=%s, updated_at=NOW()
           WHERE id=%s""",
        (data['title'], data.get('slug', ''), data.get('category', 'Quranic Studies'),
         data.get('description'), data.get('image_url'), data.get('badges', []),
         data.get('link_url', ''), data.get('seo_title'), data.get('seo_description'),
         int(data.get('display_order', 0)), data.get('is_visible', True), cid)
    )
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()



def delete_course(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()



# ── Academic Subjects CRUD ──
def get_all_academic_subjects(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM academic_subjects"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY display_order ASC, id ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_academic_subject(aid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM academic_subjects WHERE id = %s", (aid,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def create_academic_subject(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO academic_subjects (title, description, icon_or_image, badges, cta_text, cta_url, display_order, is_visible)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (data['title'], data.get('description'), data.get('icon_or_image'),
         data.get('badges', []), data.get('cta_text'), data.get('cta_url'),
         int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_academic_subject(aid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE academic_subjects SET
           title=%s, description=%s, icon_or_image=%s, badges=%s,
           cta_text=%s, cta_url=%s, display_order=%s, is_visible=%s
           WHERE id=%s""",
        (data['title'], data.get('description'), data.get('icon_or_image'),
         data.get('badges', []), data.get('cta_text'), data.get('cta_url'),
         int(data.get('display_order', 0)), data.get('is_visible', True), aid)
    )
    conn.commit(); cur.close(); conn.close()


def delete_academic_subject(aid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM academic_subjects WHERE id=%s", (aid,))
    conn.commit(); cur.close(); conn.close()


# ── Statistics CRUD ──
def get_all_statistics(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM homepage_statistics"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY display_order ASC, id ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def create_statistic(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO homepage_statistics (value, label, icon, display_order, is_visible)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (data['value'], data['label'], data.get('icon', '📊'),
         int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_statistic(sid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE homepage_statistics SET
           value=%s, label=%s, icon=%s, display_order=%s, is_visible=%s
           WHERE id=%s""",
        (data['value'], data['label'], data.get('icon', '📊'),
         int(data.get('display_order', 0)), data.get('is_visible', True), sid)
    )
    conn.commit(); cur.close(); conn.close()


def delete_statistic(sid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM homepage_statistics WHERE id=%s", (sid,))
    conn.commit(); cur.close(); conn.close()


# ── Features CRUD (Why Choose Us) ──
def get_all_features(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM homepage_features"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY display_order ASC, id ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def create_feature(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO homepage_features (title, description, image_url, icon, display_order, is_visible)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (data['title'], data.get('description'), data.get('image_url'), data.get('icon', '⭐'),
         int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_feature(fid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE homepage_features SET
           title=%s, description=%s, image_url=%s, icon=%s, display_order=%s, is_visible=%s
           WHERE id=%s""",
        (data['title'], data.get('description'), data.get('image_url'), data.get('icon', '⭐'),
         int(data.get('display_order', 0)), data.get('is_visible', True), fid)
    )
    conn.commit(); cur.close(); conn.close()


def delete_feature(fid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM homepage_features WHERE id=%s", (fid,))
    conn.commit(); cur.close(); conn.close()


# ── FAQs CRUD ──
def get_all_faqs(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM homepage_faqs"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY display_order ASC, id ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def create_faq(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO homepage_faqs (question, answer, display_order, is_visible)
           VALUES (%s, %s, %s, %s) RETURNING id""",
        (data['question'], data['answer'], int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_faq(fid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE homepage_faqs SET
           question=%s, answer=%s, display_order=%s, is_visible=%s
           WHERE id=%s""",
        (data['question'], data['answer'], int(data.get('display_order', 0)), data.get('is_visible', True), fid)
    )
    conn.commit(); cur.close(); conn.close()


def delete_faq(fid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM homepage_faqs WHERE id=%s", (fid,))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()


# ── Team Members CRUD ──
def get_all_team_members(visible_only=False):
    conn = get_conn()
    cur  = conn.cursor()
    sql = "SELECT * FROM team_members"
    if visible_only:
        sql += " WHERE is_visible = TRUE"
    sql += " ORDER BY is_director DESC, display_order ASC, id ASC"
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def get_team_member(tid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM team_members WHERE id = %s", (tid,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def create_team_member(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO team_members (name, role_label, subject, education, image_url, is_director, display_order, is_visible)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (data['name'], data.get('role_label', ''), data.get('subject', ''),
         data.get('education', ''), data.get('image_url'), data.get('is_director', False),
         int(data.get('display_order', 0)), data.get('is_visible', True))
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()
    return new_id


def update_team_member(tid, data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """UPDATE team_members SET
           name=%s, role_label=%s, subject=%s, education=%s, image_url=%s,
           is_director=%s, display_order=%s, is_visible=%s, updated_at=NOW()
           WHERE id=%s""",
        (data['name'], data.get('role_label', ''), data.get('subject', ''),
         data.get('education', ''), data.get('image_url'), data.get('is_director', False),
         int(data.get('display_order', 0)), data.get('is_visible', True), tid)
    )
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()


def delete_team_member(tid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM team_members WHERE id=%s", (tid,))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()


# ── Contact Enquiries CRUD ──
def create_contact_enquiry(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO contact_enquiries (name, phone, email, course, age, address, message, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (data['name'], data['phone'], data.get('email', ''), data.get('course', ''),
         data.get('age', ''), data.get('address', ''), data.get('message', ''), 'new')
    )
    new_id = cur.fetchone()['id']
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()
    return new_id


def get_all_contact_enquiries():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM contact_enquiries ORDER BY created_at DESC, id DESC")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def update_enquiry_status(eid, status):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("UPDATE contact_enquiries SET status = %s WHERE id = %s", (status, eid))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()


def delete_enquiry(eid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM contact_enquiries WHERE id = %s", (eid,))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()


def update_item_order(table_name, item_id, display_order):
    valid_tables = {'courses', 'academic_subjects', 'homepage_statistics', 'homepage_features', 'homepage_faqs', 'reviews', 'team_members', 'contact_enquiries'}
    if table_name not in valid_tables:
        return
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(f"UPDATE {table_name} SET display_order = %s WHERE id = %s", (display_order, item_id))
    conn.commit(); cur.close(); conn.close()
    clear_cms_cache()




# ─────────────────────────────────────────────────────────────
#  CMS Auto-Seeding
# ─────────────────────────────────────────────────────────────
_SEED_SETTINGS = {
    'hero': {
        'arabic_heading': 'وَرَتِّلِ الْقُرْآنَ تَرْتِيلًا',
        'title': 'Learn Quran with Tajweed & Islamic Studies Online',
        'sub_title': 'Excellence in Islamic and Language Education',
        'badge': 'Certified Native Scholars & Personalised 1-on-1 Guidance',
        'description': 'Master Quran Recitation, Tajweed, Hifz, Qirat, and Arabic Language from certified scholars worldwide with flexible schedules for adults and children.',
        'primary_cta_text': 'Explore Courses',
        'primary_cta_url': '#courses',
        'secondary_cta_text': 'Contact via WhatsApp',
        'secondary_cta_url': 'https://wa.me/919045520249',
        'image_url': '',
        'is_visible': True
    },
    'about': {
        'tag': 'Who We Are',
        'title': 'Pioneering Excellence in',
        'title_gold': 'Islamic & Language Education',
        'description': "Al-Qur'an Global Institute is a premier online academy dedicated to spreading authentic Quranic knowledge, Arabic proficiency, and Islamic values to students of all ages across the globe.",
        'mission_points': [
            'Certified & Experienced Native Male & Female Scholars',
            'Interactive 1-on-1 Live Classes Tailored to Every Student',
            'Flexible Scheduling Across All Global Timezones',
            'Structured Curriculum from Beginner to Ijazah Level',
            'Regular Student Progress Assessment & Direct Parent Feedback',
            'Free Trial Class & Affordable Monthly Subscription Plans'
        ],
        'image_url': '/static/images/who_we_are.webp',
        'is_visible': True
    },
    'seo': {
        'title': "Al-Qur'an Global Institute — Online Quran, Arabic & Islamic Studies",
        'meta_description': 'Learn Quran recitation, Tajweed, Hifz, Qirat, Arabic, Urdu and English with certified tutors worldwide. Interactive 1-on-1 online classes.',
        'og_image': '/static/images/logo.png',
        'canonical_url': 'https://alquranglobal.com',
        'is_visible': True
    },
    'courses_header': {
        'tag': 'Browse Our Programs',
        'title': 'Explore Our',
        'title_span': 'Featured Courses',
        'description': 'Structured online courses designed for students of all ages — guided by certified native scholars.',
        'is_visible': True
    },
    'academic_header': {
        'tag': 'School Curriculum Support',
        'title': 'Academic',
        'title_span': 'Subjects Tuition',
        'description': 'Personalized online tutoring in Mathematics, Science, English, and general subjects for school students.',
        'is_visible': True
    },
    'why_choose_header': {
        'tag': 'Why Choose Us',
        'title': 'Why Study With',
        'title_span': "Al-Qur'an Global Institute",
        'is_visible': True
    },
    'faq_header': {
        'tag': 'Frequently Asked Questions',
        'title': 'Got',
        'title_span': 'Questions?',
        'is_visible': True
    },
    'reviews_header': {
        'tag': 'Student Testimonials',
        'title': 'What Our Students',
        'title_span': '& Parents Say',
        'is_visible': True
    }
}

_SEED_COURSES = [
    {
        'title': 'Tajweed Course',
        'slug': 'tajweed',
        'category': 'Quranic Studies',
        'description': 'Learn proper pronunciation (Makharij) and rules of Tajweed with certified male and female scholars.',
        'image_url': '/static/images/courses/tajweed.webp',
        'badges': ['All Levels', 'Online', 'Certificate'],
        'link_url': '/course/tajweed',
        'display_order': 1
    },
    {
        'title': 'Quran Recitation Course',
        'slug': 'quran-recitation',
        'category': 'Quranic Studies',
        'description': 'Improve fluency, melody, and rhythm in Quran reading with guided daily practice.',
        'image_url': '/static/images/courses/Quran_recitation_course.webp',
        'badges': ['1 Year', 'All Levels', 'Nazira'],
        'link_url': '/course/quran-recitation',
        'display_order': 2
    },
    {
        'title': 'Quran Hifz Course',
        'slug': 'hifz',
        'category': 'Quranic Studies',
        'description': 'Systematic Quran memorization program with regular revision and personal Hafiz guide.',
        'image_url': '/static/images/courses/Quran_Hifz.webp',
        'badges': ['Mon-Sat', 'All Ages', 'Hafiz Path'],
        'link_url': '/course/hifz',
        'display_order': 3
    },
    {
        'title': 'Qirat Course',
        'slug': 'qirat',
        'category': 'Quranic Studies',
        'description': 'Master the authentic ten recitations (Qira’at) under qualified scholars leading to Ijazah.',
        'image_url': '/static/images/courses/Quran_Qirat_course.webp',
        'badges': ['Flexible', 'Ijazah', 'Advanced'],
        'link_url': '/course/qirat',
        'display_order': 4
    },
    {
        'title': 'Basic Arabic Speaking Course',
        'slug': 'arabic',
        'category': 'Language Courses',
        'description': 'Develop conversational Arabic skills, vocabulary, and grammar for daily communication.',
        'image_url': '/static/images/courses/Arabic_Speaking_Course.webp',
        'badges': ['3 Months', 'Beginner', '5x Week'],
        'link_url': '/course/arabic',
        'display_order': 5
    },
    {
        'title': 'Urdu Language Course',
        'slug': 'urdu',
        'category': 'Language Courses',
        'description': 'Master reading, writing, and speaking Urdu language with structured lessons.',
        'image_url': '/static/images/courses/Urdu_language.webp',
        'badges': ['Tue-Wed', 'All Levels', 'Certificate'],
        'link_url': '/course/urdu',
        'display_order': 6
    },
    {
        'title': 'Basic English Course',
        'slug': 'english',
        'category': 'Language Courses',
        'description': 'Improve English grammar, vocabulary, and confident spoken English skills.',
        'image_url': '/static/images/courses/English_course.webp',
        'badges': ['3 Months', 'Beginner', '5x Week'],
        'link_url': '/course/english',
        'display_order': 7
    }
]

_SEED_ACADEMIC_SUBJECTS = [
    {
        'title': 'Mathematics Tuition',
        'description': 'Comprehensive math assistance covering arithmetic, algebra, geometry, and problem solving.',
        'icon_or_image': '📐',
        'badges': ['Grades 1-12', '1-on-1', 'Homework Help'],
        'cta_text': 'Enroll via Contact',
        'cta_url': '#contact',
        'display_order': 1
    },
    {
        'title': 'Science & Biology',
        'description': 'Interactive science concepts, physics fundamentals, chemistry, and biology support.',
        'icon_or_image': '🔬',
        'badges': ['Primary & Secondary', 'Lab Concepts', 'Exam Prep'],
        'cta_text': 'Enroll via Contact',
        'cta_url': '#contact',
        'display_order': 2
    },
    {
        'title': 'English Academic Support',
        'description': 'Grammar, creative writing, comprehension, and school curriculum English language arts.',
        'icon_or_image': '📖',
        'badges': ['Reading & Writing', 'All Grades'],
        'cta_text': 'Enroll via Contact',
        'cta_url': '#contact',
        'display_order': 3
    }
]

_SEED_STATS = [
    {'value': '1000+', 'label': 'Active Students Worldwide', 'icon': '🎓', 'display_order': 1},
    {'value': '50+', 'label': 'Weekly Live Classes', 'icon': '💻', 'display_order': 2},
    {'value': '15+', 'label': 'Countries Reached', 'icon': '🌍', 'display_order': 3},
    {'value': '4.9/5', 'label': 'Student & Parent Rating', 'icon': '⭐', 'display_order': 4}
]

_SEED_FEATURES = [
    {
        'title': 'Expert Quran Tutors',
        'description': 'Qualified Hafiz and Qari teachers with years of online teaching experience.',
        'image_url': '/static/images/why/expert_tutor.webp',
        'icon': '🎓',
        'display_order': 1
    },
    {
        'title': 'We Value Our Students',
        'description': 'Dedicated academic advisors and personalized learning plans for every student.',
        'image_url': '/static/images/why/we_value_our_students.webp',
        'icon': '💖',
        'display_order': 2
    },
    {
        'title': 'One-on-One Classes',
        'description': 'Individual attention in private online sessions tailored to your pace.',
        'image_url': '/static/images/why/one-on-one-classes.webp',
        'icon': '👥',
        'display_order': 3
    },
    {
        'title': 'Flexible Timings',
        'description': 'Choose a schedule that fits your daily routine across any time zone.',
        'image_url': '/static/images/why/flexible-timings.webp',
        'icon': '⏰',
        'display_order': 4
    }
]

_SEED_FAQS = [
    {
        'question': 'How do online 1-on-1 classes work at Al-Qur’an Global Institute?',
        'answer': 'Classes are conducted via Zoom or Google Meet. You get a private video session with your dedicated tutor, customized to your learning pace and schedule.',
        'display_order': 1
    },
    {
        'question': 'Can I choose between male and female teachers?',
        'answer': 'Yes, absolutely. We have certified male and female scholars available for children and adult female students.',
        'display_order': 2
    },
    {
        'question': 'Is there a free trial class available before enrolling?',
        'answer': 'Yes! We offer a complimentary 30-minute 1-on-1 trial session so you can evaluate the teacher and teaching methodology.',
        'display_order': 3
    },
    {
        'question': 'What age groups do you teach?',
        'answer': 'We teach students from age 4 onwards, including young kids, teenagers, adults, and seniors.',
        'display_order': 4
    },
    {
        'question': 'How do I track my child’s progress?',
        'answer': 'Our academic supervisors send monthly progress reports and host regular parent-teacher updates via WhatsApp or email.',
        'display_order': 5
    },
    {
        'question': 'What are the class timings and frequency options?',
        'answer': 'You can choose 2, 3, or 5 classes per week. Timings are 100% flexible based on your timezone.',
        'display_order': 6
    },
    {
        'question': 'Do you award certificates upon course completion?',
        'answer': 'Yes, students completing course requirements receive an official Al-Qur’an Global Institute Certificate, and advanced students can attain Ijazah.',
        'display_order': 7
    },
    {
        'question': 'How can I make fee payments?',
        'answer': 'We accept online payments via bank transfer, PayPal, and credit/debit cards with transparent monthly billing.',
        'display_order': 8
    }
]

_SEED_REVIEWS = [
    {
        'name': 'Fatima Al-Amin',
        'location': 'London, UK',
        'course': 'Tajweed Course',
        'rating': 5,
        'review_text': 'The Tajweed course transformed my recitation completely. The instructor’s patience and detailed feedback made such a difference. JazakAllah Khair!',
        'status': 'approved',
        'display_order': 1
    },
    {
        'name': 'Khalid Mahmood',
        'location': 'Toronto, Canada',
        'course': 'Hifz Course',
        'rating': 5,
        'review_text': 'My son completed Juz Amma in the Hifz program in just 3 months. The structured daily plan and personal attention is truly exceptional.',
        'status': 'approved',
        'display_order': 2
    },
    {
        'name': 'Zainab Rahman',
        'location': 'Dubai, UAE',
        'course': 'Arabic Course',
        'rating': 5,
        'review_text': 'I enrolled in the Arabic speaking course as a complete beginner. Within 3 months I could hold basic conversations. An amazing program!',
        'status': 'approved',
        'display_order': 3
    },
    {
        'name': 'Nadia Anwar',
        'location': 'Manchester, UK',
        'course': 'Home Tuition',
        'rating': 5,
        'review_text': 'Wonderful institute! My three children attend different courses and all of them look forward to every single class. The teachers are inspiring.',
        'status': 'approved',
        'display_order': 4
    },
    {
        'name': 'Omar Bashir',
        'location': 'New York, USA',
        'course': 'Online Hifz',
        'rating': 5,
        'review_text': 'I completed my Juz Amma memorization in just 4 months. The systematic revision method is excellent. Already signed up for the next Juz!',
        'status': 'approved',
        'display_order': 5
    },
    {
        'name': 'Samira Idris',
        'location': 'Birmingham, UK',
        'course': 'Islamic Studies',
        'rating': 5,
        'review_text': 'The Islamic Studies alongside Quran is wonderful. My kids now understand what they’re reciting — it has made them truly fall in love with learning.',
        'status': 'approved',
        'display_order': 6
    }
]


_SEED_TEAM = [
    {
        'name': 'Qari Mohammad Shariq Zafar',
        'role_label': 'Founder & Director',
        'subject': 'Tajweed & Qirat Scholar',
        'education': 'Aalim, Qari & Hafiz',
        'image_url': '/static/images/team/director_shariq_zafar.jpeg',
        'is_director': True,
        'display_order': 0,
        'is_visible': True
    },
    {
        'name': 'Maulana Osama Quasmi',
        'role_label': 'Senior Educator',
        'subject': 'Quran Recitation & Islamic Studies',
        'education': 'Graduate from Darul Uloom Deoband',
        'image_url': '/static/images/team/maulana_osama_quasmi.jpeg',
        'is_director': False,
        'display_order': 1,
        'is_visible': True
    },
    {
        'name': 'Mufti Maaz Quasmi',
        'role_label': 'Senior Educator',
        'subject': 'Fiqh & Quranic Sciences',
        'education': 'Mufti & Scholar',
        'image_url': '/static/images/team/mufti_maaz_quasmi.jpeg',
        'is_director': False,
        'display_order': 2,
        'is_visible': True
    },
    {
        'name': 'Aalima Rahnuma Fatima',
        'role_label': 'Female Tutor',
        'subject': 'Tajweed & Arabic Tutoress',
        'education': 'Aalima',
        'image_url': '/static/images/team/default_female.svg',
        'is_director': False,
        'display_order': 3,
        'is_visible': True
    },
    {
        'name': 'Hafiza Sumaiya Fatima',
        'role_label': 'Female Tutor',
        'subject': 'Hifz & Tajweed Tutoress',
        'education': 'Hafiza & Aalima',
        'image_url': '/static/images/team/default_female.svg',
        'is_director': False,
        'display_order': 4,
        'is_visible': True
    },
    {
        'name': 'Hafiza Safia Junaid',
        'role_label': 'Female Tutor',
        'subject': 'Quran & Urdu Language Tutoress',
        'education': 'Hafiza',
        'image_url': '/static/images/team/default_female.svg',
        'is_director': False,
        'display_order': 5,
        'is_visible': True
    },
    {
        'name': 'Dr Noorussama Fatima',
        'role_label': 'Academic Specialist',
        'subject': 'Academic & School Curriculum Support',
        'education': 'PhD / Academic Specialist',
        'image_url': '/static/images/team/default_female.svg',
        'is_director': False,
        'display_order': 6,
        'is_visible': True
    }
]


def seed_cms_data():
    conn = get_conn()
    cur  = conn.cursor()

    # 1. Seed homepage settings
    cur.execute("SELECT COUNT(*) AS cnt FROM homepage_settings")
    if cur.fetchone()['cnt'] == 0:
        for k, v in _SEED_SETTINGS.items():
            cur.execute(
                "INSERT INTO homepage_settings (section_key, data, is_visible) VALUES (%s, %s, %s)",
                (k, json.dumps(v), v.get('is_visible', True))
            )

    # 2. Seed courses
    cur.execute("SELECT COUNT(*) AS cnt FROM courses")
    if cur.fetchone()['cnt'] == 0:
        for c in _SEED_COURSES:
            cur.execute(
                """INSERT INTO courses (title, slug, category, description, image_url, badges, link_url, display_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (c['title'], c['slug'], c['category'], c['description'],
                 c['image_url'], c['badges'], c['link_url'], c['display_order'])
            )

    # 3. Seed academic subjects
    cur.execute("SELECT COUNT(*) AS cnt FROM academic_subjects")
    if cur.fetchone()['cnt'] == 0:
        for a in _SEED_ACADEMIC_SUBJECTS:
            cur.execute(
                """INSERT INTO academic_subjects (title, description, icon_or_image, badges, cta_text, cta_url, display_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (a['title'], a['description'], a['icon_or_image'], a['badges'], a['cta_text'], a['cta_url'], a['display_order'])
            )

    # 4. Seed statistics
    cur.execute("SELECT COUNT(*) AS cnt FROM homepage_statistics")
    if cur.fetchone()['cnt'] == 0:
        for s in _SEED_STATS:
            cur.execute(
                "INSERT INTO homepage_statistics (value, label, icon, display_order) VALUES (%s, %s, %s, %s)",
                (s['value'], s['label'], s['icon'], s['display_order'])
            )

    # 5. Seed features
    cur.execute("SELECT COUNT(*) AS cnt FROM homepage_features")
    if cur.fetchone()['cnt'] == 0:
        for f in _SEED_FEATURES:
            cur.execute(
                "INSERT INTO homepage_features (title, description, image_url, icon, display_order) VALUES (%s, %s, %s, %s, %s)",
                (f['title'], f['description'], f['image_url'], f['icon'], f['display_order'])
            )

    # 6. Seed FAQs
    cur.execute("SELECT COUNT(*) AS cnt FROM homepage_faqs")
    if cur.fetchone()['cnt'] == 0:
        for q in _SEED_FAQS:
            cur.execute(
                "INSERT INTO homepage_faqs (question, answer, display_order) VALUES (%s, %s, %s)",
                (q['question'], q['answer'], q['display_order'])
            )

    # 7. Seed initial static reviews into reviews table if reviews table is empty
    cur.execute("SELECT COUNT(*) AS cnt FROM reviews")
    if cur.fetchone()['cnt'] == 0:
        for r in _SEED_REVIEWS:
            cur.execute(
                """INSERT INTO reviews (name, location, course, rating, review_text, status, display_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (r['name'], r['location'], r['course'], r['rating'], r['review_text'], r['status'], r['display_order'])
            )

    # 8. Seed initial team members if team_members table is empty
    cur.execute("SELECT COUNT(*) AS cnt FROM team_members")
    if cur.fetchone()['cnt'] == 0:
        for m in _SEED_TEAM:
            cur.execute(
                """INSERT INTO team_members (name, role_label, subject, education, image_url, is_director, display_order, is_visible)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (m['name'], m['role_label'], m['subject'], m['education'], m['image_url'], m['is_director'], m['display_order'], m['is_visible'])
            )

    conn.commit()
    cur.close()
    conn.close()


