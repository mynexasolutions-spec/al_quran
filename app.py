from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('pages/index.html')

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

@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    # TODO: Add email sending logic here
    # name    = data.get('name', '')
    # email   = data.get('email', '')
    # phone   = data.get('phone', '')
    # course  = data.get('course', '')
    # message = data.get('message', '')
    return jsonify({'status': 'ok', 'message': "JazakAllah Khair! We will contact you within 24 hours, insha'Allah."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
