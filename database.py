import os
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com"),
            port=int(os.getenv("DB_PORT", 4000)),
            user=os.getenv("DB_USER", "3qhuLcFWYmLLDwF.root"),
            password=os.getenv("DB_PASSWORD", "Qck6mj0lODbIGZaF"),
            database=os.getenv("DB_NAME", "pantrypal"),
            charset="utf8mb4",
            use_unicode=True,
            ssl_disabled=False
        )
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None


    