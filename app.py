import os
import io
import functools
import cloudinary
from translations import TRANSLATIONS
import cloudinary.uploader
from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, flash, send_file, abort
)
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import db as DB

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback-secret-key')

# Force browsers to revalidate static files (CSS/JS/images) on every
# request instead of caching them for hours. This app's CSS/JS gets
# edited frequently; without this, visitors can keep running an old,
# already-fixed-since-then copy of a script until they hard-refresh —
# the site would look "fixed" to us but stay broken for them.
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ── Cloudinary configuration ──────────────────────────────────
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key    = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure     = True
)

# ── Initialise DB on startup ──────────────────────────────────
with app.app_context():
    try:
        DB.init_db()
        DB.seed_competitions()
        DB.seed_hero_content()
        DB.seed_courses()
        DB.seed_prizes()
        # Backfill Urdu text for anything seeded before Urdu support
        # existed — a no-op once every row already has its Urdu columns.
        DB.backfill_hero_urdu()
        DB.backfill_course_urdu()
        DB.backfill_prizes_urdu()
    except Exception as e:
        print(f"[DB INIT WARNING] {e}")


# ═══════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'AlQuranAdmin2026')

STATUS_LABELS = {
    'upcoming':  'Upcoming',
    'ongoing':   'Ongoing',
    'completed': 'Completed',
}

# Fallback used if the DB is unreachable or the hero_content row is
# missing — keeps the homepage rendering with the original hard-coded
# copy instead of erroring out.
DEFAULT_HERO_CONTENT = {
    'badge_text':        "#1 World's Trusted Online Quran Institute",
    'heading_line1':     'Learn the Quran',
    'heading_prefix':    'with',
    'heading_highlight': 'Excellence',
    'heading_line3':     'from Anywhere',
    'heading_line4':     'in the World',
    'subtitle':          'One-to-one Quran classes with Tajweed, Hifz, Arabic language and Islamic studies for all ages.',
    'btn1_text':         'Enroll Now',
    'btn1_link':         '#courses',
    'btn2_text':         'Book Free Trial',
    'btn2_link':         'https://wa.me/919045520249',
    'image_url':         '/static/images/al-quran-banner.webp',
}

DEFAULT_PRIZES_SECTION = {
    'tag':          'Rewards',
    'heading':      'Prizes &',
    'heading_span': 'Recognition',
    'subtitle':     "We celebrate every participant's effort, with special honours for those who excel at the top.",
}

# ── Bilingual DB content: which fields have a "<field>_ur" counterpart ──
HERO_UR_FIELDS = (
    'badge_text', 'heading_line1', 'heading_prefix', 'heading_highlight',
    'heading_line3', 'heading_line4', 'subtitle', 'btn1_text', 'btn2_text',
)
COURSE_UR_FIELDS = (
    'card_category', 'card_description', 'card_badges', 'oc_title', 'oc_description',
    'category', 'title', 'tagline', 'hero_badges',
    'duration', 'schedule', 'eligibility', 'certificate_val',
    'quote', 'quote_cite', 'intro',
)
COURSE_SECTION_UR_FIELDS = ('heading', 'items')
PRIZES_SECTION_UR_FIELDS = ('tag', 'heading', 'heading_span', 'subtitle')
PRIZE_UR_FIELDS = ('heading', 'items')


def localize(raw, fields, lang):
    """Return a shallow copy of `raw` where every field in `fields` is
    swapped for its "<field>_ur" counterpart when lang == 'ur' and that
    translation is actually filled in — otherwise the English value is
    left in place. Used to turn a DB row (which always carries both
    languages, for the admin forms) into what a specific page render
    should show. `raw` may be None (falls straight through) or a dict."""
    if not raw:
        return raw
    out = dict(raw)
    if lang == 'ur':
        for f in fields:
            ur_val = raw.get(f + '_ur')
            if ur_val:  # non-empty string, or non-empty list for *_badges/items
                out[f] = ur_val
    return out


def localize_course(course, lang):
    """localize() a course dict plus each of its content-block sections."""
    if not course:
        return course
    c = localize(course, COURSE_UR_FIELDS, lang)
    if 'sections' in c:
        c['sections'] = [localize(s, COURSE_SECTION_UR_FIELDS, lang) for s in c['sections']]
    return c

THEME_MAP = {
    'teal':  'comp-top--teal',
    'gold':  'comp-top--gold',
    'green': 'comp-top--green',
    'grey':  'comp-top--grey',
}

BADGE_MAP = {
    'upcoming':  'comp-badge--upcoming',
    'ongoing':   'comp-badge--ongoing',
    'completed': 'comp-badge--completed',
}


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_nav_courses():
    """Courses with a detail page, for the navbar dropdown and footer
    link list — included on every page via navbar.html/footer.html,
    which don't otherwise have access to a route's own context."""
    try:
        lang = session.get('lang', 'en')
        courses = DB.get_all_courses()
        return {'nav_courses': [localize_course(c, lang) for c in courses if c['has_detail_page']]}
    except Exception:
        return {'nav_courses': []}


@app.context_processor
def inject_pending_reviews():
    """Inject pending review count into all templates (for admin sidebar badge)."""
    try:
        if session.get('admin_logged_in'):
            reviews = DB.get_all_reviews()
            count = sum(1 for r in reviews if r['status'] == 'pending')
            return {'pending_reviews_count': count}
    except Exception:
        pass
    return {'pending_reviews_count': 0}


@app.context_processor
def inject_translations():
    """Inject current-language translation dict (`t`) and `lang` into every template."""
    lang = session.get('lang', 'en')
    t_obj = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    # Wrap in a simple attribute-access object so templates can use t.key
    class _T(dict):
        def __getattr__(self, item):
            try:
                return self[item]
            except KeyError:
                return ''
    return {'t': _T(t_obj), 'lang': lang}


@app.route('/set-lang/<lang>')
def set_lang(lang):
    """Set the UI language via session cookie, then redirect back."""
    if lang in ('en', 'ur'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))


def _parse_tags(raw):
    """Split comma-separated tags string into cleaned list."""
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


def _build_excel(registrations, title='Registrations'):
    """Build an openpyxl workbook from a list of registration dicts."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]  # Excel sheet name max 31 chars

    # Styles
    hdr_font    = Font(bold=True, color='FFFFFF', size=11)
    hdr_fill    = PatternFill('solid', fgColor='0A3D33')
    hdr_align   = Alignment(horizontal='center', vertical='center', wrap_text=True)
    border_side = Side(style='thin', color='CCCCCC')
    cell_border = Border(left=border_side, right=border_side,
                         top=border_side, bottom=border_side)

    headers = ['#', 'Competition', 'Name', 'Email', 'Phone',
               'Age', 'Country', 'Experience', 'Notes', 'Registered At']
    col_widths = [5, 30, 22, 28, 18, 10, 18, 35, 35, 22]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font      = hdr_font
        cell.fill      = hdr_fill
        cell.alignment = hdr_align
        cell.border    = cell_border
        ws.column_dimensions[cell.column_letter].width = w

    ws.row_dimensions[1].height = 28

    alt_fill = PatternFill('solid', fgColor='F5F5F5')
    for row_idx, reg in enumerate(registrations, start=2):
        row_data = [
            row_idx - 1,
            reg.get('competition_title', ''),
            reg.get('name', ''),
            reg.get('email', ''),
            reg.get('phone', ''),
            reg.get('age', ''),
            reg.get('country', ''),
            reg.get('experience', ''),
            reg.get('notes', ''),
            str(reg.get('created_at', ''))[:19],
        ]
        for col_idx, val in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = cell_border
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            if row_idx % 2 == 0:
                cell.fill = alt_fill
        ws.row_dimensions[row_idx].height = 20

    return wb


# ═══════════════════════════════════════════════════════════════
#  Public Routes — Courses
# ═══════════════════════════════════════════════════════════════
@app.route('/')
def index():
    lang = session.get('lang', 'en')
    try:
        comps = DB.get_all_competitions()
    except Exception:
        comps = []
    featured = [c for c in comps if c['status'] != 'completed'][:3]
    try:
        reviews = DB.get_approved_reviews()
    except Exception:
        reviews = []
    try:
        hero = localize(DB.get_hero_content() or DEFAULT_HERO_CONTENT, HERO_UR_FIELDS, lang)
    except Exception:
        hero = DEFAULT_HERO_CONTENT
    try:
        courses = [localize_course(c, lang) for c in DB.get_all_courses()]
    except Exception:
        courses = []
    return render_template('pages/index.html', featured_comps=featured,
                           reviews=reviews, hero=hero, courses=courses,
                           THEME_MAP=THEME_MAP, BADGE_MAP=BADGE_MAP,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/course/<slug>')
def course_detail(slug):
    lang = session.get('lang', 'en')
    course = DB.get_course_by_slug(slug)
    if not course or not course['has_detail_page']:
        abort(404)
    try:
        all_courses = DB.get_all_courses()
    except Exception:
        all_courses = []
    other_courses = [localize_course(c, lang) for c in all_courses
                     if c['id'] != course['id'] and c['has_detail_page']]
    return render_template('pages/course_detail.html',
                           course=localize_course(course, lang), other_courses=other_courses)


@app.route('/team')
def team():
    return render_template('pages/team.html')


# ═══════════════════════════════════════════════════════════════
#  Public Routes — Competitions
# ═══════════════════════════════════════════════════════════════
@app.route('/competitions')
def competitions():
    lang = session.get('lang', 'en')
    try:
        comps = DB.get_all_competitions()
    except Exception:
        comps = []
    try:
        prizes_section = localize(DB.get_prizes_section() or DEFAULT_PRIZES_SECTION, PRIZES_SECTION_UR_FIELDS, lang)
    except Exception:
        prizes_section = DEFAULT_PRIZES_SECTION
    try:
        prizes = [localize(p, PRIZE_UR_FIELDS, lang) for p in DB.get_all_prizes()]
    except Exception:
        prizes = []
    return render_template('pages/competitions.html', competitions=comps,
                           prizes_section=prizes_section, prizes=prizes,
                           THEME_MAP=THEME_MAP, BADGE_MAP=BADGE_MAP,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/competitions/<int:cid>/register', methods=['GET'])
def register_page(cid):
    comp = DB.get_competition(cid)
    if not comp:
        abort(404)
    if comp['status'] == 'completed':
        flash('This competition has ended. Registration is closed.', 'warning')
        return redirect(url_for('competitions'))
    return render_template('pages/register.html', competition=comp)


@app.route('/competitions/<int:cid>/register', methods=['POST'])
def register_submit(cid):
    comp = DB.get_competition(cid)
    if not comp or comp['status'] == 'completed':
        abort(404)

    name  = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()

    if not name or not phone:
        flash('Name and phone number are required.', 'error')
        return redirect(url_for('competitions') + '#all-competitions')

    DB.create_registration({
        'competition_id':    cid,
        'competition_title': comp['title'],
        'name':       name,
        'email':      email,
        'phone':      request.form.get('phone', '').strip(),
        'age':        request.form.get('age', '').strip(),
        'country':    request.form.get('country', '').strip(),
        'experience': request.form.get('experience', '').strip(),
        'notes':      request.form.get('notes', '').strip(),
    })

    flash(f'JazakAllah Khair! Your registration for "{comp["title"]}" has been received. We\'ll be in touch soon, insha\'Allah.', 'success')
    return redirect(url_for('competitions') + '#all-competitions')


@app.route('/competitions/<int:cid>/register/success')
def register_success(cid):
    comp = DB.get_competition(cid)
    if not comp:
        abort(404)
    return render_template('pages/register.html', competition=comp, success=True)


# ═══════════════════════════════════════════════════════════════
#  Contact Form (existing)
# ═══════════════════════════════════════════════════════════════
@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    return jsonify({'status': 'ok',
                    'message': "JazakAllah Khair! We will contact you within 24 hours, insha'Allah."})


# ═══════════════════════════════════════════════════════════════
#  Public — Review Submission
# ═══════════════════════════════════════════════════════════════
@app.route('/reviews/submit', methods=['POST'])
def review_submit():
    name  = request.form.get('name', '').strip()
    text  = request.form.get('review_text', '').strip()
    if not name or not text:
        flash('Name and review text are required.', 'error')
        return redirect(url_for('index') + '#reviews')
    try:
        rating = max(1, min(5, int(request.form.get('rating', 5))))
    except (ValueError, TypeError):
        rating = 5
    DB.create_review({
        'name':        name,
        'location':    request.form.get('location', '').strip(),
        'course':      request.form.get('course', '').strip(),
        'rating':      rating,
        'review_text': text,
    })
    flash("JazakAllah Khair! Your review has been submitted and will appear after admin approval, insha'Allah.", 'success')
    return redirect(url_for('index') + '#reviews')


# ═══════════════════════════════════════════════════════════════
#  Admin — Authentication
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_competitions'))

    error = None
    if request.method == 'POST':
        if (request.form.get('username') == ADMIN_USERNAME and
                request.form.get('password') == ADMIN_PASSWORD):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_competitions'))
        error = 'Invalid username or password.'

    return render_template('admin/login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/')
@admin_required
def admin_dashboard():
    return redirect(url_for('admin_competitions'))


# ═══════════════════════════════════════════════════════════════
#  Admin — Competitions
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/competitions')
@admin_required
def admin_competitions():
    comps = DB.get_all_competitions()
    # attach registration counts
    for c in comps:
        c['reg_count'] = DB.get_registration_count(c['id'])
    total_regs = sum(c['reg_count'] for c in comps)
    return render_template('admin/competitions_list.html',
                           competitions=comps,
                           total_regs=total_regs,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/admin/competitions/new', methods=['GET', 'POST'])
@admin_required
def admin_competition_new():
    if request.method == 'POST':
        image_url = None
        if 'image' in request.files and request.files['image'].filename:
            try:
                result = cloudinary.uploader.upload(
                    request.files['image'],
                    folder='alquran/competitions',
                    transformation=[{'width': 800, 'crop': 'limit'}]
                )
                image_url = result.get('secure_url')
            except Exception as e:
                flash(f'Image upload failed: {e}', 'warning')

        DB.create_competition({
            'title':        request.form['title'],
            'category':     request.form.get('category', 'Quranic Studies'),
            'description':  request.form.get('description'),
            'date_display': request.form.get('date_display'),
            'status':       request.form.get('status', 'upcoming'),
            'location':     request.form.get('location', 'Online — Worldwide'),
            'age_group':    request.form.get('age_group', 'All Ages'),
            'prize':        request.form.get('prize'),
            'tags':         _parse_tags(request.form.get('tags', '')),
            'icon':         request.form.get('icon', '🏆'),
            'color_theme':  request.form.get('color_theme', 'teal'),
            'image_url':    image_url or request.form.get('image_url'),
        })
        flash('Competition created successfully!', 'success')
        return redirect(url_for('admin_competitions'))

    return render_template('admin/competition_form.html',
                           action='new', competition=None,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/admin/competitions/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_competition_edit(cid):
    comp = DB.get_competition(cid)
    if not comp:
        abort(404)

    if request.method == 'POST':
        image_url = comp.get('image_url')
        if 'image' in request.files and request.files['image'].filename:
            try:
                result = cloudinary.uploader.upload(
                    request.files['image'],
                    folder='alquran/competitions',
                    transformation=[{'width': 800, 'crop': 'limit'}]
                )
                image_url = result.get('secure_url')
            except Exception as e:
                flash(f'Image upload failed: {e}', 'warning')

        DB.update_competition(cid, {
            'title':        request.form['title'],
            'category':     request.form.get('category', 'Quranic Studies'),
            'description':  request.form.get('description'),
            'date_display': request.form.get('date_display'),
            'status':       request.form.get('status', 'upcoming'),
            'location':     request.form.get('location', 'Online — Worldwide'),
            'age_group':    request.form.get('age_group', 'All Ages'),
            'prize':        request.form.get('prize'),
            'tags':         _parse_tags(request.form.get('tags', '')),
            'icon':         request.form.get('icon', '🏆'),
            'color_theme':  request.form.get('color_theme', 'teal'),
            'image_url':    image_url or request.form.get('image_url'),
        })
        flash('Competition updated successfully!', 'success')
        return redirect(url_for('admin_competitions'))

    # Prepare tags as comma string for the form
    comp['tags_str'] = ', '.join(comp.get('tags') or [])
    return render_template('admin/competition_form.html',
                           action='edit', competition=comp,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/admin/competitions/<int:cid>/status', methods=['POST'])
@admin_required
def admin_competition_status(cid):
    new_status = request.form.get('status')
    if new_status not in STATUS_LABELS:
        return jsonify({'error': 'Invalid status'}), 400
    DB.update_competition_status(cid, new_status)
    return jsonify({'ok': True, 'status': new_status,
                    'label': STATUS_LABELS[new_status]})


@app.route('/admin/competitions/<int:cid>/delete', methods=['POST'])
@admin_required
def admin_competition_delete(cid):
    DB.delete_competition(cid)
    flash('Competition deleted.', 'info')
    return redirect(url_for('admin_competitions'))


# ═══════════════════════════════════════════════════════════════
#  Admin — Registrations
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/registrations')
@admin_required
def admin_registrations():
    cid   = request.args.get('competition_id', type=int)
    regs  = DB.get_all_registrations(competition_id=cid)
    comps = DB.get_all_competitions()
    selected_comp = DB.get_competition(cid) if cid else None
    return render_template('admin/registrations.html',
                           registrations=regs,
                           competitions=comps,
                           selected_comp=selected_comp,
                           selected_id=cid)


@app.route('/admin/registrations/<int:rid>/delete', methods=['POST'])
@admin_required
def admin_registration_delete(rid):
    cid = request.form.get('competition_id', type=int)
    DB.delete_registration(rid)
    flash('Registration deleted.', 'info')
    if cid:
        return redirect(url_for('admin_registrations', competition_id=cid))
    return redirect(url_for('admin_registrations'))


@app.route('/admin/registrations/export')
@admin_required
def admin_registrations_export():
    cid   = request.args.get('competition_id', type=int)
    regs  = DB.get_all_registrations(competition_id=cid)

    if cid:
        comp = DB.get_competition(cid)
        sheet_title = (comp['title'][:28] if comp else 'Competition')
        filename    = f"registrations_{cid}.xlsx"
    else:
        sheet_title = 'All Registrations'
        filename    = 'all_registrations.xlsx'

    wb = _build_excel(regs, title=sheet_title)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


# ═══════════════════════════════════════════════════════════════
#  Admin — Reviews Moderation
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/reviews')
@admin_required
def admin_reviews():
    reviews = DB.get_all_reviews()
    pending = [r for r in reviews if r['status'] == 'pending']
    return render_template('admin/reviews.html',
                           reviews=reviews,
                           pending_count=len(pending),
                           pending_reviews_count=len(pending))


@app.route('/admin/reviews/<int:rid>/status', methods=['POST'])
@admin_required
def admin_review_status(rid):
    status = request.form.get('status')
    if status not in ('approved', 'rejected', 'pending'):
        return jsonify({'error': 'invalid status'}), 400
    DB.update_review_status(rid, status)
    return jsonify({'ok': True, 'status': status})


@app.route('/admin/reviews/<int:rid>/delete', methods=['POST'])
@admin_required
def admin_review_delete(rid):
    DB.delete_review(rid)
    flash('Review deleted.', 'success')
    return redirect(url_for('admin_reviews'))


# ═══════════════════════════════════════════════════════════════
#  Admin — Homepage Hero Banner
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/hero', methods=['GET', 'POST'])
@admin_required
def admin_hero():
    hero = DB.get_hero_content() or DEFAULT_HERO_CONTENT

    if request.method == 'POST':
        image_url = hero.get('image_url')
        if 'image' in request.files and request.files['image'].filename:
            try:
                result = cloudinary.uploader.upload(
                    request.files['image'],
                    folder='alquran/hero',
                    transformation=[{'width': 1600, 'crop': 'limit'}]
                )
                image_url = result.get('secure_url')
            except Exception as e:
                flash(f'Image upload failed: {e}', 'warning')
        elif request.form.get('image_url', '').strip():
            image_url = request.form['image_url'].strip()

        hero_columns = HERO_UR_FIELDS + tuple(f + '_ur' for f in HERO_UR_FIELDS) + ('btn1_link', 'btn2_link')
        data = {c: request.form.get(c, '').strip() for c in hero_columns}
        DB.update_hero_content(data, image_url=image_url)

        flash('Homepage banner updated successfully!', 'success')
        return redirect(url_for('admin_hero'))

    return render_template('admin/hero_form.html', hero=hero)


# ═══════════════════════════════════════════════════════════════
#  Admin — Courses
# ═══════════════════════════════════════════════════════════════
def _parse_pipe_list(raw):
    """Comma/newline list -> list of strings (badges, paragraphs, plain bullets)."""
    if not raw:
        return []
    return [line.strip() for line in raw.replace(',', '\n').splitlines() if line.strip()]


def _parse_highlight_items(raw):
    """Each non-empty line is 'icon_url | Heading | Text' -> list of dicts.
    A bare icon filename (no slash) is resolved against the shared
    static/images/ folder so admins can type e.g. 'hl_instructor.svg'."""
    items = []
    for line in (raw or '').splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        icon, heading, text = (parts + ['', '', ''])[:3]
        if icon and '/' not in icon:
            icon = f'/static/images/{icon}'
        items.append({'icon_url': icon, 'heading': heading, 'text': text})
    return items


def _parse_highlight_items_ur(raw, english_items):
    """Urdu highlight items are entered as 'Heading | Text' (no icon —
    it reuses the English item's icon at the same position, since the
    icon itself doesn't change with language)."""
    items = []
    for i, line in enumerate(line.strip() for line in (raw or '').splitlines()):
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        heading, text = (parts + ['', ''])[:2]
        icon = english_items[i]['icon_url'] if i < len(english_items) else ''
        items.append({'icon_url': icon, 'heading': heading, 'text': text})
    return items


def _sections_from_form(form):
    types       = form.getlist('section_type[]')
    headings    = form.getlist('section_heading[]')
    styles      = form.getlist('section_list_style[]')
    items       = form.getlist('section_items[]')
    headings_ur = form.getlist('section_heading_ur[]')
    items_ur    = form.getlist('section_items_ur[]')
    sections = []
    for block_type, heading, list_style, raw_items, heading_ur, raw_items_ur in zip(
            types, headings, styles, items, headings_ur, items_ur):
        heading = heading.strip()
        if block_type == 'highlights':
            parsed = _parse_highlight_items(raw_items)
            parsed_ur = _parse_highlight_items_ur(raw_items_ur, parsed)
        else:
            parsed = _parse_pipe_list(raw_items)
            parsed_ur = _parse_pipe_list(raw_items_ur)
        if not heading and not parsed:
            continue  # skip fully-empty blocks (e.g. an added-then-unused row)
        sections.append({
            'block_type': block_type,
            'list_style': list_style if block_type == 'bullets' else None,
            'heading': heading,
            'items': parsed,
            'heading_ur': heading_ur.strip(),
            'items_ur': parsed_ur,
        })
    return sections


def _course_data_from_form(form, card_image_url, icon_url):
    """Build the course data dict (English + Urdu text fields) shared by
    both the create and edit routes."""
    data = {
        'slug': form.get('slug', '').strip().lower(),
        'sort_order': form.get('sort_order', type=int) or 0,
        'has_detail_page': bool(form.get('has_detail_page')),
        'card_image_url': card_image_url,
        'icon_url': icon_url,
        'arabic_title': form.get('arabic_title', '').strip(),
    }
    for f in COURSE_UR_FIELDS:
        if f in ('card_badges', 'hero_badges'):
            data[f] = _parse_pipe_list(form.get(f, ''))
            data[f + '_ur'] = _parse_pipe_list(form.get(f + '_ur', ''))
        else:
            data[f] = form.get(f, '').strip()
            data[f + '_ur'] = form.get(f + '_ur', '').strip()
    return data


def _upload_course_image(field_name, folder, current_url, form):
    if field_name in request.files and request.files[field_name].filename:
        try:
            result = cloudinary.uploader.upload(
                request.files[field_name],
                folder=folder,
                transformation=[{'width': 1000, 'crop': 'limit'}]
            )
            return result.get('secure_url')
        except Exception as e:
            flash(f'Image upload failed: {e}', 'warning')
            return current_url
    url_field = f'{field_name}_url'
    if form.get(url_field, '').strip():
        return form[url_field].strip()
    return current_url


@app.route('/admin/courses')
@admin_required
def admin_courses():
    courses = DB.get_all_courses()
    return render_template('admin/courses_list.html', courses=courses)


@app.route('/admin/courses/new', methods=['GET', 'POST'])
@admin_required
def admin_course_new():
    if request.method == 'POST':
        card_image_url = _upload_course_image('card_image', 'alquran/courses', None, request.form)
        icon_url       = _upload_course_image('icon_image', 'alquran/courses', None, request.form)
        data = _course_data_from_form(request.form, card_image_url, icon_url)

        if not data['slug'] or not data['title']:
            flash('Slug and Title are required.', 'error')
            return render_template('admin/course_form.html', action='new', course=data, sections=_sections_from_form(request.form))

        DB.create_course(data, _sections_from_form(request.form))
        flash('Course created successfully!', 'success')
        return redirect(url_for('admin_courses'))

    return render_template('admin/course_form.html', action='new', course=None, sections=[])


@app.route('/admin/courses/<int:cid>/edit', methods=['GET', 'POST'])
@admin_required
def admin_course_edit(cid):
    course = DB.get_course(cid)
    if not course:
        abort(404)

    if request.method == 'POST':
        card_image_url = _upload_course_image('card_image', 'alquran/courses', course.get('card_image_url'), request.form)
        icon_url       = _upload_course_image('icon_image', 'alquran/courses', course.get('icon_url'), request.form)
        data = _course_data_from_form(request.form, card_image_url, icon_url)

        if not data['slug'] or not data['title']:
            flash('Slug and Title are required.', 'error')
            return render_template('admin/course_form.html', action='edit', course=dict(course, **data), sections=_sections_from_form(request.form))

        DB.update_course(cid, data, _sections_from_form(request.form))
        flash('Course updated successfully!', 'success')
        return redirect(url_for('admin_courses'))

    return render_template('admin/course_form.html', action='edit', course=course, sections=course['sections'])


@app.route('/admin/courses/<int:cid>/delete', methods=['POST'])
@admin_required
def admin_course_delete(cid):
    DB.delete_course(cid)
    flash('Course deleted.', 'info')
    return redirect(url_for('admin_courses'))


# ═══════════════════════════════════════════════════════════════
#  Admin — Prizes & Recognition (competitions page)
# ═══════════════════════════════════════════════════════════════
@app.route('/admin/prizes', methods=['GET', 'POST'])
@admin_required
def admin_prizes():
    section = DB.get_prizes_section() or DEFAULT_PRIZES_SECTION
    prizes  = DB.get_all_prizes()

    if request.method == 'POST':
        section_data = {f: request.form.get(f, '').strip() for f in PRIZES_SECTION_UR_FIELDS}
        section_data.update({f + '_ur': request.form.get(f + '_ur', '').strip() for f in PRIZES_SECTION_UR_FIELDS})
        DB.update_prizes_section(section_data)

        variants    = request.form.getlist('prize_variant[]')
        icons       = request.form.getlist('prize_icon[]')
        headings    = request.form.getlist('prize_heading[]')
        items_l     = request.form.getlist('prize_items[]')
        headings_ur = request.form.getlist('prize_heading_ur[]')
        items_ur_l  = request.form.getlist('prize_items_ur[]')
        new_prizes = []
        for variant, icon, heading, raw_items, heading_ur, raw_items_ur in zip(
                variants, icons, headings, items_l, headings_ur, items_ur_l):
            heading = heading.strip()
            items   = _parse_pipe_list(raw_items)
            if not heading and not items:
                continue  # skip an added-then-unused card
            new_prizes.append({
                'variant': variant, 'medal_icon': icon.strip(),
                'heading': heading, 'items': items,
                'heading_ur': heading_ur.strip(), 'items_ur': _parse_pipe_list(raw_items_ur),
            })
        DB.replace_all_prizes(new_prizes)

        flash('Prizes & Recognition updated successfully!', 'success')
        return redirect(url_for('admin_prizes'))

    return render_template('admin/prizes_form.html', section=section, prizes=prizes)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

