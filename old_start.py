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
        return render_template('subscribe.html')

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


@app.route('/renew')
def function():
    if 'username' in session:
        return render_template('renew.html')
    
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


# we added the attribute "photoBLOB" to the Photo relation
@app.route("/share")
def share():
    return render_template("share.html")

# <input type="text" name="filepath" size=110 maxLength=100 required/>
@app.route("/share_action", methods=["POST"])
def share_action():
    if request.form:
        formData = request.form
        filepath = formData["filepath"]
        allFollowers = int(formData["allFollowers"])
        caption = formData["caption"]
        photoPoster = session["username"]

        if allFollowers == 1:
            postingdate = datetime.now()
            with open(filepath, "rb") as f:
                img_data = f.read()
            with conn.cursor() as cursor:
                query = "INSERT INTO Photo (postingdate, filepath, allFollowers, caption, photoPoster, photoBLOB) " \
                        "VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(query, (postingdate, filepath, allFollowers, caption, photoPoster, img_data))
                conn.commit()
            return render_template("home.html")
        else:
            with conn.cursor() as cursor:
                query = "SELECT groupName FROM Friendgroup WHERE groupOwner = %s"
                cursor.execute(query, (photoPoster))
                query_result = cursor.fetchall()
            return render_template("share_group.html", filepath=filepath, caption=caption, Friendgroups=query_result)
    else:
        error = "Unknown error"
        return render_template("share.html", error=error)


@app.route("/share_group", methods=["POST"])
def post_action_group():
    if request.form:
        formData = request.form
        postingdate = datetime.now()
        filepath = formData["filepath"]
        allFollowers = 0
        caption = formData["caption"]
        photoPoster = session["username"]
        Friendgroup = formData["Friendgroup"]

        with open(filepath, "rb") as f:
            data = f.read()
        with conn.cursor() as cursor:
            query = "INSERT INTO Photo (postingdate, filepath, allFollowers, caption, photoPoster, photoBLOB) " \
                    "VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (postingdate, filepath, allFollowers, caption, photoPoster, data))
            query = "SELECT photoID FROM Photo AS p WHERE photoID > " \
                    "ALL(SELECT photoID FROM Photo WHERE photoID != p.photoID)"
            cursor.execute(query)
            query_result = cursor.fetchone()
            query = "INSERT INTO SharedWith VALUES (%s, %s, %s)"
            cursor.execute(query, (photoPoster, Friendgroup, query_result["photoID"]))
            conn.commit()
        return render_template("home.html")
    else:
        error = "Unknown error"
        return render_template("share.html", error=error)

# we assume the user viewing a photo is not the user who uploaded it and must download the data from the server as
# a "temporary" file.
@app.route("/view")
def view():
    username = session["username"]
    with conn.cursor() as cursor:
        query = "(SELECT photoID, postingdate, filepath, photoPoster, photoBLOB FROM Photo " \
                "WHERE allFollowers = 1 AND photoPoster IN (SELECT username_followed " \
                "FROM Follow WHERE username_follower = %s AND followstatus = 1)) " \
                "UNION (SELECT photoID, postingdate, filepath, photoPoster, photoBLOB FROM SharedWith s " \
                "NATURAL JOIN Photo p WHERE groupName IN (SELECT groupName FROM BelongTo " \
                "WHERE member_username = %s AND owner_username = s.groupOwner)) ORDER BY postingdate DESC"
        cursor.execute(query, (username, username))
        query_result = cursor.fetchall()
    for row in query_result:
        filepath = row["filepath"]
        photoBLOB = row["photoBLOB"]
        with open(filepath, 'wb') as f:
            f.write(photoBLOB)
        # short-term fix for large data transfer
        row["photoBLOB"] = 0
    return render_template("view.html", photos=query_result)


@app.route("/photo_view/<filename>", methods=["GET"])
def photo_view(filename):
    if os.path.isfile(filename):
        return send_file(filename, mimetype="image/jpg")


@app.route("/view_details/<photoID>", methods=["GET"])
def view_details(photoID):
    query = "SELECT photoID, postingdate, filepath, photoPoster, firstname, lastname FROM (Photo JOIN Person ON " \
            "(Photo.photoPoster = Person.username)) WHERE photoID = %s"
    with conn.cursor() as cursor:
        cursor.execute(query, photoID)
        query_result = cursor.fetchone()
        query = "SELECT username, comment_text FROM Comment WHERE photoID = %s"
        cursor.execute(query, photoID)
        query_result1 = cursor.fetchall()
        query = "SELECT username, firstname, lastname FROM Tagged NATURAL JOIN Person WHERE photoID = %s " \
                "AND tagstatus = 1"
        cursor.execute(query, photoID)
        query_result2 = cursor.fetchall()
        query = "SELECT username, rating FROM Likes WHERE photoID = %s"
        cursor.execute(query, photoID)
        query_result3 = cursor.fetchall()
    if not query_result1:
        query_result1 = [{"username": "N/A", "comment_text": "N/A"}]
    if not query_result2:
        query_result2 = [{"username": "N/A", "firstname": "N/A", "lastname": "N/A"}]
    if not query_result3:
        query_result3 = [{"username": "N/A", "rating": "N/A"}]
    return render_template("view_details.html", photo=query_result, comments=query_result1, tags=query_result2,
                           likes=query_result3)


@app.route("/search_by_user")
def search_by_user():
    return render_template("search_by_user.html")


@app.route("/search_by_user_action", methods=["POST"])
def search_by_user_action():
    if request.form:
        their_username = request.form["username"]
        my_username = session["username"]
        query = "(SELECT photoID, postingdate, filepath, photoPoster, photoBLOB FROM Photo WHERE allFollowers = 1 " \
                "AND photoPoster IN (SELECT username_followed FROM Follow WHERE username_follower = %s " \
                "AND username_followed = %s AND followstatus = 1)) UNION " \
                "(SELECT photoID, postingdate, filepath, photoPoster, photoBLOB FROM SharedWith NATURAL JOIN Photo " \
                "WHERE groupName IN (SELECT groupName FROM BelongTo WHERE member_username = %s " \
                "AND owner_username = %s)) ORDER BY postingdate DESC"

        with conn.cursor() as cursor:
            cursor.execute(query, (my_username, their_username, my_username, their_username))
            query_result = cursor.fetchall()
        for row in query_result:
            filepath = row["filepath"]
            photoBLOB = row["photoBLOB"]
            with open(filepath, 'wb') as f:
                f.write(photoBLOB)
            # short-term fix for large data transfer
            row["photoBLOB"] = 0
        return render_template("view.html", photos=query_result)
    else:
        error = "Unknown error"
        return render_template("search_by_user.html", error=error)


@app.route("/follow_user")
def follow_user():
    return render_template("follow_user.html")


@app.route("/follow_user_action", methods=["POST"])
def follow_user_action():
    if request.form:
        formData = request.form
        their_username = formData["username_followed"]
        my_username = session["username"]
        query = "INSERT INTO Follow VALUES (%s, %s, %s)"

        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (their_username, my_username, 0))
                conn.commit()
        except pymysql.IntegrityError:
            error = "You have already sent this user a follow request."
            return render_template("follow_user.html", error=error)
        return render_template("home.html")
    else:
        error = "Unknown error"
        return render_template("follow_user.html", error=error)


@app.route("/follow_requests")
def follow_requests():
    username = session["username"]
    query = "SELECT username_follower FROM Follow WHERE username_followed = %s AND followstatus = 0"

    with conn.cursor() as cursor:
        cursor.execute(query, (username))
        query_result = cursor.fetchall()
    return render_template("follow_requests.html", requests=query_result)


@app.route("/follow_requests_action", methods=["POST"])
def follow_requests_action():
    their_username = request.form.getlist("username_follower")
    if their_username:
        my_username = session["username"]
        for tu in their_username:
            query = "UPDATE Follow SET followstatus = 1 WHERE username_followed = %s AND username_follower = %s"
            with conn.cursor() as cursor:
                cursor.execute(query, (my_username, tu))
                conn.commit()
        return render_template("home.html")
    else:
        error = "Unknown error"
        return render_template("follow_requests.html", error=error)


@app.route("/add_comment", methods=["POST"])
def add_comment():
    if request.form:
        formData = request.form
        username_commenter = session["username"]
        photoID = formData["photoID"]
        comment_text = formData["comment_text"]
        query = "INSERT INTO Comment VALUES (%s, %s, %s)"
        page_path = os.path.join("view_details/", photoID)

        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (username_commenter, photoID, comment_text))
                conn.commit()
        except pymysql.IntegrityError:
            return redirect(page_path)
        return redirect(page_path)
    else:
        error = "Unknown error"
        return render_template("home.html", error=error)


@app.route("/like_photo", methods=["POST"])
def like_photo():
    if request.form:
        username = session["username"]
        photoID = request.form["photoID"]
        liketime = datetime.now()
        rating = int(request.form["rating"])
        query = "INSERT INTO Likes VALUES (%s, %s, %s, %s)"

        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (username, photoID, liketime, rating))
                conn.commit()
        except pymysql.err.IntegrityError:
            page_path = os.path.join("view_details/", photoID)
            return redirect(page_path)
        page_path = os.path.join("view_details/", photoID)
        return redirect(page_path)
    else:
        error = "Unknown error"
        return render_template("home.html", error=error)


@app.route("/add_friend_group")
def add_friend_group():
    return render_template("add_friend_group.html")


@app.route("/add_friend_group_action", methods=["POST"])
def add_friend_group_action():
    if request.form:
        groupOwner = session["username"]
        groupName = request.form["groupName"]
        description = request.form["description"]
        query = "INSERT INTO Friendgroup VALUES (%s, %s, %s)"

        try:
            with conn.cursor() as cursor:
                cursor.execute(query, (groupOwner, groupName, description))
                conn.commit()
        except pymysql.err.IntegrityError:
            error = "You have already created a friend group with that name."
            return render_template("add_friend_group.html", error=error)
        return render_template("home.html")
    else:
        error = "Unknown error"
        return render_template("add_friend_group.html", error=error)


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)
