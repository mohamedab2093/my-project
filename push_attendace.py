import psycopg2
from datetime import datetime

# connect to the database
conn = psycopg2.connect(database="zk14", user="odoo14e", password="odoo14e", host="localhost", port="5432")

# Create a cursor object to execute SQL queries
cur = conn.cursor()

# Read data from the text file
with open("zk_export.txt", "r") as file:
    data = file.readlines()
check_in = None
check_out = None

# Insert data into the hr_employee and hr_attendance tables
for line in data:
    employee_number = line.split("\t")[0]
    if line.split("\t")[5]=="I":
        check_in = line.split("\t")[1]
    else:
        check_out = line.split("\t")[1]

    # Check if an employee with the same name already exists
    cur.execute("SELECT id FROM hr_employee WHERE name=%s", (employee_number,))
    employee_id = cur.fetchone()

    if not employee_id:
        # Create a new resource for the employee
        cur.execute("INSERT INTO resource_resource (name, active, create_date, write_date , resource_type , time_efficiency , calendar_id , tz) VALUES (%s, %s, %s, %s ,%s,%s,%s,%s) RETURNING id", (employee_number, True, datetime.now(), datetime.now(), "user", 100 , 1 , "Europe/Brussels"))
        resource_id = cur.fetchone()[0]

        # Insert the employee into the hr_employee table
        employee_data = {
            'name': employee_number,
            'active': True,
            'company_id': 1,
            'gender': None,
            'marital': 'single',
            'children': 0,
            'work_phone': None,
            'mobile_phone': '01008865146',
            'work_email': None,
            'work_location': None,
            'resource_id': resource_id,
            'create_date': datetime.now(),
            'write_date': datetime.now()
        }
        cur.execute("INSERT INTO hr_employee (name, active, company_id, gender, marital, children, work_phone, mobile_phone, work_email, work_location , resource_id , create_date , write_date) VALUES (%(name)s, %(active)s, %(company_id)s, %(gender)s, %(marital)s, %(children)s, %(work_phone)s, %(mobile_phone)s, %(work_email)s, %(work_location)s, %(resource_id)s,%(create_date)s,%(write_date)s)", employee_data)

        # Get the employee ID
        cur.execute("SELECT id FROM hr_employee WHERE name=%s", (employee_number,))
        employee_id = cur.fetchone()[0]

        print("Inserted employee with name:", employee_number)

    # Insert the attendance record
    attendance_data = {
        'employee_id': employee_id,
        'check_in': check_in,
        'check_out': check_out,
        'create_date': datetime.now(),
        'write_date': datetime.now()
    }
    cur.execute("INSERT INTO hr_attendance (employee_id, check_in, check_out, create_date, write_date) VALUES (%(employee_id)s, %(check_in)s,%(check_out)s, %(create_date)s, %(write_date)s)", attendance_data)
    print("Inserted attendance record for employee with name:", employee_number)

# Commit the transaction
conn.commit()

# Close the cursor
cur.close()

# Close the database connection
conn.close()
