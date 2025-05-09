# Import necessary libraries
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from flask_sqlalchemy import SQLAlchemy
from flask_login import login_required
from collections import defaultdict
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

@app.route("/")
def home():
    username = session.get("username")

    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        LIMIT 5
    """)
    result = conn.execute(query)
    products = result.fetchall()

    return render_template("home.html", username=username, products=products)

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

                    session["user_id"] = result["UserID"] 
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

    vendor_id = session.get("vendor_id")
    vendor_name = session.get("username")

    # Fetch user data
    user_id = session.get("user_id")  # Assuming the user ID is stored in the session
    if user_id:
        with engine.connect() as conn:
            user_query = text("""SELECT * FROM User WHERE UserID = :user_id""")
            user = conn.execute(user_query, {"user_id": user_id}).fetchone()
    else:
        user = None

    with engine.connect() as conn:
        # Get vendor's products for display
        product_query = text("""
            SELECT p.*, pi.ImageURL 
            FROM Products p
            LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
            WHERE p.VendorID = :vendor_id
        """)
        products = conn.execute(product_query, {"vendor_id": vendor_id}).fetchall()

        # Get vendor-related orders
        order_query = text("""
            SELECT o.OrderID, o.OrderDate, o.TotalPrice, o.Status,
                   oi.Quantity, oi.Price,
                   p.Title AS ProductTitle,
                   u.Name AS CustomerName, u.Email AS CustomerEmail
            FROM Orders o
            JOIN OrderItems oi ON o.OrderID = oi.OrderID
            JOIN Products p ON oi.ProductID = p.ProductID
            JOIN User u ON o.UserID = u.UserID
            WHERE p.VendorID = :vendor_id
            ORDER BY o.OrderDate DESC
        """)
        orders = conn.execute(order_query, {"vendor_id": vendor_id}).fetchall()

    # Group orders by OrderID
    grouped_orders = {}
    for order in orders:
        grouped_orders.setdefault(order.OrderID, []).append(order)

    return render_template("vendor_dashboard.html",
                           vendor_name=vendor_name,
                           products=products,
                           orders=grouped_orders,
                           user=user)

@app.route("/vendor/update_order_status", methods=["POST"])
def update_order_status():
    if session.get("role") != "vendor":
        return redirect(url_for("login"))

    order_id = request.form.get("order_id")
    current_status = request.form.get("current_status")

    # Define status progression
    status_flow = {
        "pending": "confirmed",
        "confirmed": "handed to delivery partner",
        "handed to delivery partner": "shipped",
        "shipped": None  # Final state
    }

    next_status = status_flow.get(current_status.lower())

    if not next_status:
        flash("This order is already shipped or has an invalid status.", "warning")
        return redirect(url_for("vendor_dashboard"))

    with engine.begin() as conn:
        update_query = text("""
            UPDATE Orders
            SET Status = :next_status
            WHERE OrderID = :order_id
        """)
        conn.execute(update_query, {"next_status": next_status, "order_id": order_id})

    flash(f"Order {order_id} status updated to '{next_status}'.", "success")
    return redirect(url_for("vendor_dashboard"))

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
    reviews = conn.execute(text("""
    SELECT r.Rating, r.Description, r.ImageURL, r.Date, u.Username
    FROM review r
    JOIN user u ON r.CustomerID = u.UserID
    WHERE r.ProductID = :product_id
    ORDER BY r.Date DESC
"""), {"product_id": product_id}).mappings().all()
    
    result = conn.execute(query, {"product_id": product_id}).fetchone()
    if not result:
        return "<h3>Product not found.</h3>"

    product = dict(result._mapping)
    product["colors"] = product["Color"].split() if product["Color"] else []
    product["sizes"] = product["Size"].split() if product["Size"] else []
    product["categories"] = product["Category"].split() if product["Category"] else []
    return render_template("product_detail.html", product=product, current_time=datetime.utcnow(), reviews=reviews)


# Cart item model for SQLAlchemy (manages cart items in the database)
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product', back_populates='cart_items')

# Product model for SQLAlchemy (manages product information in the database)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cart_items = db.relationship('CartItem', back_populates='product')


from datetime import datetime

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
        discount_time_str = request.form.get("discount_time")
        discount_time = None

        # Ensure that discount_time is only processed if it is provided
        if discount_time_str:
            try:
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                flash("Invalid discount time format! Please use YYYY-MM-DDTHH:MM", "danger")
                return render_template("add_product.html")

        # Ensure all required fields have values
        if original_price is None:
            flash("Original price is required!", "danger")
            return render_template("add_product.html")

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
                    "discounted_price": discounted_price if discounted_price else None,  # Handle None if not provided
                    "discount_time": discount_time,
                    "vendor_id": vendor_id
                })

                # Get new ProductID
                product_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

                # Insert images
                image_urls = request.form.getlist("image_urls")  # Accept multiple image URLs
                for url in image_urls:
                    if url.strip():  # Avoid empty fields
                        image_insert = text("INSERT INTO ProductImages (ProductID, ImageURL) VALUES (:product_id, :image_url)")
                        conn.execute(image_insert, {"product_id": product_id, "image_url": url})

                flash("Product added successfully!", "success")
                return redirect(url_for("vendor_dashboard"))

        except Exception as e:
            flash(f"Error adding product: {e}", "danger")
            return render_template("add_product.html")

    return render_template("add_product.html")


@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []  # Initialize the cart if it doesn't exist

    # Retrieve form data for color, size, and quantity
    color = request.form.get('color')
    size = request.form.get('size')
    quantity = int(request.form['quantity'])
    
    product = Product.query.get(product_id)
    
    if product.InventoryAmount < quantity:
        # If not enough stock, show error or just prevent adding to cart
        return render_template("product_detail.html", product=product, error="Not enough stock available.")

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

def enrich_cart(cart):
    if not cart:
        return cart, 0

    product_ids = [item['product_id'] for item in cart]
    query = text("""
        SELECT p.ProductID, p.Title, p.DiscountedPrice, pi.ImageURL
        FROM Products p
        LEFT JOIN ProductImages pi ON p.ProductID = pi.ProductID
        WHERE p.ProductID IN :product_ids
    """)
    
    result = conn.execute(query, {"product_ids": tuple(product_ids)})
    products = result.mappings().fetchall()

    total_price = 0
    for item in cart:
        for product in products:
            if item['product_id'] == product['ProductID']:
                item['DiscountedPrice'] = product.get('DiscountedPrice', 0)
                item['Title'] = product['Title']
                item['ImageURL'] = product.get('ImageURL', '')
                total_price += item['DiscountedPrice'] * item['quantity']
    return cart, total_price

@app.route('/cart')
def cart():
    cart = session.get('cart', [])  # Retrieve cart from session

    # Enrich cart with product data and calculate total price
    cart, total_price = enrich_cart(cart)

    return render_template("cart.html", products=cart, total_price=total_price, cart=cart)

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

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    user_id = session.get('user_id')
    cart = session.get('cart', [])
    if not cart:
        return redirect(url_for('cart'))

    cart, total_price = enrich_cart(cart)

    with engine.connect() as conn:
        addresses = conn.execute(text("SELECT * FROM Address WHERE UserID = :uid"), {"uid": user_id}).fetchall()
        default_address = next((a for a in addresses if a.IsDefault), None)

    if request.method == 'POST':
        selected_address_id = request.form.get("address_id")
        new_address = request.form.get("new_address")

        billing_address = None
        if selected_address_id == "new" and new_address:
            billing_address = new_address
        else:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT AddressLine FROM Address WHERE AddressID = :aid"), {"aid": selected_address_id}).fetchone()
                billing_address = result[0] if result else None

        if not billing_address:
            flash("Please provide a valid address.", "danger")
            return redirect(url_for("checkout"))

        order_id = create_order(cart, total_price, billing_address)
        session['cart'] = []
        return redirect(url_for('order_confirmation', order_id=order_id))

    return render_template("checkout.html", products=cart, total_price=total_price, addresses=addresses, default_address=default_address)

def create_order(cart, total_price, billing_address):
    user_id = session.get('user_id')
    
    order_date = datetime.now()
    status = 'pending'

    db.session.execute(
        text("""
            INSERT INTO Orders (UserID, OrderDate, TotalPrice, Status, BillingAddress)
            VALUES (:user_id, :order_date, :total_price, :status, :billing_address)
        """),
        {
            'user_id': user_id,
            'order_date': datetime.now(),
            'total_price': total_price,
            'status': 'pending',
            'billing_address': billing_address  # make sure this is passed to the function
        }
    )
    db.session.commit()

    order_id = db.session.execute(
        text('SELECT LAST_INSERT_ID()')
    ).fetchone()[0]

    for item in cart:
        product_id = item['product_id']
        quantity = item['quantity']
        product = Product.query.get(product_id)

        # Insert item into OrderItems table
        db.session.execute(
            text('''
            INSERT INTO OrderItems (OrderID, ProductID, Quantity, Price)
            VALUES (:order_id, :product_id, :quantity, :price)
            '''), 
            {'order_id': order_id, 'product_id': product_id, 'quantity': quantity, 'price': product.price}
        )

        # Update inventory
        new_inventory_amount = product.InventoryAmount - quantity
        db.session.execute(
            text('''
            UPDATE Products
            SET InventoryAmount = :new_inventory_amount,
                StockStatus = CASE
                    WHEN :new_inventory_amount <= 0 THEN 'Out of Stock'
                    ELSE 'In Stock'
                END
            WHERE ProductID = :product_id
            '''), 
            {'new_inventory_amount': new_inventory_amount, 'product_id': product_id}
        )

    db.session.commit()

    return order_id

@app.route('/order_confirmation/<order_id>')
def order_confirmation(order_id):
    return render_template("order_confirmation.html", order_id=order_id)

@app.route("/vendor/manage") #vendor delete or edit product
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

@app.route("/vendor/delete_product/<int:product_id>", methods=["POST"]) #for vendor to delete product route
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

@app.route("/admin/manage", methods=["GET"])
def admin_manage_products():
    if session.get("role") != "admin": #log out user who role is not admin
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
        # Re-open a fresh connection to safely check for related orders
        with engine.connect() as conn:
            order_check = conn.execute(
                text("SELECT 1 FROM OrderItems WHERE ProductID = :product_id LIMIT 1"),
                {"product_id": product_id}
            ).fetchone()

        if order_check:
            flash("Cannot delete: Product is part of an existing order.", "danger")
        else:
            flash(f"Error deleting product: {e}", "danger")

    return redirect(url_for("admin_manage_products"))

from datetime import datetime

@app.route("/admin/edit_product/<int:product_id>", methods=["GET", "POST"])
def admin_edit_product(product_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))

    with engine.begin() as conn:
        product = conn.execute(
            text("SELECT * FROM Products WHERE ProductID = :product_id"),
            {"product_id": product_id}
        ).fetchone()

        if not product:
            flash("Product not found.", "warning")
            return redirect(url_for("admin_manage_products"))

        if request.method == "POST":
            try:
                title = request.form["title"]
                description = request.form["description"]
                original_price = request.form.get("original_price", type=float)
                discounted_price = request.form.get("discounted_price", type=float)
                discount_time_str = request.form.get("discount_time")
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M") if discount_time_str else None

                conn.execute(text("""
                    UPDATE Products
                    SET Title = :title,
                        Description = :description,
                        OriginalPrice = :original_price,
                        DiscountedPrice = :discounted_price,
                        DiscountTime = :discount_time
                    WHERE ProductID = :product_id
                """), {
                    "title": title,
                    "description": description,
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_time": discount_time,
                    "product_id": product_id
                })

                flash("Product updated successfully.", "success")
                return redirect(url_for("admin_manage_products"))

            except Exception as e:
                flash(f"Error updating product: {e}", "danger")

    return render_template("edit_product.html", product=product)

  
@app.route("/vendor/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    vendor_id = session.get("vendor_id")
    if not vendor_id:
        return redirect(url_for("login"))

    with engine.begin() as conn: 
        query = text("SELECT * FROM Products WHERE ProductID = :product_id AND VendorID = :vendor_id")
        product = conn.execute(query, {"product_id": product_id, "vendor_id": vendor_id}).fetchone()

        if not product:
            flash("Product not found or not authorized.", "danger")
            return redirect(url_for("manage_products"))

        if request.method == "POST":
            try:
                title = request.form["title"]
                description = request.form["description"]
                original_price = request.form.get("original_price", type=float)
                discounted_price = request.form.get("discounted_price", type=float)
                discount_time_str = request.form.get("discount_time")
                discount_time = datetime.strptime(discount_time_str, "%Y-%m-%dT%H:%M") if discount_time_str else None

                conn.execute(text("""
                    UPDATE Products
                    SET Title = :title,
                        Description = :description,
                        OriginalPrice = :original_price,
                        DiscountedPrice = :discounted_price,
                        DiscountTime = :discount_time
                    WHERE ProductID = :product_id AND VendorID = :vendor_id
                """), {
                    "title": title,
                    "description": description,
                    "original_price": original_price,
                    "discounted_price": discounted_price,
                    "discount_time": discount_time,
                    "product_id": product_id,
                    "vendor_id": vendor_id
                })

                flash("Product updated successfully!", "success")
                return redirect(url_for("manage_products"))

            except Exception as e:
                flash(f"Error updating product: {e}", "danger")

    return render_template("edit_product.html", product=product)

@app.route("/chat/<int:receiver_id>", methods=["GET", "POST"])
def chat(receiver_id):
    sender_id = session.get("user_id") #get the id of user thats logged in
    if not sender_id:
        flash("Please log in to chat.", "warning")
        return redirect(url_for("login")) #return to log in page if user not in session

    if request.method == "POST":
        message = request.form["message"] #where the messages send
        image_url = request.form.get("image_url")  #sending images

        with engine.begin() as conn: #insert into databse
            conn.execute(text("""
                INSERT INTO Chat (SenderID, ReceiverID, Message, ImageURL, Timestamp)
                VALUES (:sender, :receiver, :message, :image_url, :timestamp)
            """), {
                "sender": sender_id,
                "receiver": receiver_id,
                "message": message,
                "image_url": image_url,
                "timestamp": datetime.utcnow()
            })

    
        return redirect(url_for("chat", receiver_id=receiver_id)) #reloads page to show new messages

   #get both messages
    messages = fetch_messages(sender_id, receiver_id)
    receiver = fetch_receiver_name(receiver_id)

   #check role in database to determine the base
    base_template = "vendor_base.html" if session.get("role") == "vendor" else "base.html"

    return render_template(
        "chat.html",
        messages=messages,
        receiver_name=receiver,
        receiver_id=receiver_id,
        base_template=base_template  #pass the logic to not have duplicate chat
    )

# fetch messages between the sender and receiver
def fetch_messages(sender_id, receiver_id):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT c.*, u.Username AS SenderName
            FROM Chat c
            JOIN User u ON c.SenderID = u.UserID
            WHERE (c.SenderID = :sender_id AND c.ReceiverID = :receiver_id)
               OR (c.SenderID = :receiver_id AND c.ReceiverID = :sender_id)
            ORDER BY c.Timestamp ASC
        """), {
            "sender_id": sender_id,
            "receiver_id": receiver_id
        })
        return result.fetchall()

# Fetch the name of the receiver
def fetch_receiver_name(receiver_id):
    with engine.connect() as conn:
        return conn.execute(text("SELECT Username FROM User WHERE UserID = :id"), {"id": receiver_id}).scalar()

#list all the users 
@app.route("/chat_users", methods=["GET", "POST"])
def chat_users():
    current_user_id = session.get("user_id")
    if not current_user_id:
        flash("Please log in to view users.", "warning")
        return redirect(url_for("login"))
    
    search_query = request.form.get("search_query", "") 

    with engine.connect() as conn:
        if search_query:
            #search for user
            users = conn.execute(text("""
                SELECT UserID, Username 
                FROM User 
                WHERE UserID != :current_user_id 
                AND Username LIKE :search_query
            """), {"current_user_id": current_user_id, "search_query": f"%{search_query}%"}).fetchall()
        else:
            # show all the users if you cant find the searched one
            users = conn.execute(text("""
                SELECT UserID, Username 
                FROM User 
                WHERE UserID != :current_user_id
            """), {"current_user_id": current_user_id}).fetchall()

    # Set base_template here
    base_template = "vendor_base.html" if session.get("role") == "vendor" else "base.html"
    
    return render_template("chat_users.html", users=users, search_query=search_query, base_template=base_template)
@app.route("/account", methods=["GET", "POST"])
def account():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please log in to view your account info.", "warning")
        return redirect(url_for("login"))

    with engine.connect() as conn:
        user = conn.execute(text("SELECT * FROM User WHERE UserID = :uid"), {"uid": user_id}).fetchone()
        addresses = conn.execute(text("SELECT * FROM Address WHERE UserID = :uid"), {"uid": user_id}).fetchall()

    base_template = "vendor_base.html" if session.get("role", "customer") == "vendor" else "base.html"
    return render_template("account.html", user=user, addresses=addresses, base_template=base_template)

@app.route("/add_address", methods=["GET", "POST"])
@login_required  # Optional: if you use login-based access
def add_address():
    if request.method == "POST":
        street = request.form.get("street")
        city = request.form.get("city")
        state = request.form.get("state")
        zip_code = request.form.get("zip_code")
        country = request.form.get("country")
        is_default = request.form.get("is_default") == "on"
        user_id = session.get("user_id")  # Adjust if you use a different session key

        if not all([street, city, state, zip_code, country]):
            error = "All fields are required."
            return render_template("add_address.html", error=error)

        # If is_default is true, unset existing default
        if is_default:
            Address.query.filter_by(user_id=user_id, is_default=True).update({"is_default": False})
        
        new_address = Address(
            user_id=user_id,
            street=street,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            is_default=is_default
        )
        db.session.add(new_address)
        db.session.commit()

        return redirect(url_for("account"))  # Or another route

    return render_template("add_address.html")

@app.route('/product/<int:product_id>/review', methods=['POST'])
def submit_review(product_id):
    if 'user_id' not in session:
        flash("You must be logged in to leave a review.", "warning")
        return redirect(url_for('login'))

    customer_id = session['user_id']
    rating = int(request.form.get('rating'))
    description = request.form.get('description')
    image_url = request.form.get('image_url')  # optional

    # Check if the user has purchased the product
    with engine.connect() as conn:
        purchase_check = conn.execute(text("""
            SELECT 1 
            FROM `Orders` o
            JOIN `Orderitems` oi ON o.OrderID = oi.OrderID
            WHERE o.CustomerID = :customer_id AND oi.ProductID = :product_id
            LIMIT 1
        """), {
            "customer_id": customer_id,
            "product_id": product_id
        }).fetchone()


        if not purchase_check:
            flash("You can only review products you've purchased.", "danger")
            return redirect(url_for('product_detail', product_id=product_id))

    # Insert the review
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO review (CustomerID, ProductID, Rating, Description, ImageURL, Date)
            VALUES (:customer_id, :product_id, :rating, :description, :image_url, CURRENT_DATE())
        """), {
            "customer_id": customer_id,
            "product_id": product_id,
            "rating": rating,
            "description": description,
            "image_url": image_url or None
        })

    flash("Your review has been submitted!", "success")
    return redirect(url_for('product_detail', product_id=product_id))

@app.route("/create_complaint", methods=["GET", "POST"])
def create_complaint():
    if session.get("role") != "customer":
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        demand = request.form.get("demand")
        product_id = request.form.get("product_id") 

        try:
            with engine.begin() as conn:
                insert_complaint = text("""
                    INSERT INTO Complaints (CustomerID, ProductID, Date, Title, Description, Demand)
                    VALUES (:customer_id, :product_id, CURRENT_DATE, :title, :description, :demand)
                """)
                conn.execute(insert_complaint, {
                    "customer_id": user_id,
                    "product_id": product_id,
                    "title": title,
                    "description": description,
                    "demand": demand
                })
            flash("Complaint submitted successfully!", "success")
            return redirect(url_for("home2"))
        except Exception as e:
            return f"<h3>Error submitting complaint: {e}</h3>"

    # Fetch ordered products for this customer, excluding those with confirmed complaints
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT p.ProductID, p.Title, o.OrderDate
            FROM Orders o
            JOIN OrderItems oi ON o.OrderID = oi.OrderID
            JOIN Products p ON oi.ProductID = p.ProductID
            WHERE o.UserID = :user_id
            AND p.ProductID NOT IN (
                SELECT ProductID FROM Complaints WHERE CustomerID = :user_id AND Status = 'confirmed'
            )
        """), {"user_id": user_id})

        ordered_products = result.fetchall()

    return render_template("create_complaint.html", ordered_products=ordered_products)

@app.route("/admin/review_complaints", methods=["GET", "POST"])
def admin_review_complaints():
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))
    
    with engine.connect() as conn:
        query = text("""
            SELECT 
                c.ComplaintID AS id,
                c.Title AS title,
                c.Description AS description,
                c.Status AS status,
                c.Demand AS category,
                p.Title AS product_title,
                u.Name AS customer_name
            FROM Complaints c
            JOIN Products p ON c.ProductID = p.ProductID
            JOIN User u ON c.CustomerID = u.UserID
        """)
        complaints = conn.execute(query).fetchall()

    
    # Categorize complaints into pending, confirmed, and rejected
    categorized_complaints = {
        "pending": [],
        "confirmed": [],
        "rejected": []
    }

    for complaint in complaints:
        if complaint.status == "pending":
            categorized_complaints["pending"].append(complaint)
        elif complaint.status == "confirmed": 
            categorized_complaints["confirmed"].append(complaint)
        elif complaint.status == "rejected":
            categorized_complaints["rejected"].append(complaint)


    return render_template("admin_review_complaints.html", complaints=categorized_complaints)

@app.route("/admin/resolve_complaint/<int:complaint_id>", methods=["POST"])
def resolve_complaint(complaint_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))
    
    action = request.form["action"]  # Now this should work since 'action' is part of the form
    
    status = 'rejected' if action == 'reject' else 'confirmed'
    
    try:
        with engine.begin() as conn:
            update_status = text("""
                UPDATE Complaints
                SET Status = :status
                WHERE ComplaintID = :complaint_id
            """)
            conn.execute(update_status, {"status": status, "complaint_id": complaint_id})
        
        flash(f"Complaint {complaint_id} has been {status}.", "success")
        return redirect(url_for("admin_review_complaints"))
    except Exception as e:
        flash(f"Error resolving complaint: {e}", "danger")
        return redirect(url_for("admin_review_complaints"))

@app.route("/admin/reject_complaint/<int:complaint_id>", methods=["POST"])
def reject_complaint(complaint_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))
    
    try:
        with engine.begin() as conn:
            # Update the complaint status to 'rejected'
            update_status = text("""
                UPDATE Complaints
                SET Status = 'rejected'
                WHERE ComplaintID = :complaint_id
            """)
            conn.execute(update_status, {"complaint_id": complaint_id})
        
        flash(f"Complaint {complaint_id} has been rejected.", "success")
        return redirect(url_for("admin_review_complaints"))
    except Exception as e:
        flash(f"Error rejecting complaint: {e}", "danger")
        return redirect(url_for("admin_review_complaints"))

@app.route("/admin/process_complaint/<int:complaint_id>", methods=["POST"])
def process_complaint(complaint_id):
    if session.get("role") != "admin":
        flash("Unauthorized access. Admins only.", "danger")
        return redirect(url_for("login"))
    
    # Process the complaint to the next stage: processing → complete
    try:
        with engine.begin() as conn:
            update_status = text("""
                UPDATE Complaints
                SET Status = 'processing'
                WHERE ComplaintID = :complaint_id AND Status = 'confirmed'
            """)
            conn.execute(update_status, {"complaint_id": complaint_id})
        
        flash(f"Complaint {complaint_id} is now processing.", "success")
        return redirect(url_for("admin_review_complaints"))
    except Exception as e:
        flash(f"Error processing complaint: {e}", "danger")
        return redirect(url_for("admin_review_complaints"))

@app.route("/customer/complaints")
def customer_complaints():
    if session.get("role") != "customer":
        return redirect(url_for("login"))
    
    customer_id = session.get("customer_id")
    
    with engine.connect() as conn:
        query = text("""
            SELECT c.ComplaintID, c.Title, c.Status, p.Title AS ProductTitle
            FROM Complaints c
            JOIN Products p ON c.ProductID = p.ProductID
            WHERE c.CustomerID = :customer_id
        """)
        complaints = conn.execute(query, {"customer_id": customer_id}).fetchall()
    
    return render_template("customer_complaints.html", complaints=complaints)

  # Run the Flask application

if __name__ == '__main__':
    app.run(debug=True)
