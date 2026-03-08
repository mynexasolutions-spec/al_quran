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
    try:
        comps = DB.get_all_competitions()
    except Exception:
        comps = []
    featured = [c for c in comps if c['status'] != 'completed'][:3]
    try:
        reviews = DB.get_approved_reviews()
    except Exception:
        reviews = []
    return render_template('pages/index.html', featured_comps=featured,
                           reviews=reviews,
                           THEME_MAP=THEME_MAP, BADGE_MAP=BADGE_MAP,
                           STATUS_LABELS=STATUS_LABELS)


@app.route('/course/tajweed')
def course_tajweed():
    return render_template('pages/course_tajweed.html')


@app.route('/course/quran-recitation')
def course_quran_recitation():
    return render_template('pages/course_quran_recitation.html')


@app.route('/course/hifz')
def course_hifz():
    return render_template('pages/course_hifz.html')


@app.route('/course/qirat')
def course_qirat():
    return render_template('pages/course_qirat.html')


@app.route('/course/arabic')
def course_arabic():
    return render_template('pages/course_arabic.html')


@app.route('/course/urdu')
def course_urdu():
    return render_template('pages/course_urdu.html')


@app.route('/course/english')
def course_english():
    return render_template('pages/course_english.html')


# ═══════════════════════════════════════════════════════════════
#  Public Routes — Competitions
# ═══════════════════════════════════════════════════════════════
@app.route('/competitions')
def competitions():
    try:
        comps = DB.get_all_competitions()
    except Exception:
        comps = []
    return render_template('pages/competitions.html', competitions=comps,
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

    if not name or not email:
        flash('Name and email are required.', 'error')
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

