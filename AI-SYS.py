import os
import numpy as np
import tensorflow as tf
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image

# 1. Initialize the AI Model (This stays in RAM for speed)
# MobileNetV2 is perfect for humanitarian field hardware
model = MobileNetV2(weights='imagenet')

app = Flask(__name__)

# 2. IT Infrastructure & Database Configuration
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///humanitarian_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure upload folder exists on the hardware
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)

# 3. Database Schema (Records Management)
class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100))
    status = db.Column(db.String(100))
    confidence = db.Column(db.String(20))

# Create the database file if it doesn't exist
with app.app_context():
    db.create_all()

# 4. AI Logic: The "Digital Eye"
def analyze_image(img_path):
    # Standardize image for the AI (224x224 pixels)
    img = image.load_img(img_path, target_size=(224, 224))
    x = image.img_to_array(img)
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    
    # Run prediction
    preds = model.predict(x)
    label = decode_predictions(preds, top=1)[0][0]
    
    # Return (Object Name, Confidence %)
    return label[1].replace('_', ' ').title(), f"{label[2]*100:.1f}%"

# 5. Web Routes (The User Interface)
@app.route('/')
def index():
    # Show most recent assessments first
    reports = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template('index.html', reports=reports)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)

        if file:
            # Save to local storage
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Default values for fault tolerance
            object_name = "AI Processing Error"
            conf_score = "0%"
            
            try:
                # Run AI Analysis
                object_name, conf_score = analyze_image(filepath)
            except Exception as e:
                print(f"Hardware/AI Error: {e}")
            
            # Save results to the database
            new_report = Assessment(
                filename=filename, 
                status=object_name, 
                confidence=conf_score
            )
            db.session.add(new_report)
            db.session.commit()
            return redirect(url_for('index'))
            
    return render_template('upload.html')

# 6. Start the Service
if __name__ == '__main__':
    # '0.0.0.0' allows other devices on the network to connect
    app.run(debug=True, host='127.0.0.1', port=5000)