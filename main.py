
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
import hashlib

app = Flask(__name__)

con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)
conn = engine.connect()
app.secret_key = "idk"

@app.route("/")
def home():
    return render_template("home_main.html")

@app.route("/home")
def home2():
    username = session.get("username") or session.get("vendor_name")
    if not username:
        return redirect(url_for("login"))
    return render_template("home.html", username=username)



@app.route("/search")
def search():
    query = request.args.get('q')
    if not query:
        return render_template("search_results.html", query=query, products=[])

    try:
        with engine.connect() as conn:
            search_query = text("""
                SELECT p.*, pi.ImageURL
                 FROM products p
                LEFT JOIN productimages pi ON p.ProductID = pi.ProductID
                 WHERE p.Title LIKE :query OR p.Description LIKE :query
                """)
            result = conn.execute(search_query, {"query": f"%{query}%"}).fetchall()
            return render_template("search_results.html", query=query, products=result)

    except Exception as e:
        return f"<h3>Error during search: {e}</h3>"


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

            if username.endswith("_vend"):
                session["vendor_name"] = username
            else:
                session["username"] = username

            flash("You have successfully signed up!")
            return redirect(url_for("home"))

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
                }).mappings().fetchone()

                if result:
                    username = result["Username"]

                    if username.endswith("_vend"):
                        session["vendor_name"] = username
                        return redirect(url_for("vendor_dashboard"))
                    else:
                        session["username"] = username
                        return redirect(url_for("home2"))
                else:
                    return f"<h3>Invalid email or password.</h3><a href='{url_for('login')}'>Try again</a>"

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"

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
        discount_time = request.form["discount_time"] 
        image_urls = request.form.getlist("image_urls") 

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
