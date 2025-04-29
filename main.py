# Import necessary libraries
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib

# Initialize Flask app
app = Flask(__name__)

# Database connection string and engine setup
con_str = "mysql://root:cset155@localhost/MultiVendorEcommerce"
engine = create_engine(con_str, echo=True)  # Echo True logs SQL queries
conn = engine.connect()
app.secret_key = "idkwhattoput"  # Secret key for session management
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
        return redirect(url_for("login"))

    # Add product query to prevent NameError
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()

    return render_template("home.html", username=username, products=products)

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

# Sign up route for new users (GET to display form, POST to process form)
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

        try:
            with engine.begin() as conn:
                # Check for duplicate email or username
                email_exists = conn.execute(text("SELECT * FROM User WHERE Email = :email"), {"email": email}).fetchone()
                username_exists = conn.execute(text("SELECT * FROM User WHERE Username = :username"), {"username": username}).fetchone()

                if email_exists:
                    return render_template("signup.html", error="Email is already registered.")
                if username_exists:
                    return render_template("signup.html", error="Username is already taken.")

                # Insert user
                insert_user = text("""
                    INSERT INTO User (Name, Email, Username, Password, Role)
                    VALUES (:name, :email, :username, :password, :role)
                """)
                conn.execute(insert_user, {
                    "name": name,
                    "email": email,
                    "username": username,
                    "password": hashed_password,
                    "role": role
                })

                # Get the new user ID
                user_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                # If vendor, insert into the Vendor table using same ID
                if role == "vendor":
                    insert_vendor = text("INSERT INTO Vendor (VendorID) VALUES (:vendor_id)")
                    conn.execute(insert_vendor, {"vendor_id": user_id})

            return render_template("signup_success.html", username=username)

        except Exception as e:
            return render_template("signup.html", error=f"An error occurred: {e}")

    return render_template("signup.html")


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
                    result = dict(result._mapping)  # Convert result to dictionary for key access

                    session["username"] = result["Username"]
                    session["role"] = result["Role"]
                    session["vendor_id"] = result["UserID"] if result["Role"] == "vendor" else None

                    if result["Role"] == "vendor":
                        return redirect(url_for("vendor_dashboard"))
                    elif result["Role"] == "admin":
                        return redirect(url_for("admin_manage_products"))
                    else:
                        return redirect(url_for("home2"))
                else:
                    return f"<h3>Invalid email or password.</h3><a href='{url_for('login')}'>Try again</a>"

        except Exception as e:
            return f"<h3>Login error: {e}</h3>"  # Handle any errors during login

    return render_template("login.html")  # Render the login form


# Logout route to clear the session and redirect to login page
@app.route("/logout")
def logout():
    session.clear()  # Clear the session
    return redirect(url_for("login"))  # Redirect to login page

@app.route("/vendor/dashboard")
def vendor_dashboard():
    if session.get("role") != "vendor":
        return redirect(url_for("login"))

    vendor_name = session.get("username")
    return render_template("vendor_dashboard.html", vendor_name=vendor_name)



@app.route("/products")
def products():
    category = request.args.get('category')
    color = request.args.get('color')
    size = request.args.get('size')
    availability = request.args.get('availability')  # 'in' or 'out'

    query_base = """
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL, p.Color, p.Size, 
               p.InventoryAmount, p.Category
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE 1=1
    """
    filters = {}
    if category:
        query_base += " AND p.Category = :category"
        filters['category'] = category
    if color:
        query_base += " AND FIND_IN_SET(:color, p.Color)"
        filters['color'] = color
    if size:
        query_base += " AND FIND_IN_SET(:size, p.Size)"
        filters['size'] = size
    if availability == 'in':
        query_base += " AND p.InventoryAmount > 0"
    elif availability == 'out':
        query_base += " AND p.InventoryAmount = 0"

    result = conn.execute(text(query_base), filters)
    products = result.fetchall()
    return render_template("products.html", products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    query = text("""
        SELECT p.ProductID, p.Title, p.Description, p.DiscountedPrice, p.Category, 
               p.Color, p.Size, p.InventoryAmount, p.WarrantyPeriod, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID = :product_id
    """)
    result = conn.execute(query, {"product_id": product_id}).fetchone()
    if not result:
        return "<h3>Product not found.</h3>"

    product = dict(result._mapping)
    product["colors"] = product["Color"].split() if product["Color"] else []
    product["sizes"] = product["Size"].split() if product["Size"] else []
    product["categories"] = product["Category"].split() if product["Category"] else []
    return render_template("product_detail.html", product=product)

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  # Initialize the cart if it doesn't exist

    # Retrieve form data for color, size, and quantity
    color = request.form.get('color')
    size = request.form.get('size')
    quantity = int(request.form.get('quantity', 1))

    # Check if the item with selected color and size already exists in the cart
    product_in_cart = next((item for item in session['cart'] if item['product_id'] == product_id and item['color'] == color and item['size'] == size), None)

    if product_in_cart:
        product_in_cart['quantity'] += quantity  # Increment quantity if the item is already in the cart
    else:
        session['cart'].append({
            'product_id': product_id,
            'color': color,
            'size': size,
            'quantity': quantity
        })

    session.modified = True  # Ensure session changes are saved
    return redirect(url_for('cart'))  # Redirect to cart page

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Retrieve cart from session
    print("Cart:", cart)  # Debug: Check the contents of the cart

    if not cart:  # If the cart is empty
        return render_template("cart.html", products=[], total_price=0, cart=cart)

    # Continue with your logic here to fetch product details
    # Extract product_ids from cart
    product_ids = [item['product_id'] for item in cart]
    print("Product IDs:", product_ids)  # Debug: Check extracted product IDs

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    
    try:
        result = conn.execute(query, {"product_ids": tuple(product_ids)})
        products = result.mappings().fetchall()  # Use mappings to return rows as dictionaries
        print("Products Fetched:", products)  # Debug: Check fetched products
    except Exception as e:
        print("Error executing query:", e)
        return "There was an error fetching products"

    # Merge the DiscountedPrice with each cart item
    for item in cart:
        for product in products:
            if item['product_id'] == product['ProductID']:
                item['DiscountedPrice'] = product['DiscountedPrice']
                item['Title'] = product['Title']
                item['ImageURL'] = product['ImageURL']

    # Calculate total price based on cart items
    total_price = 0
    for item in cart:
        if 'DiscountedPrice' in item:
            total_price += item['DiscountedPrice'] * item['quantity']

    return render_template("cart.html", products=cart, total_price=total_price, cart=cart)


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
                        InventoryAmount, OriginalPrice, DiscountedPrice, DiscountTime, VendorID )
                    VALUES (:title, :description, :warranty_period, :color, :size,
                        :inventory_amount, :original_price, :discounted_price, :discount_time, :vendor_id )
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

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'cart' not in session:
        return redirect(url_for('cart'))  # Redirect if cart doesn't exist in session

    cart = session['cart']
    updated_cart = []

    for item in cart:
        product_id = item['product_id']
        
        # Get updated quantity
        quantity = int(request.form.get(f'quantities[{product_id}]', item['quantity']))  # Default to existing quantity if no update
        
        # Check if item should be deleted
        if f'delete_{product_id}' in request.form and request.form.get(f'delete_{product_id}') == '1':
            continue  # Skip adding this item to the updated cart if it's marked for deletion

        item['quantity'] = quantity  # Update quantity
        updated_cart.append(item)  # Add updated item to the new cart

    session['cart'] = updated_cart  # Update session cart
    session.modified = True
    return redirect(url_for('cart'))  # Redirect to cart page


# Checkout route to display the checkout page with total price
@app.route("/checkout")
def checkout():
    cart = session.get('cart', [])
    total_price = 0
    product_ids = [item['product_id'] for item in cart]

    # Fixed the SQL query here:
    query = text("""
        SELECT p.ProductID, p.DiscountedPrice
        FROM Products p
        WHERE p.ProductID IN :product_ids
    """)
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.fetchall()

    for product in products:
        for item in cart:
            if item['product_id'] == product['ProductID']:
                total_price += product['DiscountedPrice'] * item['quantity']

    return render_template("checkout.html", products=products, total_price=total_price)
from flask import flash, redirect, render_template, session, url_for
from sqlalchemy import text

@app.route("/vendor/manage")
def manage_products():
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    with engine.connect() as conn:
        query = text("""
            SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
            FROM Products p
            LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
            WHERE p.VendorID = :vendor_id
        """)
        result = conn.execute(query, {"vendor_id": vendor_id})
        products = result.fetchall()

    return render_template("manage.html", products=products)


@app.route("/vendor/delete_product/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))
    
    with engine.connect() as conn:
        product_check = text("SELECT * FROM Products WHERE ProductID = :product_id AND VendorID = :vendor_id")
        product = conn.execute(product_check, {"product_id": product_id, "vendor_id": vendor_id}).fetchone()

    if product:
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM ProductImages WHERE ProductID = :product_id"), {"product_id": product_id})
                conn.execute(text("DELETE FROM Products WHERE ProductID = :product_id"), {"product_id": product_id})
                
            flash("Product deleted successfully!", "success")
        except Exception as e:
            flash(f"Error deleting product: {e}", "error")
    else:
        flash("You can only delete your own products.", "danger")

    return redirect(url_for("manage_products"))


@app.route('/account', methods=['GET'])
def account():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    user = conn.execute(
        text('SELECT * FROM user WHERE Username = :username'),
        {'username': username}
    ).fetchone()

    return render_template('vendor_dashboard.html', user=user)

@app.route("/admin/manage", methods=["GET"])
def admin_manage_products():
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
    """)
    products = conn.execute(query).fetchall()

    return render_template("admin.html", products=products)


@app.route("/admin/delete_product/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM ProductImages WHERE ProductID = :product_id"), {"product_id": product_id})
            conn.execute(text("DELETE FROM Products WHERE ProductID = :product_id"), {"product_id": product_id})
        flash("Product deleted successfully by admin.", "success")
    except Exception as e:
        flash(f"Error deleting product: {e}", "danger")

    return redirect(url_for("admin_manage_products"))


# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
