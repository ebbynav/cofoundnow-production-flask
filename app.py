import pyrebase
import datetime
import json
import firebase_admin
from flask import Flask, render_template, request, redirect, url_for, session
from flask_session import Session
from firebase_admin import credentials, storage, firestore, auth

from werkzeug.datastructures import FileStorage

config = {
  "apiKey": "",
  "authDomain": "",
  "databaseURL": "",
  "projectId": "",
  "storageBucket": "",
  "messagingSenderId": "",
  "appId": "",
  "measurementId": "",
    
  "databaseURL": "",
    "type": "",
  "private_key_id": "",
  "private_key": "",
  "client_id": "",
    "client_email": "",
  "auth_uri": "",
  "token_uri": "",
  "auth_provider_x509_cert_url": "",
  "client_x509_cert_url": ""
}

cred = credentials.Certificate({
    "type": "service_account",
    "project_id": config["projectId"],
    "private_key_id": config["private_key_id"],
    "private_key": config["private_key"],
    "client_email": config["client_email"],
    "client_id": config["client_id"],
    "auth_uri": config["auth_uri"],
    "token_uri": config["token_uri"],
    "auth_provider_x509_cert_url": config["auth_provider_x509_cert_url"],
    "client_x509_cert_url": config["client_x509_cert_url"]
})

firebase_admin.initialize_app(cred, {
    'storageBucket': config["storageBucket"],
})
bucket = storage.bucket()

firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
db = firestore.client()

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

def store_user_info(uid, firstname, lastname, email):
    user_ref = db.collection('users').document(uid)
    user_ref.set({
        'firstname': firstname,
        'lastname': lastname,
        'fullname': firstname + ' ' + lastname,
        'email': email,
        'created_at': datetime.datetime.now().strftime('%d/%m/%Y %I:%M:%S %p IST%z'),
})
    
def getname(uid):
    user_ref = db.collection('users').document(uid)
    user = user_ref.get()
    if user.exists:
        return user.to_dict()['fullname']
    else:
        return "User not found"
    
def upload_file_to_firebase(file):
    filename = file.filename
    blob = bucket.blob(filename)
    blob.upload_from_file(file)
    return blob.public_url


@app.route('/')
def index():
    if 'email' in session:
        return redirect(url_for('feed'))
    else:
        return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'email' in session:
        return redirect(url_for('feed'))
    else:
        if request.method == "GET":
            return render_template('login.html')
        if request.method == "POST":
            email = request.form['email']
            password = request.form['password']
            try:
                try:
                    user = auth.sign_in_with_email_and_password(email, password)
                    if not auth.get_account_info(user['idToken'])['users'][0]['emailVerified']:
                        return render_template('login.html', error="Please verify your email")
                except:
                    return render_template('login.html', error="Invalid email or password")
                session['email'] = email
                return redirect(url_for('feed'))
            except:
                return render_template('login.html', error="Invalid email or password")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "GET":
        return render_template('signup.html')
    if request.method == "POST":
        email = request.form['email']
        firstname = request.form['first_name']
        lastname = request.form['last_name']
        check_password = request.form['password']
        check_confirm_password = request.form['confirm_password']

        if check_password != check_confirm_password:
            return render_template('signup.html', error="Passwords do not match")
        else:
            password = check_password

        if len(password) >= 6:
          try:
            user = auth.create_user_with_email_and_password(email, password)
            auth.send_email_verification(user['idToken'])

            uid = auth.get_account_info(user['idToken'])['users'][0]['localId']
            store_user_info(uid, firstname, lastname, email)

            return render_template('signup.html', error="Account created successfully")
          except:
            return render_template('signup.html', error="Account already exists")
        else:
          return render_template('signup.html', error="Password must be at least 6 characters")

@app.route('/resetpassword', methods=['GET', 'POST'])
def resetpassword():
    if request.method == "GET":
        return render_template('resetpassword.html')
    if request.method == "POST":
        email = request.form['email']
        try:
            auth.send_password_reset_email(email)
            return render_template('resetpassword.html', error="Password reset email sent successfully")
        except:
            return render_template('resetpassword.html', error="Email not found")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
    
@app.route('/create-post', methods=['GET', 'POST'])
def create_post():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'GET':
        return render_template('create-post.html')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        photo_files = request.files.getlist('photo')

        from firebase_admin import auth

        email = session.get('email')
        user = auth.get_user_by_email(email)

        uid = user.uid

        fullname = getname(uid)
        
        if not title or not description:
            return render_template('create-post.html', error='Please fill out all fields')
        
        if len(photo_files) == 1 and isinstance(photo_files[0], FileStorage) and photo_files[0].filename == '' and photo_files[0].content_type == 'application/octet-stream':
            post = {
                'title': title,
                'description': description,
                'date': datetime.datetime.now().strftime('%d/%m/%Y'),
                'name': fullname,
                'uid': uid
            }
            db.collection('posts').add(post)
            return render_template('create-post.html', error='Post created successfully')
        
        if len(photo_files) > 3:
            return render_template('create-post.html', error='You can upload up to 3 photos')
        else:
            photoUrls = []
            for photo_file in photo_files:
                if photo_file and isinstance(photo_file, FileStorage) and photo_file.filename != '':
                    if photo_file.content_length > 1 * 1024 * 1024:  # 1MB in bytes
                        return render_template('create-post.html', error='File size must be less than 1MB')
                    else:
                        if photo_file.content_type not in ['image/jpeg', 'image/png']:
                            return render_template('create-post.html', error='File type must be JPEG or PNG')
                        else:
                            photoUrl = upload_file_to_firebase(photo_file)
                            photoUrls.append(photoUrl)

            post = {
                'title': title,
                'description': description,
                'date': datetime.datetime.now().strftime('%d/%m/%Y'),
                'photos': photoUrls,
                'name': fullname,
                'uid': uid
            }
            db.collection('posts').add(post)
            return redirect(url_for('feed'))
        
@app.route('/feed')
def feed():
    if 'email' not in session:
        return redirect(url_for('login'))
    else:
        from firebase_admin import auth
        uid = auth.get_user_by_email(session.get('email')).uid
        posts = []
        for doc in db.collection('posts').stream():
            post = doc.to_dict()
            post['id'] = doc.id
            posts.append(post)
        return render_template('feed.html', posts=posts, email=session.get('email'), uid=uid)

if __name__ == '__main__':
    app.run(debug=True,port=5000)