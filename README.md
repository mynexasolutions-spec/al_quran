# Al-Qur'an Global Institute — Website

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Project Structure

```
alquran_institute/
├── app.py                  # Flask backend
├── requirements.txt
├── static/
│   ├── css/
│   │   └── main.css        # All styles
│   ├── js/
│   │   └── main.js         # All JavaScript
│   └── images/
│       └── logo.png        # Place your logo here
└── templates/
    ├── base.html           # Shared layout (nav, footer)
    ├── index.html
    ├── course_tajweed.html
    ├── course_quran_recitation.html
    ├── course_hifz.html
    ├── course_qirat.html
    ├── course_arabic.html
    ├── course_urdu.html
    └── course_english.html
```

## Notes
- Place your `logo.png` inside `static/images/`
- To enable contact form emails, configure SMTP in `app.py`
