
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
import hashlib
from datetime import datetime


# Initialize Flask app
app = Flask(__name__)

# Database connection string and engine setup
con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)  # Echo True logs SQL queries
conn = engine.connect()
app.secret_key = "idk"  # Secret key for session management
app.config['SQLALCHEMY_DATABASE_URI'] = con_str  # Set the SQLAlchemy URI
db = SQLAlchemy(app)  # Initialize SQLAlchemy with Flask

# Home route that displays the latest 5 products
@app.route("/")
def home():
    # SQL query to select top 5 products with their image URLs
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)  # Execute the query
    products = result.fetchall()  # Fetch all results
    return render_template("home.html", products=products)  # Render the home page with products

# Alternative home route with session-based username management
@app.route("/home")
def home2():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))  # Redirect to login if username is not found
    return render_template("home.html", username=username, products=products)

@app.route("/search")
def search():
    query = request.args.get('q')  # Get the search query from the URL parameters
    if not query:
        return redirect(url_for('products'))  # Redirect if no query is provided
    # SQL query to search products by title
    search_query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.Title LIKE :search
    """)
    result = conn.execute(search_query, {"search": f"%{query}%"})  # Execute query with search parameter
    products = result.fetchall()
    return render_template("search_results.html", query=query, products=products)

# Sign up route for new users (GET to display form, POST to process form)
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":  # Handle form submission
        name = request.form["name"]
        email = request.form["email"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]

        # Basic email validation
        if not email or "@" not in email:
            return render_template("signup.html", error="Please enter a valid email address.")
        
        # Password length validation
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters long.")

        # Hash the password using SHA-256
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        # Append '_vend' to username for vendors
        if role == "vendor":
            username += "_vend"

        try:
            with engine.connect() as conn:
                # Check if the email is already registered
                check_email_query = text("SELECT * FROM User WHERE Email = :email")
                email_result = conn.execute(check_email_query, {"email": email}).fetchone()

                if email_result:
                    return render_template("signup.html", error="Email is already registered.")

                # Check if the username is already taken
                check_username_query = text("SELECT * FROM User WHERE Username = :username")
                username_result = conn.execute(check_username_query, {"username": username}).fetchone()

                if username_result:
                    return render_template("signup.html", error="Username is already taken.")

                # Insert new user into the database
                insert_query = text("""
                    INSERT INTO User (Name, Email, Username, Password, Role)
                    VALUES (:name, :email, :username, :password, :role)
                """)
                with engine.begin() as conn:
                    conn.execute(insert_query, {
                        "name": name,
                        "email": email,
                        "username": username,
                        "password": hashed_password
                    })

            return render_template("signup_success.html", username=username)  # Success page

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")  # Error handling

    return render_template("signup.html")  # Render the signup form

# Login route for users (GET to display form, POST to process form)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["Email"]
        password = request.form["password"]
        hashed_password = hashlib.sha256(password.encode()).hexdigest()  # Hash the entered password

        try:
            with engine.connect() as conn:
                # SQL query to check email and password against the database
                query = text("""
                    SELECT * FROM User
                    WHERE Email = :email AND Password = :password
                """)
                result = conn.execute(query, {
                    "email": email,
                    "password": hashed_password
                }).fetchone()
                if result:
                    session["username"] = result[1]  # Set the username in the session
                    return redirect(url_for("home2"))  # Redirect to home page
                else:
                    flash("Invalid email or password.", "error")
                    return redirect(url_for("login"))

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"  # Handle any errors during login

    return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

@app.route("/vendor/dashboard")
def vendor_dashboard():
    vendor_name = session.get("vendor_name")
    if not vendor_name:
        return redirect(url_for("login"))
    return render_template("vendor_dashboard.html", vendor_name=vendor_name)

@app.route("/products")
def products():
    try:
        with engine.connect() as conn:
            query = text("SELECT p.*, pi.ImageURL FROM products p LEFT JOIN productimages pi ON p.ProductID = pi.ProductID")
            result = conn.execute(query).mappings().fetchall()
            return render_template("products.html", products=result)
    except Exception as e:
        return f"<h3>Error loading products: {e}</h3>"
    
@app.route("/vendor/add_product", methods=["GET", "POST"])
def add_product():
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Collect form data
        title = request.form["title"]
        description = request.form["description"]
        warranty_period = request.form.get("warranty_period", type=int)
        color = request.form["color"]
        size = request.form["size"]
        inventory_amount = request.form.get("inventory_amount", type=int)
        original_price = request.form.get("original_price", type=float)
        discounted_price = request.form.get("discounted_price", type=float)
        discount_time_str = request.form["discount_time"]  # Get the datetime string
        discount_time = None

        if discount_time_str:
            discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M")

        image_urls = request.form.getlist("image_urls")  # Accept multiple image URLs

        try:
            with engine.begin() as conn:
                # Insert product
                product_insert = text("""
                    INSERT INTO Products (Title, Description, WarrantyPeriod, Color, Size,
                        InventoryAmount, OriginalPrice, DiscountedPrice, DiscountTime, VendorID)
                    VALUES (:title, :description, :warranty_period, :color, :size,
                        :inventory_amount, :original_price, :discounted_price, :discount_time, :vendor_id)
                """)
                conn.execute(product_insert, {
                    "title": title,
                    "description": description,
                    "warranty_period": warranty_period,
                    "color": color,
                    "size": size,
                    "inventory_amount": inventory_amount,
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_time": discount_time,
                    "vendor_id": vendor_id
                })

                # Get new ProductID
                product_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                # Insert images
                for url in image_urls:
                    if url.strip():  # Avoid empty fields
                        image_insert = text("INSERT INTO ProductImages (ProductID, ImageURL) VALUES (:product_id, :image_url)")
                        conn.execute(image_insert, {"product_id": product_id, "image_url": url})

                flash("Product added successfully!", "success")
                return redirect(url_for("vendor_dashboard"))

        except Exception as e:
            return f"<h3>Error adding product: {e}</h3>"

    return render_template("add_product.html")





if __name__ == '__main__':
    app.run(debug=True)