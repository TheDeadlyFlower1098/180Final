
from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, text
import hashlib

app = Flask(__name__)

con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)
conn = engine.connect()
app.secret_key = "idkwhattoput"

@app.route("/")
def home():
    return render_template("home_main.html")

@app.route("/home")
def home2():
  
   query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    
    result = conn.execute(query)
    products = result.fetchall()
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    return render_template("home.html", username=username)

@app.route("/search")
def search():
    query = request.args.get('q')
    return render_template("search_results.html", query=query)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        if not email or "@" not in email:
            return render_template("signup.html", error="Please enter a valid email address.")
        
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters long.")

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        if role == "vendor":
            username += "_vend"

        try:
            with engine.connect() as conn:
                check_email_query = text("SELECT * FROM User WHERE Email = :email")
                email_result = conn.execute(check_email_query, {"email": email}).fetchone()

                if email_result:
                    return render_template("signup.html", error="Email is already registered.")

             
                check_username_query = text("SELECT * FROM User WHERE Username = :username")
                username_result = conn.execute(check_username_query, {"username": username}).fetchone()

                if username_result:
                    return render_template("signup.html", error="Username is already taken.")

                insert_query = text("""
                    INSERT INTO User (Name, Email, Username, Password)
                    VALUES (:name, :email, :username, :password)
                """)
                conn.execute(insert_query, {
                    "name": name,
                    "email": email,
                    "username": username,
                    "password": hashed_password
                })
                conn.commit()

            return render_template("signup_success.html", username=username)

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["Email"] 
        password = request.form["password"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            with engine.connect() as conn:
                query = text("""
                    SELECT * FROM User
                    WHERE Email = :email AND Password = :password
                """)
                result = conn.execute(query, {
                    "email": email,
                    "password": hashed_password
                }).fetchone()
                if result:
                    session["username"] = result[1]
                    return redirect(url_for("home2"))
                else:
                    return f"<h3>Invalid email or password.</h3><a href='{url_for('login')}'>Try again</a>"

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"

    return render_template("login.html")


if __name__ == '__main__':
    app.run(debug=True)
