from flask import Flask, render_template, redirect, url_for, request, session, flash
import sqlite3
import os
import re
# import stripe

app = Flask(__name__)
app.config["STRIPE_SECRET_KEY"] = "your_stripe_secret_key"
app.config["STRIPE_PUBLIC_KEY"] = "your_stripe_public_key"
# stripe.api_key = app.config["STRIPE_SECRET_KEY"]
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/images'
app.static_folder = 'static'

def secure_filename(filename):
    filename = re.sub(r'[^\w\s.-]', '', filename)
    return filename

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.executescript('''
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS cart;

        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL CHECK (is_admin IN (0, 1))
        );

        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT NOT NULL,
            details TEXT 
        );

        CREATE TABLE cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            image TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );

        INSERT INTO users (username, password, is_admin) VALUES
            ('admin', 'admin', 1),
            ('user', 'user', 0);
    ''')
    conn.commit()
    conn.close()

if not os.path.exists('database.db'):
    init_db()

@app.before_request
def before_request():
    allowed_routes = ['login', 'logout', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.route('/')
def home():
    return render_template('user_home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['is_admin'] = user['is_admin']
            if user['is_admin']:
                return redirect(url_for('admin_home'))
            else:
                return redirect(url_for('user_home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

@app.route('/user_home')
def user_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_home.html')

@app.route('/admin_home')
def admin_home():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('admin_home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/products', methods=['GET', 'POST'])
def products():
    conn = get_db_connection()
    if request.method == 'POST':
        category = request.form.get('categories')  # <--- Change here
        if category:
            products = conn.execute('SELECT * FROM products WHERE category =?', (category,)).fetchall()
        else:
            products = conn.execute('SELECT * FROM products').fetchall()
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    else:
        products = conn.execute('SELECT * FROM products').fetchall()
        categories = conn.execute("SELECT DISTINCT category FROM products").fetchall()
    conn.close()
    return render_template('products.html', products=products, categories=categories)

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    categories = ['Skin Care', 'Body Care', 'Hair Care', 'Others']

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        quantity = request.form['quantity']
        category = request.form['category']
        details = request.form['details']
        new_category = request.form.get('new_category')
        image = request.files.get('image')

        if category == 'Others' and new_category:
            category = new_category
            if new_category not in categories:
                categories.append(new_category)

        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
        else:
            image_path = None

        if image_path:
            image_name = os.path.basename(image_path)

        conn = get_db_connection()
        conn.execute('INSERT INTO products (name, price, quantity, category, image, details) VALUES (?, ?, ?, ?, ?, ?)',
                     (name, price, quantity, category, image_name, details))
        conn.commit()
        conn.close()

        return redirect(url_for('add_product'))

    return render_template('add_product.html', categories=categories)

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cart_items = conn.execute('''
        SELECT c.id, p.name, p.price, c.quantity, p.category, p.image, p.details, p.quantity AS available_quantity
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()
    total = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/manage_products')
def manage_products():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return render_template('manage_products.html', products=products)

@app.route('/edit_product/<int:id>', methods=['POST'])
def edit_product(id):
    name = request.form['name']
    price = request.form['price']
    category = request.form['category']
    quantity = request.form['quantity']
    details = request.form['details']
    image = request.files.get('image')

    conn = get_db_connection()

    if image:
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        image_name = os.path.basename(image_path)
        conn.execute('UPDATE products SET name = ?, price = ?, category = ?, quantity = ?, details = ?, image = ? WHERE id = ?', 
                     (name, price, category, quantity, details, image_name, id))
    else:
        conn.execute('UPDATE products SET name = ?, price = ?, category = ?, quantity = ?, details = ? WHERE id = ?', 
                     (name, price, category, quantity, details, id))
                     
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))

@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_products'))

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_id = session['user_id']

    product = conn.execute('SELECT * FROM products WHERE id =?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.')
        return redirect(url_for('products'))

    cart_item = conn.execute('SELECT * FROM cart WHERE user_id =? AND product_id =?', (user_id, product_id)).fetchone()
    
    if cart_item:
        new_quantity = cart_item['quantity'] 
        if product['quantity']==0:
            flash('Not enough stock available.')
            return redirect(url_for('products'))
        conn.execute('UPDATE cart SET quantity =? WHERE user_id =? AND product_id =?', (new_quantity+1, user_id, product_id))
        product_quantity=new_quantity
    else:
        if product['quantity'] == 0:
            flash('Not enough stock available.')
            return redirect(url_for('products'))
        conn.execute('INSERT INTO cart (user_id, product_id, name, price, category, quantity, image, details) VALUES (?,?,?,?,?,?,?,?)',
                     (user_id, product_id, product['name'], product['price'], product['category'], 1, product['image'], product['details']))
    conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (product['quantity'] - 1, product_id))

    conn.commit()
    conn.close()
    return redirect(url_for('products'))

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    user_id = session['user_id']
    
    try:
        # Fetch the cart item
        cart_item = conn.execute('SELECT * FROM cart WHERE user_id = ? AND product_id = ?', (user_id, product_id)).fetchone()
        
        if cart_item:
            current_quantity = cart_item['quantity']
            if current_quantity > 0:
                # Decrease the quantity in the cart
                conn.execute('UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?', (current_quantity - 1, user_id, product_id))
  
            # Update the product quantity in the products table
            product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if product:
                product_quantity = product['quantity']
                conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (product_quantity + 1, product_id))
            print("Current cart quantity:", current_quantity)
            print("Product quantity in stock:", product_quantity)

        conn.commit()
    except sqlite3.Error as e:
        print("An error occurred:", e.args[0])
        conn.rollback()
    finally:
        conn.close()
    
    return redirect(url_for('cart'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route("/payment", methods=["GET", "POST"])
def payment():
    if request.method == "POST":
        card_number = request.form["card-number"]
        expiration_date = request.form["expiration-date"]
        cvv = request.form["cvv"]
        amount = request.form["amount"]

        try:
            customer = stripe.Customer.create(
                email=request.form["email"],
                source=request.form["stripeToken"]
            )

            charge = stripe.Charge.create(
                amount=amount,
                currency="usd",
                customer=customer.id,
                description="Payment"
            )

            return "Payment successful!"
        except stripe.Error.CardError as e:
            return "Error: {}".format(e)

    return render_template("payment.html")
    return 'Payment successful'
if __name__ == '__main__':
    app.run(debug=True)
