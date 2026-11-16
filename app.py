from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import get_db_connection
from decimal import Decimal, InvalidOperation
app = Flask(__name__)
app.secret_key = "pantrypal_demo_secret"
FAMILY_ID = 1

# =====================================
# DATABASE CONNECTION
# =====================================
def get_connection():
   connection = get_db_connection()
   if connection is None:
       raise RuntimeError(
           "ไม่สามารถเชื่อมต่อ MySQL ได้ กรุณาตรวจสอบ database.py"
       )
   return connection

# =====================================
# HELPER FUNCTIONS
# =====================================
def get_ingredients(cursor):
   cursor.execute("""
       SELECT ingredient_id, ingredient_name, unit
       FROM Ingredient
       ORDER BY ingredient_name
   """)
   return cursor.fetchall()

def valid_quantity(value):
   try:
       return Decimal(value) > 0
   except (InvalidOperation, TypeError, ValueError):
       return False

# =====================================
# DASHBOARD
# =====================================
@app.route("/")
def dashboard():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT COUNT(*) AS total
           FROM Pantry_Item
           WHERE family_id = %s
       """, (FAMILY_ID,))
       total_items = cursor.fetchone()["total"]
       cursor.execute("""
           SELECT COUNT(*) AS expiring
           FROM Pantry_Item
           WHERE family_id = %s
           AND expiry_date >= CURDATE()
           AND expiry_date <= DATE_ADD(CURDATE(), INTERVAL 3 DAY)
       """, (FAMILY_ID,))
       expiring_items = cursor.fetchone()["expiring"]
       return render_template(
           "dashboard.html",
           total_items=total_items,
           expiring_items=expiring_items
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# MY PANTRY - READ
# =====================================
@app.route("/pantry")
def pantry():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT
               p.pantry_item_id,
               i.ingredient_name,
               p.quantity,
               i.unit,
               p.purchase_date,
               p.expiry_date
           FROM Pantry_Item p
           JOIN Ingredient i
               ON p.ingredient_id = i.ingredient_id
           WHERE p.family_id = %s
           ORDER BY p.expiry_date IS NULL, p.expiry_date
       """, (FAMILY_ID,))
       pantry_items = cursor.fetchall()
       return render_template(
           "pantry.html",
           pantry_items=pantry_items
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# MY PANTRY - CREATE
# =====================================
@app.route("/pantry/add", methods=["GET", "POST"])
def add_pantry():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       ingredients = get_ingredients(cursor)
       if request.method == "POST":
           ingredient_id = request.form.get("ingredient_id")
           quantity = request.form.get("quantity", "").strip()
           purchase_date = request.form.get("purchase_date") or None
           expiry_date = request.form.get("expiry_date") or None
           if not valid_quantity(quantity):
               flash("จำนวนอาหารต้องมากกว่า 0")
               return render_template(
                   "pantry_form.html",
                   ingredients=ingredients,
                   item=None
               )
           if purchase_date and expiry_date and expiry_date < purchase_date:
               flash("วันหมดอายุต้องไม่ก่อนวันที่ซื้อ")
               return render_template(
                   "pantry_form.html",
                   ingredients=ingredients,
                   item=None
               )
           cursor.execute("""
               INSERT INTO Pantry_Item
               (family_id, ingredient_id, quantity,
                purchase_date, expiry_date)
               VALUES (%s, %s, %s, %s, %s)
           """, (
               FAMILY_ID,
               ingredient_id,
               quantity,
               purchase_date,
               expiry_date
           ))
           connection.commit()
           flash("เพิ่มอาหารเรียบร้อยแล้ว")
           return redirect(url_for("pantry"))
       return render_template(
           "pantry_form.html",
           ingredients=ingredients,
           item=None
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# MY PANTRY - UPDATE
# =====================================
@app.route("/pantry/edit/<int:item_id>", methods=["GET", "POST"])
def edit_pantry(item_id):
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT *
           FROM Pantry_Item
           WHERE pantry_item_id = %s
           AND family_id = %s
       """, (item_id, FAMILY_ID))
       item = cursor.fetchone()
       if item is None:
           return "ไม่พบรายการอาหาร", 404
       ingredients = get_ingredients(cursor)
       if request.method == "POST":
           ingredient_id = request.form.get("ingredient_id")
           quantity = request.form.get("quantity", "").strip()
           purchase_date = request.form.get("purchase_date") or None
           expiry_date = request.form.get("expiry_date") or None
           if not valid_quantity(quantity):
               flash("จำนวนอาหารต้องมากกว่า 0")
           elif purchase_date and expiry_date and expiry_date < purchase_date:
               flash("วันหมดอายุต้องไม่ก่อนวันที่ซื้อ")
           else:
               cursor.execute("""
                   UPDATE Pantry_Item
                   SET ingredient_id = %s,
                       quantity = %s,
                       purchase_date = %s,
                       expiry_date = %s
                   WHERE pantry_item_id = %s
                   AND family_id = %s
               """, (
                   ingredient_id,
                   quantity,
                   purchase_date,
                   expiry_date,
                   item_id,
                   FAMILY_ID
               ))
               connection.commit()
               flash("แก้ไขข้อมูลเรียบร้อยแล้ว")
               return redirect(url_for("pantry"))
           # โหลดข้อมูลเดิมกลับมาแสดง
           item.update({
               "ingredient_id": ingredient_id,
               "quantity": quantity,
               "purchase_date": purchase_date,
               "expiry_date": expiry_date
           })
       return render_template(
           "pantry_form.html",
           ingredients=ingredients,
           item=item
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# MY PANTRY - DELETE
# =====================================
@app.route("/pantry/delete/<int:item_id>", methods=["POST"])
def delete_pantry(item_id):
   connection = get_connection()
   cursor = connection.cursor()
   try:
       cursor.execute("""
           DELETE FROM Pantry_Item
           WHERE pantry_item_id = %s
           AND family_id = %s
       """, (item_id, FAMILY_ID))
       connection.commit()
       flash("ลบรายการอาหารเรียบร้อยแล้ว")
       return redirect(url_for("pantry"))
   finally:
       cursor.close()
       connection.close()

# =====================================
# RECIPES
# =====================================
@app.route("/recipes")
def recipes():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT
               r.recipe_id,
               r.recipe_name,
               r.instructions,
               GROUP_CONCAT(
                   CONCAT(
                       i.ingredient_name,
                       ' (',
                       ri.required_quantity,
                       ' ',
                       i.unit,
                       ')'
                   )
                   SEPARATOR ', '
               ) AS ingredients
           FROM Recipe r
           LEFT JOIN Recipe_Ingredient ri
               ON r.recipe_id = ri.recipe_id
           LEFT JOIN Ingredient i
               ON ri.ingredient_id = i.ingredient_id
           GROUP BY
               r.recipe_id,
               r.recipe_name,
               r.instructions
           ORDER BY r.recipe_id
       """)
       recipes_data = cursor.fetchall()
       return render_template(
           "recipes.html",
           recipes=recipes_data
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# SHOPPING LIST - READ
# =====================================
@app.route("/shopping")
def shopping():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT
               s.shopping_id,
               i.ingredient_name,
               s.quantity,
               i.unit,
               s.status
           FROM Shopping_List s
           JOIN Ingredient i
               ON s.ingredient_id = i.ingredient_id
           WHERE s.family_id = %s
           ORDER BY s.shopping_id DESC
       """, (FAMILY_ID,))
       items = cursor.fetchall()
       return render_template(
           "shopping.html",
           items=items
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# SHOPPING LIST - CREATE
# =====================================
@app.route("/shopping/add", methods=["GET", "POST"])
def add_shopping():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       ingredients = get_ingredients(cursor)
       if request.method == "POST":
           ingredient_id = request.form.get("ingredient_id")
           quantity = request.form.get("quantity", "").strip()
           if not valid_quantity(quantity):
               flash("จำนวนต้องมากกว่า 0")
           else:
               cursor.execute("""
                   INSERT INTO Shopping_List
                   (family_id, ingredient_id, quantity, status)
                   VALUES (%s, %s, %s, %s)
               """, (
                   FAMILY_ID,
                   ingredient_id,
                   quantity,
                   "ยังไม่ได้ซื้อ"
               ))
               connection.commit()
               flash("เพิ่มรายการซื้อแล้ว")
               return redirect(url_for("shopping"))
       return render_template(
           "shopping_form.html",
           ingredients=ingredients
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# SHOPPING LIST - UPDATE STATUS
# =====================================
@app.route("/shopping/status/<int:item_id>", methods=["POST"])
def shopping_status(item_id):
   connection = get_connection()
   cursor = connection.cursor()
   try:
       cursor.execute("""
           UPDATE Shopping_List
           SET status = CASE
               WHEN status = 'ซื้อแล้ว' THEN 'ยังไม่ได้ซื้อ'
               ELSE 'ซื้อแล้ว'
           END
           WHERE shopping_id = %s
           AND family_id = %s
       """, (item_id, FAMILY_ID))
       connection.commit()
       return redirect(url_for("shopping"))
   finally:
       cursor.close()
       connection.close()

# =====================================
# SHOPPING LIST - DELETE
# =====================================
@app.route("/shopping/delete/<int:item_id>", methods=["POST"])
def delete_shopping(item_id):
   connection = get_connection()
   cursor = connection.cursor()
   try:
       cursor.execute("""
           DELETE FROM Shopping_List
           WHERE shopping_id = %s
           AND family_id = %s
       """, (item_id, FAMILY_ID))
       connection.commit()
       flash("ลบรายการซื้อเรียบร้อยแล้ว")
       return redirect(url_for("shopping"))
   finally:
       cursor.close()
       connection.close()

# =====================================
# MY FAMILY
# =====================================
@app.route("/family")
def family():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT
               f.family_name,
               m.member_id,
               m.username,
               m.email
           FROM Family f
           JOIN Family_Member fm
               ON f.family_id = fm.family_id
           JOIN Member m
               ON fm.member_id = m.member_id
           WHERE f.family_id = %s
           ORDER BY m.member_id
       """, (FAMILY_ID,))
       members = cursor.fetchall()
       return render_template(
           "family.html",
           members=members
       )
   finally:
       cursor.close()
       connection.close()

# =====================================
# CATEGORIES
# =====================================
@app.route("/categories")
def categories():
   connection = get_connection()
   cursor = connection.cursor(dictionary=True)
   try:
       cursor.execute("""
           SELECT
               c.category_id,
               c.category_name,
               COUNT(i.ingredient_id) AS total_ingredients
           FROM Category c
           LEFT JOIN Ingredient i
               ON c.category_id = i.category_id
           GROUP BY
               c.category_id,
               c.category_name
           ORDER BY c.category_id
       """)
       categories_data = cursor.fetchall()
       return render_template(
           "categories.html",
           categories=categories_data
       )
   finally:
       cursor.close()
       connection.close()



# =====================================
# JSON API FOR FIGMA MAKE
# FAMILY_ID is currently fixed to 1, matching the existing web application.
# =====================================

@app.after_request
def add_cors_headers(response):
    # Development CORS only. Restrict this origin before public production use.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, ngrok-skip-browser-warning"
    response.headers["Access-Control-Max-Age"] = "600"
    return response


def api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def api_date(value):
    return value.isoformat() if value is not None else None


def api_pantry_item(cursor, item_id):
    cursor.execute("""
        SELECT
            p.pantry_item_id,
            p.family_id,
            p.ingredient_id,
            i.ingredient_name,
            i.unit,
            p.quantity,
            p.purchase_date,
            p.expiry_date
        FROM Pantry_Item p
        JOIN Ingredient i ON i.ingredient_id = p.ingredient_id
        WHERE p.pantry_item_id = %s
          AND p.family_id = %s
    """, (item_id, FAMILY_ID))
    row = cursor.fetchone()
    if row is None:
        return None

    return {
        "pantry_item_id": row["pantry_item_id"],
        "family_id": row["family_id"],
        "ingredient_id": row["ingredient_id"],
        "ingredient_name": row["ingredient_name"],
        "name": row["ingredient_name"],
        "unit": row["unit"],
        "quantity": float(row["quantity"]),
        "purchase_date": api_date(row["purchase_date"]),
        "expiry_date": api_date(row["expiry_date"]),
    }


@app.route("/api/health", methods=["GET", "OPTIONS"])
def api_health():
    if request.method == "OPTIONS":
        return ("", 204)

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]
        return jsonify({
            "success": True,
            "message": "PantryPal API connected",
            "database": database_name
        })
    except Exception as exc:
        app.logger.exception("API health check failed")
        return api_error("Backend or database connection failed", 503)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/ingredients", methods=["GET", "OPTIONS"])
def api_ingredients():
    if request.method == "OPTIONS":
        return ("", 204)

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                i.ingredient_id,
                i.ingredient_name,
                i.unit,
                i.category_id,
                c.category_name
            FROM Ingredient i
            LEFT JOIN Category c ON c.category_id = i.category_id
            ORDER BY i.ingredient_name
        """)
        rows = cursor.fetchall()
        ingredients = [{
            "ingredient_id": row["ingredient_id"],
            "ingredient_name": row["ingredient_name"],
            "name": row["ingredient_name"],
            "unit": row["unit"],
            "category_id": row["category_id"],
            "category_name": row["category_name"],
        } for row in rows]
        return jsonify({"success": True, "ingredients": ingredients})
    except Exception:
        app.logger.exception("Could not load ingredients")
        return api_error("Could not load ingredients", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/pantry", methods=["GET", "POST", "OPTIONS"])
def api_pantry():
    if request.method == "OPTIONS":
        return ("", 204)

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "GET":
            cursor.execute("""
                SELECT
                    p.pantry_item_id,
                    p.family_id,
                    p.ingredient_id,
                    i.ingredient_name,
                    i.unit,
                    p.quantity,
                    p.purchase_date,
                    p.expiry_date
                FROM Pantry_Item p
                JOIN Ingredient i ON i.ingredient_id = p.ingredient_id
                WHERE p.family_id = %s
                ORDER BY p.expiry_date IS NULL, p.expiry_date, p.pantry_item_id DESC
            """, (FAMILY_ID,))
            rows = cursor.fetchall()
            items = [{
                "pantry_item_id": row["pantry_item_id"],
                "family_id": row["family_id"],
                "ingredient_id": row["ingredient_id"],
                "ingredient_name": row["ingredient_name"],
                "name": row["ingredient_name"],
                "unit": row["unit"],
                "quantity": float(row["quantity"]),
                "purchase_date": api_date(row["purchase_date"]),
                "expiry_date": api_date(row["expiry_date"]),
            } for row in rows]
            return jsonify({"success": True, "items": items, "count": len(items)})

        data = request.get_json(silent=True) or {}
        ingredient_id = data.get("ingredient_id")
        quantity = data.get("quantity")
        purchase_date = data.get("purchase_date") or None
        expiry_date = data.get("expiry_date") or None

        try:
            ingredient_id = int(ingredient_id)
            quantity_value = Decimal(str(quantity))
            if quantity_value <= 0:
                raise ValueError()
        except (TypeError, ValueError, InvalidOperation):
            return api_error("ingredient_id must be valid and quantity must be greater than 0")

        if purchase_date and expiry_date and expiry_date < purchase_date:
            return api_error("expiry_date cannot be earlier than purchase_date")

        cursor.execute(
            "SELECT ingredient_id FROM Ingredient WHERE ingredient_id = %s",
            (ingredient_id,)
        )
        if cursor.fetchone() is None:
            return api_error("Ingredient not found", 404)

        cursor.execute("""
            INSERT INTO Pantry_Item
                (family_id, ingredient_id, quantity, purchase_date, expiry_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (FAMILY_ID, ingredient_id, str(quantity_value), purchase_date, expiry_date))
        connection.commit()
        new_id = cursor.lastrowid
        item = api_pantry_item(cursor, new_id)
        return jsonify({"success": True, "message": "Pantry item created", "item": item}), 201

    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Pantry API request failed")
        return api_error("Pantry request failed. Check the Flask terminal for details.", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/api/pantry/<int:item_id>", methods=["GET", "PUT", "PATCH", "DELETE", "OPTIONS"])
def api_pantry_item_detail(item_id):
    if request.method == "OPTIONS":
        return ("", 204)

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "GET":
            item = api_pantry_item(cursor, item_id)
            if item is None:
                return api_error("Pantry item not found", 404)
            return jsonify({"success": True, "item": item})

        cursor.execute("""
            SELECT pantry_item_id
            FROM Pantry_Item
            WHERE pantry_item_id = %s AND family_id = %s
        """, (item_id, FAMILY_ID))
        if cursor.fetchone() is None:
            return api_error("Pantry item not found", 404)

        if request.method == "DELETE":
            cursor.execute("""
                DELETE FROM Pantry_Item
                WHERE pantry_item_id = %s AND family_id = %s
            """, (item_id, FAMILY_ID))
            connection.commit()
            return jsonify({"success": True, "message": "Pantry item deleted"})

        data = request.get_json(silent=True) or {}
        ingredient_id = data.get("ingredient_id")
        quantity = data.get("quantity")
        purchase_date = data.get("purchase_date") or None
        expiry_date = data.get("expiry_date") or None

        try:
            ingredient_id = int(ingredient_id)
            quantity_value = Decimal(str(quantity))
            if quantity_value <= 0:
                raise ValueError()
        except (TypeError, ValueError, InvalidOperation):
            return api_error("ingredient_id must be valid and quantity must be greater than 0")

        if purchase_date and expiry_date and expiry_date < purchase_date:
            return api_error("expiry_date cannot be earlier than purchase_date")

        cursor.execute(
            "SELECT ingredient_id FROM Ingredient WHERE ingredient_id = %s",
            (ingredient_id,)
        )
        if cursor.fetchone() is None:
            return api_error("Ingredient not found", 404)

        cursor.execute("""
            UPDATE Pantry_Item
            SET ingredient_id = %s,
                quantity = %s,
                purchase_date = %s,
                expiry_date = %s
            WHERE pantry_item_id = %s AND family_id = %s
        """, (
            ingredient_id, str(quantity_value), purchase_date,
            expiry_date, item_id, FAMILY_ID
        ))
        connection.commit()
        item = api_pantry_item(cursor, item_id)
        return jsonify({"success": True, "message": "Pantry item updated", "item": item})

    except Exception:
        if connection:
            connection.rollback()
        app.logger.exception("Pantry item API request failed")
        return api_error("Pantry item request failed. Check the Flask terminal for details.", 500)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# =====================================
# RUN FLASK
# ต้องอยู่ท้ายสุดเท่านั้น
# =====================================
if __name__ == "__main__":
   app.run(
       host="127.0.0.1",
       port=5000,
       debug=True
   )
   