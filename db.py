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

    # Singleton settings row (id is always 1) holding the editable
    # homepage hero banner — image + heading/subtitle/button copy.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hero_content (
            id                INTEGER PRIMARY KEY DEFAULT 1,
            badge_text        TEXT NOT NULL DEFAULT '#1 World''s Trusted Online Quran Institute',
            heading_line1     TEXT NOT NULL DEFAULT 'Learn the Quran',
            heading_prefix    TEXT NOT NULL DEFAULT 'with',
            heading_highlight TEXT NOT NULL DEFAULT 'Excellence',
            heading_line3     TEXT NOT NULL DEFAULT 'from Anywhere',
            heading_line4     TEXT NOT NULL DEFAULT 'in the World',
            subtitle          TEXT NOT NULL DEFAULT 'One-to-one Quran classes with Tajweed, Hifz, Arabic language and Islamic studies for all ages.',
            btn1_text         TEXT NOT NULL DEFAULT 'Enroll Now',
            btn1_link         TEXT NOT NULL DEFAULT '#courses',
            btn2_text         TEXT NOT NULL DEFAULT 'Book Free Trial',
            btn2_link         TEXT NOT NULL DEFAULT 'https://wa.me/919045520249',
            image_url         TEXT NOT NULL DEFAULT '/static/images/al-quran-banner.webp',
            updated_at        TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT hero_content_singleton CHECK (id = 1)
        )
    """)

    # Courses — the homepage "Popular Courses" grid card, the "other
    # courses" cross-links on every course page, and (when
    # has_detail_page is true) a full course detail page are all
    # rendered from this one row. Column groups, in order: homepage
    # card, "other courses" cross-link card, detail-page hero,
    # sidebar, and the fixed quote/intro that opens the detail body.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id                SERIAL PRIMARY KEY,
            slug              TEXT UNIQUE NOT NULL,
            sort_order        INTEGER NOT NULL DEFAULT 0,
            has_detail_page   BOOLEAN NOT NULL DEFAULT TRUE,

            card_category     TEXT NOT NULL DEFAULT '',
            card_image_url    TEXT,
            card_description  TEXT NOT NULL DEFAULT '',
            card_badges       JSONB NOT NULL DEFAULT '[]',

            oc_title          TEXT NOT NULL DEFAULT '',
            oc_description    TEXT NOT NULL DEFAULT '',

            category          TEXT NOT NULL DEFAULT '',
            icon_url          TEXT,
            title             TEXT NOT NULL DEFAULT '',
            arabic_title      TEXT NOT NULL DEFAULT '',
            tagline           TEXT NOT NULL DEFAULT '',
            hero_badges       JSONB NOT NULL DEFAULT '[]',

            duration          TEXT NOT NULL DEFAULT '',
            schedule          TEXT NOT NULL DEFAULT '',
            eligibility       TEXT NOT NULL DEFAULT '',
            certificate_val   TEXT NOT NULL DEFAULT '',

            quote             TEXT NOT NULL DEFAULT '',
            quote_cite        TEXT NOT NULL DEFAULT '',
            intro             TEXT NOT NULL DEFAULT '',

            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Each row is one content block in a course's detail-page body,
    # rendered in sort_order. block_type is one of:
    #   'bullets'     — <ul class="{list_style}">, items = ["...", ...]
    #   'highlights'  — .highlights-grid, items = [{icon_url,heading,text}, ...]
    #   'paragraphs'  — plain <p> tags, items = ["...", ...]
    # list_style (bullets only) is 'learn-list' (✦ gold bullet) or
    # 'detail-list' (✓ teal check) — the two styles already in course.css.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS course_sections (
            id           SERIAL PRIMARY KEY,
            course_id    INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
            sort_order   INTEGER NOT NULL DEFAULT 0,
            block_type   TEXT NOT NULL,
            list_style   TEXT,
            heading      TEXT NOT NULL DEFAULT '',
            items        JSONB NOT NULL DEFAULT '[]'
        )
    """)

    # Singleton row holding the "Prizes & Recognition" section's intro
    # copy on the competitions page (the cards themselves are the
    # `prizes` table below).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prizes_section (
            id           INTEGER PRIMARY KEY DEFAULT 1,
            tag          TEXT NOT NULL DEFAULT 'Rewards',
            heading      TEXT NOT NULL DEFAULT 'Prizes &',
            heading_span TEXT NOT NULL DEFAULT 'Recognition',
            subtitle     TEXT NOT NULL DEFAULT 'We celebrate every participant''s effort, with special honours for those who excel at the top.',
            updated_at   TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT prizes_section_singleton CHECK (id = 1)
        )
    """)

    # One row per prize card on the competitions page (1st Place, 2nd
    # Place, etc). `variant` picks one of the 4 card styles already
    # defined in competitions.css (.prize-card--<variant>).
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prizes (
            id          SERIAL PRIMARY KEY,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            variant     TEXT NOT NULL DEFAULT 'gold',
            medal_icon  TEXT NOT NULL DEFAULT '🏆',
            heading     TEXT NOT NULL DEFAULT '',
            items       JSONB NOT NULL DEFAULT '[]',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── Urdu columns ─────────────────────────────────────────
    # Added after the tables above already existed with English-only
    # data (from earlier migrations), so these use ADD COLUMN IF NOT
    # EXISTS rather than being part of the CREATE TABLE statements —
    # that keeps this safe to re-run against a database that already
    # has rows in it. Every "<field>_ur" holds the Urdu version of
    # "<field>"; the public site falls back to the English value
    # whenever the Urdu one is empty (see `localize()` in app.py).
    for table, col, coltype in [
        ('hero_content', 'badge_text_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'heading_line1_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'heading_prefix_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'heading_highlight_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'heading_line3_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'heading_line4_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'subtitle_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'btn1_text_ur', "TEXT NOT NULL DEFAULT ''"),
        ('hero_content', 'btn2_text_ur', "TEXT NOT NULL DEFAULT ''"),

        ('courses', 'card_category_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'card_description_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'card_badges_ur', "JSONB NOT NULL DEFAULT '[]'"),
        ('courses', 'oc_title_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'oc_description_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'category_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'title_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'tagline_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'hero_badges_ur', "JSONB NOT NULL DEFAULT '[]'"),
        ('courses', 'duration_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'schedule_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'eligibility_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'certificate_val_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'quote_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'quote_cite_ur', "TEXT NOT NULL DEFAULT ''"),
        ('courses', 'intro_ur', "TEXT NOT NULL DEFAULT ''"),

        ('course_sections', 'heading_ur', "TEXT NOT NULL DEFAULT ''"),
        ('course_sections', 'items_ur', "JSONB NOT NULL DEFAULT '[]'"),

        ('prizes_section', 'tag_ur', "TEXT NOT NULL DEFAULT ''"),
        ('prizes_section', 'heading_ur', "TEXT NOT NULL DEFAULT ''"),
        ('prizes_section', 'heading_span_ur', "TEXT NOT NULL DEFAULT ''"),
        ('prizes_section', 'subtitle_ur', "TEXT NOT NULL DEFAULT ''"),

        ('prizes', 'heading_ur', "TEXT NOT NULL DEFAULT ''"),
        ('prizes', 'items_ur', "JSONB NOT NULL DEFAULT '[]'"),
    ]:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {coltype}")

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


def seed_hero_content():
    """Insert the singleton hero-content row (id=1) if it doesn't exist yet.
    All column defaults match the original hard-coded homepage copy, so a
    fresh database renders identically to before this feature existed."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        "INSERT INTO hero_content (id) VALUES (1) ON CONFLICT (id) DO NOTHING"
    )
    conn.commit()
    cur.close()
    conn.close()


# Hand-written Urdu translation of the hero banner's default copy. Unlike
# courses/prizes, this exact copy was never in translations.py (it's
# newer custom text), so there's no existing source to backfill from.
_HERO_UR_DEFAULTS = {
    'badge_text_ur':        "#1 دنیا کا معتبر ترین آن لائن قرآن انسٹیٹیوٹ",
    'heading_line1_ur':     'قرآن سیکھیں',
    'heading_prefix_ur':    'کے ساتھ',
    'heading_highlight_ur': 'عمدگی',
    'heading_line3_ur':     'کہیں سے بھی',
    'heading_line4_ur':     'دنیا میں',
    'subtitle_ur':          'تمام عمر کے افراد کے لیے تجوید، حفظ، عربی زبان اور اسلامی علوم کے ساتھ ون ٹو ون قرآن کلاسز۔',
    'btn1_text_ur':         'ابھی داخلہ لیں',
    'btn2_text_ur':         'مفت ٹرائل بک کریں',
}


def backfill_hero_urdu():
    """Fill in the hero banner's *_ur columns if they're still empty
    (a hero_content row seeded before Urdu support existed). Only
    touches the Urdu columns — never overwrites the English text or
    anything an admin may have already customised."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT badge_text_ur FROM hero_content WHERE id = 1")
    row = cur.fetchone()
    if not row or row['badge_text_ur'] != '':
        cur.close(); conn.close()
        return

    set_clause = ', '.join(f"{col} = %s" for col in _HERO_UR_DEFAULTS)
    cur.execute(
        f"UPDATE hero_content SET {set_clause} WHERE id = 1",
        tuple(_HERO_UR_DEFAULTS.values())
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


# ─────────────────────────────────────────────────────────────
#  Hero Content (homepage banner) — singleton row, id always 1
# ─────────────────────────────────────────────────────────────
def get_hero_content():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM hero_content WHERE id = 1")
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


_HERO_TEXT_COLUMNS = (
    'badge_text', 'heading_line1', 'heading_prefix', 'heading_highlight',
    'heading_line3', 'heading_line4', 'subtitle', 'btn1_text', 'btn1_link',
    'btn2_text', 'btn2_link',
    'badge_text_ur', 'heading_line1_ur', 'heading_prefix_ur',
    'heading_highlight_ur', 'heading_line3_ur', 'heading_line4_ur',
    'subtitle_ur', 'btn1_text_ur', 'btn2_text_ur',
)


def update_hero_content(data, image_url=None):
    """Upsert the singleton hero_content row. `image_url` is passed
    separately (rather than always overwritten from `data`) so the
    caller can keep the existing image when no new one was uploaded.
    `data` should have every key in _HERO_TEXT_COLUMNS (missing keys
    default to '')."""
    conn = get_conn()
    cur  = conn.cursor()
    cols = ', '.join(_HERO_TEXT_COLUMNS)
    set_clause = ', '.join(f"{c} = EXCLUDED.{c}" for c in _HERO_TEXT_COLUMNS)
    placeholders = ', '.join(['%s'] * len(_HERO_TEXT_COLUMNS))
    cur.execute(
        f"""INSERT INTO hero_content (id, {cols}, image_url, updated_at)
           VALUES (1, {placeholders}, %s, NOW())
           ON CONFLICT (id) DO UPDATE SET
             {set_clause}, image_url = EXCLUDED.image_url, updated_at = NOW()""",
        tuple(data.get(c, '') for c in _HERO_TEXT_COLUMNS) + (image_url,)
    )
    conn.commit(); cur.close(); conn.close()


# ─────────────────────────────────────────────────────────────
#  Courses (homepage grid + "other courses" links + detail pages)
# ─────────────────────────────────────────────────────────────
_COURSE_COLUMNS = (
    'slug', 'sort_order', 'has_detail_page',
    'card_category', 'card_image_url', 'card_description', 'card_badges',
    'oc_title', 'oc_description',
    'category', 'icon_url', 'title', 'arabic_title', 'tagline', 'hero_badges',
    'duration', 'schedule', 'eligibility', 'certificate_val',
    'quote', 'quote_cite', 'intro',
    # Urdu counterparts — arabic_title/icon_url/card_image_url have none
    # (Quranic calligraphy and images don't change with UI language).
    'card_category_ur', 'card_description_ur', 'card_badges_ur',
    'oc_title_ur', 'oc_description_ur',
    'category_ur', 'title_ur', 'tagline_ur', 'hero_badges_ur',
    'duration_ur', 'schedule_ur', 'eligibility_ur', 'certificate_val_ur',
    'quote_ur', 'quote_cite_ur', 'intro_ur',
)

def _course_values(data):
    """Build the positional value tuple for _COURSE_COLUMNS, JSON-wrapping
    the array fields so psycopg2 stores them as JSONB correctly."""
    return (
        data['slug'], data.get('sort_order', 0), data.get('has_detail_page', True),
        data.get('card_category', ''), data.get('card_image_url'),
        data.get('card_description', ''), psycopg2.extras.Json(data.get('card_badges', [])),
        data.get('oc_title', ''), data.get('oc_description', ''),
        data.get('category', ''), data.get('icon_url'), data.get('title', ''),
        data.get('arabic_title', ''), data.get('tagline', ''),
        psycopg2.extras.Json(data.get('hero_badges', [])),
        data.get('duration', ''), data.get('schedule', ''),
        data.get('eligibility', ''), data.get('certificate_val', ''),
        data.get('quote', ''), data.get('quote_cite', ''), data.get('intro', ''),
        data.get('card_category_ur', ''), data.get('card_description_ur', ''),
        psycopg2.extras.Json(data.get('card_badges_ur', [])),
        data.get('oc_title_ur', ''), data.get('oc_description_ur', ''),
        data.get('category_ur', ''), data.get('title_ur', ''), data.get('tagline_ur', ''),
        psycopg2.extras.Json(data.get('hero_badges_ur', [])),
        data.get('duration_ur', ''), data.get('schedule_ur', ''),
        data.get('eligibility_ur', ''), data.get('certificate_val_ur', ''),
        data.get('quote_ur', ''), data.get('quote_cite_ur', ''), data.get('intro_ur', ''),
    )


def get_all_courses():
    """All courses, ordered for display — used by the homepage grid and
    the admin list (which shows every course including hidden/no-detail
    ones; the homepage template itself doesn't filter further today)."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM courses ORDER BY sort_order, id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def _attach_sections(cur, course):
    cur.execute("SELECT * FROM course_sections WHERE course_id=%s ORDER BY sort_order, id", (course['id'],))
    course['sections'] = [dict(r) for r in cur.fetchall()]
    return course


def get_course(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM courses WHERE id=%s", (cid,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    course = _attach_sections(cur, dict(row))
    cur.close(); conn.close()
    return course


def get_course_by_slug(slug):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM courses WHERE slug=%s", (slug,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None
    course = _attach_sections(cur, dict(row))
    cur.close(); conn.close()
    return course


def _replace_sections(cur, course_id, sections):
    cur.execute("DELETE FROM course_sections WHERE course_id=%s", (course_id,))
    for i, s in enumerate(sections or []):
        cur.execute(
            """INSERT INTO course_sections
                 (course_id, sort_order, block_type, list_style, heading, items, heading_ur, items_ur)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (course_id, i, s['block_type'], s.get('list_style'),
             s.get('heading', ''), psycopg2.extras.Json(s.get('items', [])),
             s.get('heading_ur', ''), psycopg2.extras.Json(s.get('items_ur', [])))
        )


def create_course(data, sections=None):
    conn = get_conn()
    cur  = conn.cursor()
    cols = ', '.join(_COURSE_COLUMNS)
    placeholders = ', '.join(['%s'] * len(_COURSE_COLUMNS))
    cur.execute(
        f"INSERT INTO courses ({cols}) VALUES ({placeholders}) RETURNING id",
        _course_values(data)
    )
    new_id = cur.fetchone()['id']
    _replace_sections(cur, new_id, sections)
    conn.commit(); cur.close(); conn.close()
    return new_id


def update_course(cid, data, sections=None):
    conn = get_conn()
    cur  = conn.cursor()
    set_clause = ', '.join(f"{c}=%s" for c in _COURSE_COLUMNS)
    cur.execute(
        f"UPDATE courses SET {set_clause}, updated_at=NOW() WHERE id=%s",
        _course_values(data) + (cid,)
    )
    _replace_sections(cur, cid, sections)
    conn.commit(); cur.close(); conn.close()


def delete_course(cid):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM courses WHERE id=%s", (cid,))
    conn.commit(); cur.close(); conn.close()


def _course_specs(t):
    """Build the course/section list resolved against one language dict
    `t` (TRANSLATIONS['en'] or TRANSLATIONS['ur']) — same shape, same
    order, same keys either way, just different text. Used both to seed
    a fresh database and, resolved once per language and merged, to
    backfill the *_ur columns on a database that already has rows."""

    def img(name):
        return f'/static/images/{name}'

    def hl(icon, h_key, p_key):
        return {'icon_url': img(f'hl_{icon}.svg'), 'heading': t[h_key], 'text': t[p_key]}

    return [
        {
            'slug': 'tajweed', 'sort_order': 0,
            'card_category': t['catQuranic'], 'card_image_url': img('courses/tajweed.webp'),
            'card_description': t['tajweedDesc'],
            'card_badges': [t['badgeAllLevels'], t['badgeOnline'], t['badgeCertificate']],
            'oc_title': t['ocTajweedTitle'], 'oc_description': t['ocTajweedP'],
            'category': t['tajweedCategory'], 'icon_url': img('course_tajweed.svg'),
            'title': t['tajweedTitle'], 'arabic_title': 'ورتل القرآن ترتيلا',
            'tagline': t['tajweedTagline'],
            'hero_badges': [t['tajweedBadge1'], t['tajweedBadge2'], t['tajweedBadge3'], t['tajweedBadge4']],
            'duration': t['tajweedDuration'], 'schedule': t['tajweedSchedule'],
            'eligibility': t['tajweedEligibility'], 'certificate_val': t['tajweedCertVal'],
            'quote': t['tajweedQuote'], 'quote_cite': t['tajweedQuoteCite'], 'intro': t['tajweedIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['tajweedLearnH'],
                 'items': [t[f'tajweedLearn{i}'] for i in range(1, 10)]},
                {'block_type': 'highlights', 'heading': t['tajweedHighH'], 'items': [
                    hl('instructor', 'tajweedHl1H', 'tajweedHl1P'),
                    hl('feedback', 'tajweedHl2H', 'tajweedHl2P'),
                    hl('global', 'tajweedHl3H', 'tajweedHl3P'),
                    hl('certificate', 'tajweedHl4H', 'tajweedHl4P'),
                ]},
                {'block_type': 'paragraphs', 'heading': t['tajweedWhyH'],
                 'items': [t['tajweedWhyP1'], t['tajweedWhyP2']]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['tajweedCertH'],
                 'items': [t[f'tajweedCert{i}'] for i in range(1, 4)]},
            ],
        },
        {
            'slug': 'quran-recitation', 'sort_order': 1,
            'card_category': t['catQuranic'], 'card_image_url': img('courses/Quran_recitation_course.webp'),
            'card_description': t['recitationDesc'],
            'card_badges': [t['badge1Year'], t['badgeAllLevels'], t['badgeNazira']],
            'oc_title': t['ocRecitationTitle'], 'oc_description': t['ocRecitationP'],
            'category': t['recitationCategory'], 'icon_url': img('course_recitation.svg'),
            'title': t['recitationTitle'], 'arabic_title': 'خيركم من تعلم القرآن وعلمه',
            'tagline': t['recitationTagline'],
            'hero_badges': [t['recitationBadge1'], t['recitationBadge2'], t['recitationBadge3'], t['recitationBadge4']],
            'duration': t['recitationDuration'], 'schedule': t['recitationSchedule'],
            'eligibility': t['recitationEligibility'], 'certificate_val': t['recitationCertVal'],
            'quote': t['recitationQuote'], 'quote_cite': t['recitationQuoteCite'], 'intro': t['recitationIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['recitationWhyH'],
                 'items': [t[f'recitationWhy{i}'] for i in range(1, 6)]},
                {'block_type': 'highlights', 'heading': t['recitationHighH'], 'items': [
                    hl('instructor', 'recitationHl1H', 'recitationHl1P'),
                    hl('curriculum', 'recitationHl2H', 'recitationHl2P'),
                    hl('interactive', 'recitationHl3H', 'recitationHl3P'),
                    hl('certificate', 'recitationHl4H', 'recitationHl4P'),
                ]},
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['recitationCoverH'],
                 'items': [t[f'recitationCover{i}'] for i in range(1, 6)]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['recitationCertH'],
                 'items': [t[f'recitationCert{i}'] for i in range(1, 4)]},
            ],
        },
        {
            'slug': 'hifz', 'sort_order': 2,
            'card_category': t['catQuranic'], 'card_image_url': img('courses/Quran_Hifz.webp'),
            'card_description': t['hifzDesc'],
            'card_badges': [t['badgeMonSat'], t['badgeAllAges'], t['badgeHafiz']],
            'oc_title': t['ocHifzTitle'], 'oc_description': t['ocHifzP'],
            'category': t['hifzCategory'], 'icon_url': img('course_hifz.svg'),
            'title': t['hifzTitle'], 'arabic_title': 'حفظ القرآن الكريم',
            'tagline': t['hifzTagline'],
            'hero_badges': [t['hifzBadge1'], t['hifzBadge2'], t['hifzBadge3'], t['hifzBadge4']],
            'duration': t['hifzDuration'], 'schedule': t['hifzSchedule'],
            'eligibility': t['hifzEligibility'], 'certificate_val': t['hifzCertVal'],
            'quote': t['hifzQuote'], 'quote_cite': t['hifzQuoteCite'], 'intro': t['hifzIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['hifzWhyH'],
                 'items': [t[f'hifzWhy{i}'] for i in range(1, 7)]},
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['hifzLearnH'],
                 'items': [t[f'hifzLearn{i}'] for i in range(1, 6)]},
                {'block_type': 'highlights', 'heading': t['hifzHighH'], 'items': [
                    hl('instructor', 'hifzHl1H', 'hifzHl1P'),
                    hl('curriculum', 'hifzHl2H', 'hifzHl2P'),
                    hl('feedback', 'hifzHl3H', 'hifzHl3P'),
                    hl('certificate', 'hifzHl4H', 'hifzHl4P'),
                ]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['hifzCertH'],
                 'items': [t[f'hifzCert{i}'] for i in range(1, 5)]},
            ],
        },
        {
            'slug': 'qirat', 'sort_order': 3,
            'card_category': t['catQuranic'], 'card_image_url': img('courses/Quran_Qirat_course.webp'),
            'card_description': t['qiratDesc'],
            'card_badges': [t['badgeFlexible'], t['badgeIjazah'], t['badgeAdvanced']],
            'oc_title': t['ocQiratTitle'], 'oc_description': t['ocQiratP'],
            'category': t['qiratCategory'], 'icon_url': img('course_qirat.svg'),
            'title': t['qiratTitle'], 'arabic_title': 'علم القراءات',
            'tagline': t['qiratTagline'],
            'hero_badges': [t['qiratBadge1'], t['qiratBadge2'], t['qiratBadge3'], t['qiratBadge4']],
            'duration': t['qiratDuration'], 'schedule': t['qiratSchedule'],
            'eligibility': t['qiratEligibility'], 'certificate_val': t['qiratCertVal'],
            'quote': t['qiratQuote'], 'quote_cite': t['qiratQuoteCite'], 'intro': t['qiratIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['qiratLearnH'],
                 'items': [t[f'qiratLearn{i}'] for i in range(1, 7)]},
                {'block_type': 'highlights', 'heading': t['qiratHighH'], 'items': [
                    hl('instructor', 'qiratHl1H', 'qiratHl1P'),
                    hl('curriculum', 'qiratHl2H', 'qiratHl2P'),
                    hl('feedback', 'qiratHl3H', 'qiratHl3P'),
                    hl('certificate', 'qiratHl4H', 'qiratHl4P'),
                ]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['qiratCertH'],
                 'items': [t[f'qiratCert{i}'] for i in range(1, 6)]},
            ],
        },
        {
            'slug': 'arabic', 'sort_order': 4,
            'card_category': t['catLanguage'], 'card_image_url': img('courses/Arabic_Speaking_Course.webp'),
            'card_description': t['arabicDesc'],
            'card_badges': [t['badge3Months'], t['badgeBeginner'], t['badge5xWeek']],
            'oc_title': t['ocArabicTitle'], 'oc_description': t['ocArabicP'],
            'category': t['arabicCategory'], 'icon_url': img('course_arabic.svg'),
            'title': t['arabicTitle'], 'arabic_title': 'تعلم اللغة العربية',
            'tagline': t['arabicTagline'],
            'hero_badges': [t['arabicBadge1'], t['arabicBadge2'], t['arabicBadge3'], t['arabicBadge4']],
            'duration': t['arabicDuration'], 'schedule': t['arabicSchedule'],
            'eligibility': t['arabicEligibility'], 'certificate_val': t['arabicCertVal'],
            'quote': t['arabicQuote'], 'quote_cite': t['arabicQuoteCite'], 'intro': t['arabicIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['arabicLearnH'],
                 'items': [t[f'arabicLearn{i}'] for i in range(1, 7)]},
                {'block_type': 'highlights', 'heading': t['arabicHighH'], 'items': [
                    hl('instructor', 'arabicHl1H', 'arabicHl1P'),
                    hl('interactive', 'arabicHl2H', 'arabicHl2P'),
                    hl('curriculum', 'arabicHl3H', 'arabicHl3P'),
                    hl('certificate', 'arabicHl4H', 'arabicHl4P'),
                ]},
                {'block_type': 'paragraphs', 'heading': t['arabicWhyH'],
                 'items': [t['arabicWhyP1'], t['arabicWhyP2']]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['arabicCertH'],
                 'items': [t[f'arabicCert{i}'] for i in range(1, 5)]},
            ],
        },
        {
            'slug': 'urdu', 'sort_order': 5,
            'card_category': t['catLanguage'], 'card_image_url': img('courses/Urdu_language.webp'),
            'card_description': t['urduDesc'],
            'card_badges': [t['badgeTueWed'], t['badgeAllLevels'], t['badgeCertificate']],
            'oc_title': t['ocUrduTitle'], 'oc_description': t['ocUrduP'],
            'category': t['urduCategory'], 'icon_url': img('course_urdu.svg'),
            'title': t['urduTitle'], 'arabic_title': 'زبان اردو',
            'tagline': t['urduTagline'],
            'hero_badges': [t['urduBadge1'], t['urduBadge2'], t['urduBadge3'], t['urduBadge4']],
            'duration': t['urduDuration'], 'schedule': t['urduSchedule'],
            'eligibility': t['urduEligibility'], 'certificate_val': t['urduCertVal'],
            'quote': t['urduQuote'], 'quote_cite': t['urduQuoteCite'], 'intro': t['urduIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['urduWhyH'],
                 'items': [t[f'urduWhy{i}'] for i in range(1, 6)]},
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['urduLearnH'],
                 'items': [t[f'urduLearn{i}'] for i in range(1, 6)]},
                {'block_type': 'highlights', 'heading': t['urduHighH'], 'items': [
                    hl('instructor', 'urduHl1H', 'urduHl1P'),
                    hl('curriculum', 'urduHl2H', 'urduHl2P'),
                    hl('feedback', 'urduHl3H', 'urduHl3P'),
                    hl('certificate', 'urduHl4H', 'urduHl4P'),
                ]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['urduCertH'],
                 'items': [t[f'urduCert{i}'] for i in range(1, 5)]},
            ],
        },
        {
            'slug': 'english', 'sort_order': 6,
            'card_category': t['catLanguage'], 'card_image_url': img('courses/English_course.webp'),
            'card_description': t['englishDesc'],
            'card_badges': [t['badge3Months'], t['badgeBeginner'], t['badge5xWeek']],
            'oc_title': t['ocEnglishTitle'], 'oc_description': t['ocEnglishP'],
            'category': t['englishCategory'], 'icon_url': img('course_english.svg'),
            'title': t['englishTitle'], 'arabic_title': 'تعلم اللغة الإنكليزية',
            'tagline': t['englishTagline'],
            'hero_badges': [t['englishBadge1'], t['englishBadge2'], t['englishBadge3'], t['englishBadge4']],
            'duration': t['englishDuration'], 'schedule': t['englishSchedule'],
            'eligibility': t['englishEligibility'], 'certificate_val': t['englishCertVal'],
            'quote': t['englishQuote'], 'quote_cite': t['englishQuoteCite'], 'intro': t['englishIntro'],
            'sections': [
                {'block_type': 'bullets', 'list_style': 'learn-list', 'heading': t['englishLearnH'],
                 'items': [t[f'englishLearn{i}'] for i in range(1, 7)]},
                {'block_type': 'highlights', 'heading': t['englishHighH'], 'items': [
                    hl('instructor', 'englishHl1H', 'englishHl1P'),
                    hl('interactive', 'englishHl2H', 'englishHl2P'),
                    hl('curriculum', 'englishHl3H', 'englishHl3P'),
                    hl('certificate', 'englishHl4H', 'englishHl4P'),
                ]},
                {'block_type': 'paragraphs', 'heading': t['englishWhyH'],
                 'items': [t['englishWhyP1'], t['englishWhyP2']]},
                {'block_type': 'bullets', 'list_style': 'detail-list', 'heading': t['englishCertH'],
                 'items': [t[f'englishCert{i}'] for i in range(1, 5)]},
            ],
        },
        {
            # Homepage-only teaser card — no detail page, matches the
            # original .course-card--no-link special case exactly.
            'slug': 'academic-subjects', 'sort_order': 7, 'has_detail_page': False,
            'card_category': t['catAcademic'], 'card_image_url': img('courses/Academic_Subjects.webp'),
            'card_description': t['academicDesc'],
            'card_badges': [t['badgeMaths'], t['badgeScience'], t['badgeAllAges']],
            'title': t['academicTitle'],
        },
    ]


_COURSE_UR_FIELD_MAP = {
    'card_category': 'card_category_ur', 'card_description': 'card_description_ur',
    'card_badges': 'card_badges_ur', 'oc_title': 'oc_title_ur',
    'oc_description': 'oc_description_ur', 'category': 'category_ur',
    'title': 'title_ur', 'tagline': 'tagline_ur', 'hero_badges': 'hero_badges_ur',
    'duration': 'duration_ur', 'schedule': 'schedule_ur',
    'eligibility': 'eligibility_ur', 'certificate_val': 'certificate_val_ur',
    'quote': 'quote_ur', 'quote_cite': 'quote_cite_ur', 'intro': 'intro_ur',
}


def _merge_course_langs(en_courses, ur_courses):
    """Zip the English and Urdu resolutions of _course_specs() (same
    order, same slugs) into one list of dicts carrying both — the
    en_course's own fields plus a "<field>_ur" for each translatable
    one, and per-section heading_ur/items_ur merged the same way
    (highlight items keep the English icon_url, just translate heading/text)."""
    merged = []
    for en_c, ur_c in zip(en_courses, ur_courses):
        assert en_c['slug'] == ur_c['slug'], f"course order mismatch: {en_c['slug']} vs {ur_c['slug']}"
        c = dict(en_c)
        for en_field, ur_field in _COURSE_UR_FIELD_MAP.items():
            if en_field in ur_c:
                c[ur_field] = ur_c[en_field]

        en_sections = en_c.get('sections', [])
        ur_sections = ur_c.get('sections', [])
        sections = []
        for en_s, ur_s in zip(en_sections, ur_sections):
            s = dict(en_s)
            s['heading_ur'] = ur_s.get('heading', '')
            if en_s['block_type'] == 'highlights':
                s['items_ur'] = [
                    {'icon_url': ei['icon_url'], 'heading': ui.get('heading', ''), 'text': ui.get('text', '')}
                    for ei, ui in zip(en_s.get('items', []), ur_s.get('items', []))
                ]
            else:
                s['items_ur'] = ur_s.get('items', [])
            sections.append(s)
        if 'sections' in en_c:
            c['sections'] = sections
        merged.append(c)
    return merged


def seed_courses():
    """One-time migration: populate `courses`/`course_sections` with the
    exact content that used to be hard-coded in the 7 course_*.html pages
    (plus the link-less "Academic Subjects" homepage card) — English from
    the original static text, Urdu from the matching translations.py
    entries that page used to read from before it was hard-coded English
    only in the database. Runs only if the courses table is empty."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM courses")
    if cur.fetchone()['cnt'] > 0:
        cur.close(); conn.close()
        return

    from translations import TRANSLATIONS
    courses = _merge_course_langs(_course_specs(TRANSLATIONS['en']), _course_specs(TRANSLATIONS['ur']))

    for c in courses:
        sections = c.pop('sections', [])
        cur.execute(
            f"INSERT INTO courses ({', '.join(_COURSE_COLUMNS)}) VALUES ({', '.join(['%s'] * len(_COURSE_COLUMNS))}) RETURNING id",
            _course_values(c)
        )
        new_id = cur.fetchone()['id']
        _replace_sections(cur, new_id, sections)

    conn.commit()
    cur.close()
    conn.close()


def backfill_course_urdu():
    """For courses seeded before Urdu support existed (title_ur still
    empty), fill in every *_ur column — matched by slug — from the same
    translations.py source seed_courses() itself uses. Safe to run
    every startup: a no-op once every course has its Urdu text."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM courses WHERE title_ur = ''")
    if cur.fetchone()['cnt'] == 0:
        cur.close(); conn.close()
        return

    from translations import TRANSLATIONS
    courses = _merge_course_langs(_course_specs(TRANSLATIONS['en']), _course_specs(TRANSLATIONS['ur']))
    ur_cols = list(_COURSE_UR_FIELD_MAP.values())

    for c in courses:
        cur.execute("SELECT id FROM courses WHERE slug = %s", (c['slug'],))
        row = cur.fetchone()
        if not row:
            continue  # an admin-added course with no entry in this seed list
        course_id = row['id']

        set_clause = ', '.join(f"{col} = %s" for col in ur_cols)
        values = []
        for col in ur_cols:
            v = c.get(col, [] if col.endswith('badges_ur') else '')
            values.append(psycopg2.extras.Json(v) if col.endswith('badges_ur') else v)
        cur.execute(f"UPDATE courses SET {set_clause} WHERE id = %s", tuple(values) + (course_id,))

        cur.execute("SELECT id FROM course_sections WHERE course_id = %s ORDER BY sort_order, id", (course_id,))
        sec_rows = cur.fetchall()
        for sec_row, sec_data in zip(sec_rows, c.get('sections', [])):
            cur.execute(
                "UPDATE course_sections SET heading_ur = %s, items_ur = %s WHERE id = %s",
                (sec_data.get('heading_ur', ''), psycopg2.extras.Json(sec_data.get('items_ur', [])), sec_row['id'])
            )

    conn.commit()
    cur.close()
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Prizes & Recognition (competitions page)
# ─────────────────────────────────────────────────────────────
def get_prizes_section():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM prizes_section WHERE id = 1")
    row = cur.fetchone()
    cur.close(); conn.close()
    return dict(row) if row else None


def update_prizes_section(data):
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """INSERT INTO prizes_section
             (id, tag, heading, heading_span, subtitle,
              tag_ur, heading_ur, heading_span_ur, subtitle_ur, updated_at)
           VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
           ON CONFLICT (id) DO UPDATE SET
             tag = EXCLUDED.tag, heading = EXCLUDED.heading,
             heading_span = EXCLUDED.heading_span, subtitle = EXCLUDED.subtitle,
             tag_ur = EXCLUDED.tag_ur, heading_ur = EXCLUDED.heading_ur,
             heading_span_ur = EXCLUDED.heading_span_ur, subtitle_ur = EXCLUDED.subtitle_ur,
             updated_at = NOW()""",
        (data['tag'], data['heading'], data['heading_span'], data['subtitle'],
         data.get('tag_ur', ''), data.get('heading_ur', ''),
         data.get('heading_span_ur', ''), data.get('subtitle_ur', ''))
    )
    conn.commit(); cur.close(); conn.close()


def get_all_prizes():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT * FROM prizes ORDER BY sort_order, id")
    rows = cur.fetchall()
    cur.close(); conn.close()
    return [dict(r) for r in rows]


def replace_all_prizes(prizes):
    """Atomically replace the whole prize-card list (same pattern as a
    course's sections) — simplest correct way to let one form submit
    add/remove/reorder all at once."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM prizes")
    for i, p in enumerate(prizes or []):
        cur.execute(
            """INSERT INTO prizes (sort_order, variant, medal_icon, heading, items, heading_ur, items_ur)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (i, p.get('variant', 'gold'), p.get('medal_icon', ''),
             p.get('heading', ''), psycopg2.extras.Json(p.get('items', [])),
             p.get('heading_ur', ''), psycopg2.extras.Json(p.get('items_ur', [])))
        )
    conn.commit(); cur.close(); conn.close()


def _prizes_section_spec(t):
    return {
        'tag': t['compPrizesTag'], 'heading': t['compPrizesH2'],
        'heading_span': t['compPrizesH2Span'], 'subtitle': t['compPrizesSub'],
    }


def _prize_specs(t):
    return [
        {'variant': 'gold', 'medal_icon': '🥇', 'heading': t['compPrize1H'],
         'items': [t[f'compPrize1Li{i}'] for i in range(1, 6)]},
        {'variant': 'silver', 'medal_icon': '🥈', 'heading': t['compPrize2H'],
         'items': [t[f'compPrize2Li{i}'] for i in range(1, 5)]},
        {'variant': 'bronze', 'medal_icon': '🥉', 'heading': t['compPrize3H'],
         'items': [t[f'compPrize3Li{i}'] for i in range(1, 4)]},
        {'variant': 'part', 'medal_icon': '🏫', 'heading': t['compPrize4H'],
         'items': [t[f'compPrize4Li{i}'] for i in range(1, 4)]},
    ]


def seed_prizes():
    """One-time migration of the "Prizes & Recognition" section from its
    original hard-coded translations.py copy (English + Urdu) — runs
    only if empty."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM prizes_section")
    section_empty = cur.fetchone()['cnt'] == 0
    cur.execute("SELECT COUNT(*) AS cnt FROM prizes")
    prizes_empty = cur.fetchone()['cnt'] == 0
    cur.close(); conn.close()

    if not (section_empty or prizes_empty):
        return

    from translations import TRANSLATIONS
    en, ur = TRANSLATIONS['en'], TRANSLATIONS['ur']

    if section_empty:
        en_sec, ur_sec = _prizes_section_spec(en), _prizes_section_spec(ur)
        update_prizes_section({
            **en_sec,
            'tag_ur': ur_sec['tag'], 'heading_ur': ur_sec['heading'],
            'heading_span_ur': ur_sec['heading_span'], 'subtitle_ur': ur_sec['subtitle'],
        })

    if prizes_empty:
        en_prizes, ur_prizes = _prize_specs(en), _prize_specs(ur)
        merged = []
        for ep, up in zip(en_prizes, ur_prizes):
            merged.append({**ep, 'heading_ur': up['heading'], 'items_ur': up['items']})
        replace_all_prizes(merged)


def backfill_prizes_urdu():
    """Fill in *_ur columns for a prizes_section/prizes seeded before
    Urdu support existed. Safe to run every startup."""
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT heading_ur FROM prizes_section WHERE id = 1")
    row = cur.fetchone()
    section_needs_backfill = row is not None and row['heading_ur'] == ''
    cur.execute("SELECT COUNT(*) AS cnt FROM prizes WHERE heading_ur = ''")
    prizes_need_backfill = cur.fetchone()['cnt'] > 0

    if not (section_needs_backfill or prizes_need_backfill):
        cur.close(); conn.close()
        return

    from translations import TRANSLATIONS
    en, ur = TRANSLATIONS['en'], TRANSLATIONS['ur']

    if section_needs_backfill:
        ur_sec = _prizes_section_spec(ur)
        cur.execute(
            """UPDATE prizes_section SET tag_ur=%s, heading_ur=%s, heading_span_ur=%s, subtitle_ur=%s
               WHERE id = 1""",
            (ur_sec['tag'], ur_sec['heading'], ur_sec['heading_span'], ur_sec['subtitle'])
        )

    if prizes_need_backfill:
        en_prizes, ur_prizes = _prize_specs(en), _prize_specs(ur)
        ur_by_variant = {p['variant']: p for p in ur_prizes}
        cur.execute("SELECT id, variant FROM prizes ORDER BY sort_order, id")
        for row in cur.fetchall():
            up = ur_by_variant.get(row['variant'])
            if not up:
                continue  # an admin-added card with no matching seed entry
            cur.execute(
                "UPDATE prizes SET heading_ur=%s, items_ur=%s WHERE id=%s",
                (up['heading'], psycopg2.extras.Json(up['items']), row['id'])
            )

    conn.commit()
    cur.close()
    conn.close()
