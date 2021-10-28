from flask import Flask, render_template, request, session, send_file, redirect
from flask_wtf.csrf import CSRFProtect
from datetime import datetime, timedelta
import pymysql.cursors
import os.path
import hashlib

app = Flask(__name__)
# CSRF protection
csrf = CSRFProtect(app)
# store these in environment variable so they aren't stored in plaintext
# app.secret_key should be updated periodically by the system admin in a deployment setting
app.secret_key = "FreshFit"
SALT = "FreshFitSalt"
UPLOAD_FOLDER = "static/"

conn = pymysql.connect(host="localhost",
                       port=8889,
                       user="root",
                       password="root",
                       db="FreshFit",
                       charset="utf8mb4",
                       cursorclass=pymysql.cursors.DictCursor)

# returns true if given status is current, and false if not
def get_designer_status():
    with conn.cursor() as cursor:
            query = "SELECT designer FROM user WHERE username = (%s)"
            cursor.execute(query, (session['username']))
            query_result = cursor.fetchone()
            return query_result['designer']


def update_designer_status(new_val):
    # update database
    with conn.cursor() as cursor:
        query = "UPDATE user SET designer = (%s) WHERE username = (%s)"
        cursor.execute(query, (new_val, session['username']))
        conn.commit()
    # update session cookie
    session['designer'] = new_val


def update_designer_period(period):
    with conn.cursor() as cursor:
        # check current expiration date
        query = "SELECT exp_date FROM user where username = (%s)"
        cursor.execute(query, (session['username']))
        exp_date = cursor.fetchone()['exp_date']

        if exp_date is None:
            new_date = datetime.now() + timedelta(days=31*int(period))
            
            query = "UPDATE user SET exp_date = (%s) WHERE username = (%s)"
            cursor.execute(query, (new_date, session['username']))
            conn.commit()
        else:
            new_date = exp_date + timedelta(days=31*int(period))

            query = "UPDATE user SET exp_date = (%s) WHERE username = (%s)"
            cursor.execute(query, (new_date, session['username']))
            conn.commit()


@app.route("/")
def index():
    # user is logged in 
    if "username" in session:
        session['designer'] = get_designer_status()
        return render_template("home.html", designer=session['designer'])

    return render_template("index.html")


@app.route("/register")
def register():
    return render_template("register.html")


@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        formData = request.form
        username = formData["username"]
        password = formData["password"]
        first_name = formData["firstname"]
        last_name = formData["lastname"]
        salt_pw = SALT + password
        hash_pw = hashlib.sha256(salt_pw.encode("utf-8")).hexdigest()

        try:
            with conn.cursor() as cursor:
                query = "INSERT INTO user (username, hash_pw, first_name, last_name) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hash_pw, first_name, last_name))
                conn.commit()
        except pymysql.err.IntegrityError:
            error = "Username already taken"
            return render_template("register.html", error=error)
        
        session['username'] = username
        session['designer'] = 0
        return render_template("home.html", designer=session['designer'])
    else:
        error = "Unknown error"
        return render_template("register.html", error=error)


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        formData = request.form
        username = formData["username"]
        password = formData["password"]
        salt_pw = SALT + password
        hash_pw = hashlib.sha256(salt_pw.encode("utf-8")).hexdigest()

        with conn.cursor() as cursor:
            query = "SELECT hash_pw FROM user WHERE username = %s"
            cursor.execute(query, (username))
            query_result = cursor.fetchone()
        if query_result:
            sql_pw = query_result["hash_pw"]
            if hash_pw == sql_pw:
                session['username'] = username
                session['designer'] = get_designer_status()
                return render_template("home.html", designer=session['designer'])
            else:
                error = "Incorrect password"
                return render_template("login.html", error=error)
        else:
            error = "Incorrect username"
            return render_template("login.html", error=error)
    else:
        error = "Unknown error"
        return render_template("login.html", error=error)


@app.route('/logout')
def logout():
    session.clear()
    return render_template('index.html')


@app.route('/subscribe')
def subscribe():
    # should be redundant with CSRF tokens and home page if statements, but still
    if 'username' in session:
        session['designer'] = get_designer_status()
        return render_template('subscribe.html', designer=session['designer'])

    error = "Please log in to subscribe"
    return render_template('login.html', error=error)


@app.route('/subscribe_form', methods=['POST'])
def subscribe_form():
    if request.form:
        period = request.form['period']
        update_designer_status(1)
        update_designer_period(period)

        return render_template('home.html', designer=session['designer'])
    else:
        error = "Unknown error"
        return render_template('subscribe.html', error=error)


@app.route('/explore_marketplace', methods=['GET', 'POST'])
def explore_marketplace():
	if request.method == "GET":
		with conn.cursor() as cursor:
			query = "SELECT * FROM listing"
			cursor.execute(query)
			query_result = cursor.fetchall()

	if request.method == "POST":
		name = request.form['search']
		with conn.cursor() as cursor:
			query = "SELECT * FROM listing WHERE name = %s"
			cursor.execute(query, (name))
			query_result = cursor.fetchall()

	return render_template("explore_marketplace.html", listings=query_result, designer=session['designer'])


@app.route('/static/<filename>', methods=['GET'])
def photo_view(filename):
    abs_path = os.path.abspath(UPLOAD_FOLDER+filename)
    print(abs_path)
    if os.path.isfile(abs_path):
        return send_file(abs_path, mimetype="image/jpg")
    else:
        pass


@app.route('/purchase/<id>', methods=['GET'])
def purchase(id):
    with conn.cursor() as cursor:
        query = "SELECT filepath FROM listing WHERE id = %s"
        cursor.execute(query, (id))
        abs_path = os.path.abspath(cursor.fetchone()['filepath'])
        os.remove(abs_path)

        query = "DELETE FROM listing WHERE id = %s"
        cursor.execute(query, (id))
        conn.commit()
    
    message = "Item purchased!"
    return render_template("home.html", message=message)


# @app.route('/listing_details/', methods=["GET"])
# def listing_details():
#     name = request.args.get('name')
#     user = request.args.get('user')
#     query = "SELECT user, image, description, price FROM listing WHERE user = %s AND name = %s"
#     with conn.cursor() as cursor:
#         cursor.execute(query, (user, name))
#         query_result = cursor.fetchone()
#         conn.close()


@app.route('/renew')
def renew():
    if 'username' in session:
        session['designer'] = get_designer_status()
        return render_template('renew.html', designer=session['designer'])
    
    error = "Please log in to renew"
    return render_template("renew.html")


@app.route('/renew_form', methods=['POST'])
def renew_form():
    if request.form:
        period = request.form['period']
        update_designer_period(period)

        return render_template('home.html', designer=session['designer'])
    else:
        error = "Unknown error"
        return render_template('renew.html', error=error)


@app.route('/donate')
def donate():
    if 'username' in session:
        session['designer'] = get_designer_status()
    return render_template('donate.html', designer=session['designer'])


@app.route('/donation_type_form', methods=['POST'])
def donation_type_form():
    if request.form:
        return render_template('donate.html', type=request.form['type'], user=session['username'])
    error="Unknown error"
    return render_template('donate.html', error=error)


@app.route('/donate_form', methods=['POST'])
def donate_pool_form():
    if request.form:
        formData = request.form
        type = formData['type']
        category = formData['category']
        color = formData['color']
        size = formData['size']
        description = formData['description']
        user = formData['user']

        with conn.cursor() as cursor:
            if type == 'pool':
                query = "INSERT INTO donated_item (type, color, size, description, user) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (type, color, size, description, user))
            elif type == 'designer':
                designer = formData['designer']
                query = "SELECT designer FROM user WHERE username = (%s)"
                cursor.execute(query, (designer))
                query_result = cursor.fetchone()
                if query_result is None:
                    error="No designer by that name"
                    return render_template('donate.html', error=error)
                
                query = "INSERT INTO donated_item (type, color, size, description, user, donated_to_designer) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(query, (type, color, size, description, user, designer))
            elif type == 'charity':
                charity = formData['charity']
                query = "INSERT INTO donated_item (type, color, size, description, user, donated_to_charity) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(query, (type, color, size, description, user, charity))
            else:
                error="Unknown error"
                return render_template('donate.html', error=error)
            conn.commit()
                
        message = "Donation successful!"
        return render_template('home.html', designer=session['designer'], message=message)
    error="Unknown error"
    return render_template('donate.html', error=error)


#Define route for trying to post
@app.route('/post_listing')
def post_listing():
    if 'username' in session:
        session['designer'] = get_designer_status()
        return render_template('post.html', designer=session['designer'])

    error = "Please log in to renew"
    # Render post.html.
    return render_template('post.html', error=error)


#Define route for inserting the post
@app.route('/listingAdd', methods=['GET', 'POST'])
def listingAdd():
    # Get information about the name, description, visibility, and types that this listing will have.
    filepath = UPLOAD_FOLDER + request.files['filename'].filename
    name = request.form['name']
    description = request.form['description']
    price = request.form['price']

    savedPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
    savedFile = request.files['filename']
    savedFile.save(savedPath)

    # Insert the file into the database.
    with conn.cursor() as cursor:
        query = 'INSERT INTO listing(name, user, filepath, description, price) VALUES (%s, %s, %s, %s, %s)'
        cursor.execute(query, (name, session['username'], filepath, description, price))
        conn.commit()
      
    return render_template('post.html', success='File Uploaded!')

'''
@app.route("/listingAdd", methods=['GET', 'POST'])
def listingAdd():
    if request.form:
        formData = request.form
        Filename = formData['filename'].filename
        name = formData['name']
        description = formData['description']
        price = formData['price']
        Type = formData['type']
        photoPoster = session["username"]

        with open(filename, "rb") as f:
            data = f.read()
        with conn.cursor() as cursor:
            query = "INSERT INTO Photo (photoBLOB, name, description, type, user, price) " 
                    "VALUES (%s, %s, %s, %s, %s, %s)"
            cursor = conn.cursor()
            cursor.execute(query, (data, name, description, Type, session['username'], price))
            cursor.close()
        return render_template('post.html', success='File Uploaded!')
    else:
        return render_template('post.html', error='Invalid File: Not an image of type jpg, png, or gif')
'''

'''#Define route for managing a page
@app.route('/manage_page')
def manage_page():
    if 'username' in session:
        return render_template('manage_page.html')

    error = "Please log in to manage your page"
    # Render page.html.
    return render_template('manage_page.html', error=error)'''

@app.route('/manage_page', methods=['GET'])
def manage_page():
    if 'username' in session:
        session['designer'] = get_designer_status()
    with conn.cursor() as cursor:
	    query = "SELECT * FROM listing WHERE user = %s"
	    cursor.execute(query, (session['username']))
	    query_result = cursor.fetchall()
    return render_template('manage_page.html', success='Changes saved!', listings=query_result, designer=session['designer'])


#Define route for trying to post
@app.route('/edit/<id>', methods=['GET'])
def edit(id):
    if 'username' in session:
        with conn.cursor() as cursor:
            query = "SELECT * FROM listing WHERE listing.id = %s"
            cursor.execute(query, id)
            query_result = cursor.fetchone()
        return render_template('edit.html', listing=query_result)

    error = "Please log in to edit your listing"
    # Render edit.html.
    return render_template('edit.html', error=error)

@app.route('/edit_listing/<id>', methods=['GET', 'POST'])
def edit_listing(id):
    name = request.form['name']
    description = request.form['description']
    price = request.form['price']

    # Insert the file into the database.
    with conn.cursor() as cursor:
        query = "UPDATE listing SET name = %s, description = %s, price = %s WHERE id = %s"
        cursor.execute(query, (name, description, price, id))
        conn.commit()
    
    message = "Changes Saved!"
    return render_template("home.html", message=message)

@app.route('/delete/<id>', methods=['GET'])
def delete(id):
    with conn.cursor() as cursor:
        query = "SELECT filepath FROM listing WHERE id = %s"
        cursor.execute(query, (id))
        abs_path = os.path.abspath(cursor.fetchone()['filepath'])
        os.remove(abs_path)

        query = "DELETE FROM listing WHERE id = %s"
        cursor.execute(query, (id))
        conn.commit()
    
    message = "Listing Deleted!"
    return render_template("home.html", message=message, designer=session['designer'])


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)
