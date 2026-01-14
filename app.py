# app.py
import os
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from io import BytesIO
import stego_utils

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB limit

ALLOWED_EXT = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/estimate', methods=['POST'])
def api_estimate():
    """
    Expects a field 'snapshot' (file blob). Returns JSON: {count: int}
    """
    if 'snapshot' not in request.files:
        return jsonify({'error': 'No snapshot provided'}), 400
    f = request.files['snapshot']
    if f.filename == '':
        return jsonify({'error': 'No file chosen'}), 400
    try:
        img_bytes = f.read()
        count = stego_utils.estimate_finger_count_from_bytes(img_bytes)
        return jsonify({'count': int(count)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/encrypt', methods=['POST'])
def api_encrypt():
    """
    form fields:
      - cover: file
      - message: text
      - passcode: text
      - gesture: integer (0-5)  OR frontend can omit and we can estimate from 'snapshot' if provided.
      - snapshot: optional file blob (if provided will be used to estimate)
    returns stego image as download
    """
    if 'cover' not in request.files:
        return jsonify({'error': 'No cover image'}), 400
    cover = request.files['cover']
    if cover.filename == '' or not allowed_file(cover.filename):
        return jsonify({'error': 'Invalid cover image'}), 400

    message = request.form.get('message','')
    passcode = request.form.get('passcode','')
    gesture = request.form.get('gesture', None)

    # If snapshot provided and gesture not specified, try to estimate
    if (gesture is None or gesture == '') and 'snapshot' in request.files:
        try:
            snap = request.files['snapshot'].read()
            gesture = stego_utils.estimate_finger_count_from_bytes(snap)
        except Exception:
            gesture = 0

    try:
        gesture = int(gesture)
    except Exception:
        gesture = 0

    if not message or not passcode:
        return jsonify({'error': 'Enter both message and passcode'}), 400

    combined_key = passcode + str(gesture)
    hashed = stego_utils.hash_password(combined_key)
    payload = hashed + message
    try:
        cover_bytes = cover.read()
        stego_bytes = stego_utils.embed_message_lsb_file(cover_bytes, payload)
        return send_file(BytesIO(stego_bytes),
                         mimetype='image/png',
                         as_attachment=True,
                         download_name='stego_encrypted.png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/decrypt', methods=['POST'])
def api_decrypt():
    """
    form fields:
      - stego: file
      - passcode: text
      - gesture: integer (0-5) OR snapshot file
    returns JSON: {success: bool, message: str}
    """
    if 'stego' not in request.files:
        return jsonify({'error':'No stego image provided'}), 400
    st = request.files['stego']
    if st.filename == '' or not allowed_file(st.filename):
        return jsonify({'error': 'Invalid stego image'}), 400

    passcode = request.form.get('passcode','')
    gesture = request.form.get('gesture', None)
    if (gesture is None or gesture == '') and 'snapshot' in request.files:
        try:
            snap = request.files['snapshot'].read()
            gesture = stego_utils.estimate_finger_count_from_bytes(snap)
        except Exception:
            gesture = 0
    try:
        gesture = int(gesture)
    except Exception:
        gesture = 0

    if not passcode:
        return jsonify({'error':'Enter passcode'}), 400
    try:
        st_bytes = st.read()
        extracted = stego_utils.extract_message_lsb_from_bytes(st_bytes)
        stored_hash = extracted[:10]
        secret_msg = extracted[10:]
        combined_key = passcode + str(gesture)
        hashed_key = stego_utils.hash_password(combined_key)
        if stored_hash == hashed_key:
            return jsonify({'success': True, 'message': secret_msg})
        else:
            return jsonify({'success': False, 'message': 'Incorrect passcode or gesture.'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
