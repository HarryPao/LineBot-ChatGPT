import time
import psycopg2
from psycopg2 import sql

class PostgreSQLHandler:
    # def __init__(self, dbname, user, password, host, port):
    #     self.connection = psycopg2.connect(
    #         dbname=dbname,
    #         user=user,
    #         password=password,
    #         host=host,
    #         port=port
    #     )
    #     self.cursor = self.connection.cursor()
    def __init__(self, database_url):
        self.connection = psycopg2.connect(database_url)
        self.cursor = self.connection.cursor()

    def create_table(self, table_name, columns):
        query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(
                sql.SQL("{} {}").format(
                    sql.Identifier(column_name),
                    sql.SQL(column_type)
                ) for column_name, column_type in columns.items()
            )
        )
        self.execute_query(query)

    def insert_data(self, table_name, data):
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, data.keys())),
            sql.SQL(', ').join(map(sql.Literal, data.values()))
        )
        self.execute_query(query)

    def select_data(self, table_name, columns=None, condition=None):
        if columns:
            query = sql.SQL("SELECT {} FROM {}").format(
                sql.SQL(', ').join(map(sql.Identifier, columns)),
                sql.Identifier(table_name)
            )
        else:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(table_name))

        if condition:
            query += sql.SQL(" WHERE {}").format(sql.SQL(condition))

        return self.execute_query(query, fetchall=True)

    def update_data(self, table_name, update_data, condition):
        query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(
                sql.SQL("{} = {}").format(
                    sql.Identifier(column),
                    sql.Literal(value)
                ) for column, value in update_data.items()
            ),
            sql.SQL(condition)
        )
        self.execute_query(query)

    def delete_data(self, table_name, condition):
        query = sql.SQL("DELETE FROM {} WHERE {}").format(
            sql.Identifier(table_name),
            sql.SQL(condition)
        )
        self.execute_query(query)

    def execute_query(self, query, fetchall=False):
        try:
            self.cursor.execute(query)
            if fetchall:
                return self.cursor.fetchall()
            else:
                self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            print(f"Error: {e}")
        # finally:
        #     self.cursor.close()

    def close_connection(self):
        self.connection.close()


# Example Usage:

# Initialize the PostgreSQLHandler
# db_handler = PostgreSQLHandler(
#     dbname='YOUR_DB_NAME',
#     user='YOUR_DB_USER',
#     password='YOUR_DB_PWD',
#     host='YOUR_DB_HOST',
#     port='YOUR_DB_SERVER_PORT'
# )

# # Insert data
# user_id = 5678
# user_name = "Joe"
# data_to_insert = {'userid': user_id, 'username': user_name, 'quota': 30}
# db_handler.insert_data('users', data_to_insert)

# # Select data
# selected_data = db_handler.select_data('users', condition=f"username = '{user_name}'")
# print("Selected Data:", selected_data)
# print("userName: ", selected_data[0][1])

# #Update data
# user_id = "Test1234"
# user_name = "Test5678"
# update_condition = "True"
# update_data = {"quota": 50}
# db_handler.update_data('users', update_data, update_condition)


# # Select updated data
# user_data = db_handler.select_data('users', columns=['username', 'userid', 'aimode', 'lastaimsgtime'])
# print("User Data:", user_data)
# for user in user_data:
#     print("user id: ", user[1])

# # Delete data
# delete_condition = "id = 1"
# db_handler.delete_data('example_table', delete_condition)

# Close the connection
# db_handler.close_connection()
