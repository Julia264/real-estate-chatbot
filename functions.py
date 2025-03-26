
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import openai
import re
import datetime
from config import get_db_connection

EMAIL_HOST ='smtp.gmail.com'
EMAIL_PORT =587
EMAIL_USER ='beterramzy667@gmail.com'
EMAIL_PASSWORD ='sjza xqkg mgze ogpj'
TEAM_EMAIL ='Sharyai2025@gmail.com'




def extract_client_preferences(user_message):

    extracted_info = {
        "property_preferences": "",
        "budget": 0,
        "location": "",
        "property_type": "",
        "bedrooms": 0,
        "bathrooms": 0
    }

    # Extract budget
    budget_match = re.search(r"(\d+(?:,\d{3})*)\s*(دولار|مليون|ألف|جنيه)", user_message)
    if budget_match:
        amount = int(budget_match.group(1).replace(",", ""))
        unit = budget_match.group(2)
        extracted_info["budget"] = amount * 1_000_000 if unit == "مليون" else amount * 1_000

    # Extract location (e.g., التجمع الخامس, 6 أكتوبر)
    locations = ["العبور","الرياض","دبي ","التجمع الخامس","مدينة نصر","مصر الجديده","المعادي","الرحاب","الشيخ زايد"," مدينتي", "6 أكتوبر", "العاصمة الإدارية", "الساحل الشمالي"]
    for loc in locations:
        if loc in user_message:
            extracted_info["location"] = loc
            break

    # Extract property type (e.g., شقة, فيلا)
    property_types = ["مطعم","عياده","محل","شقه","شقة", "فيلا", "دوبلكس", "بنتهاوس"]
    for ptype in property_types:
        if ptype in user_message:
            extracted_info["property_type"] = ptype
            break

    # Extract bedrooms
    bedrooms_match = re.search(r"(\d+)\s*غرف", user_message)
    if bedrooms_match:
        extracted_info["bedrooms"] = int(bedrooms_match.group(1))

    # Extract bathrooms
    bathrooms_match = re.search(r"(\d+)\s*حمام", user_message)
    if bathrooms_match:
        extracted_info["bathrooms"] = int(bathrooms_match.group(1))

    return extracted_info


def send_email(to_email, subject, body):
    """
    Send an email to the specified address.
    """
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
def schedule_viewing(arguments):
    logging.info(f"Received arguments: {arguments}")

    # Extract client information from arguments
    client_id = arguments.get('client_id')
    name = arguments.get('name', 'Unknown')
    phone = arguments.get('phone', 'Unknown')
    email = arguments.get('email', 'Unknown')
    property_id = arguments.get('property_id', 'Not Provided')
    conversation_id = arguments.get('conversation_id')
    # 🛠 Ask for missing details if not provided
    desired_date = arguments.get('desired_date')
    desired_time = arguments.get('desired_time')
    meeting_type = arguments.get('meeting_type')

    if not desired_date or not desired_time or not meeting_type:
        return {
            "message": "📅 من فضلك اختر تاريخ ووقت للمعاينة، وهل تفضل الاجتماع عبر زووم أم زيارة ميدانية؟"
        }

    developer_name = get_developer_name_from_database(property_id) or "Unknown Developer"
    property_name = get_property_name_from_database(property_id) or "Unknown Property"

    # ✅ Fetch conversation summary
    summary = advanced_conversation_summary_from_db(client_id, conversation_id)

    # 📨 Send email with correct details
    subject = f"🔔 معاينة وحدة جديدة - ID {property_id}"
    body = f"""
    📝 معلومات العميل:
    - client id : {client_id}
    - Name : {name}
    - Phone : {phone}
    - Email: {email}
    - property_id :{property_id}
    - Unit Name: {property_name}
    - Devloper : {developer_name}
    - Meeting type: {meeting_type}
    - Date : {desired_date}
    - Time : {desired_time}
    
    🔎 ملخص المحادثة:
    {summary}
    """

    logging.info(f"Prepared email body: {body}")
    send_email(TEAM_EMAIL, subject, body)

    return {
        "message": "✅ تم حجز موعد المعاينة بنجاح!",
        "client_id": client_id,
        "property_id": property_id,
        "developer": developer_name,
        "date": desired_date,
        "time": desired_time,
        "meeting_type": meeting_type,
    }

def retrieve_lead_info(client_id):
    """Retrieve client details from the leads table in MySQL instead of Excel."""
    if not client_id:
        return None

    query = "SELECT * FROM leads WHERE user_id = %s"
    params = (client_id,)
    result = db_operations.fetch_data(query, params)

    if result:
        print("✅ Lead info fetched from MySQL")
        return result[0]  # Return first matched lead as a dictionary

    print("❌ Lead not found in MySQL")
    return None
def get_developer_name_from_database(property_id):
    query = """
        SELECT d.name_ar AS developer_name
        FROM units u
        JOIN developers d ON u.developer_id = d.id
        WHERE u.id = %s
    """
    result = db_operations.fetch_data(query, (property_id,))
    if result:
        return result[0].get('developer_name', 'Unknown Developer')
    return "Unknown Developer"

def get_property_name_from_database(property_id):
    query = "SELECT name_ar FROM units WHERE id = %s"
    params = (property_id,)
    result = db_operations.fetch_data(query, params)

    if result:
        return { result[0]['name_ar']}

    return {"Unknown Property"}


def search_new_launches(arguments):
    """🔍 Dynamically search new launches based on location, budget, bedrooms, bathrooms."""
    try:
        budget = float(arguments.get("budget", 0))
        location = arguments.get("location", "").strip().lower()
        bedrooms = int(arguments.get("bedrooms", 0))
        bathrooms = int(arguments.get("bathrooms", 0))

        # Build dynamic location condition by fetching city ID
        city_query = "SELECT id FROM cities WHERE LOWER(name_en) LIKE %s OR LOWER(name_ar) LIKE %s LIMIT 1"
        city_params = (f"%{location}%", f"%{location}%")
        city_result = db_operations.fetch_data(city_query, city_params)

        if not city_result:
            return {"message": "❌ لم يتم العثور على المدينة المذكورة في قاعدة البيانات.", "results": []}

        city_id = city_result[0]["id"]

        # Prepare query
        query = """
            SELECT * FROM new_launches
            WHERE city_id = %s
            AND price BETWEEN %s AND %s
            AND (bedrooms >= %s OR bedrooms IS NULL)
            AND (bathrooms >= %s OR bathrooms IS NULL)
            ORDER BY created_at DESC
            LIMIT 5
        """
        params = (
            city_id,
            budget * 0.7,
            budget * 1.3,
            bedrooms,
            bathrooms
        )

        results = db_operations.fetch_data(query, params)

        if results:
            return {
                "message": "✅ تم العثور على بعض الخيارات التي تناسب طلبك:",
                "results": results
            }

        return {
            "message": "❌ لم يتم العثور على مشروعات جديدة تحت الإنشاء بالمواصفات المطلوبة.",
            "results": []
        }

    except Exception as e:
        print(f"🚨 Error in search_new_launches: {e}")
        return {"error": str(e)}


# In functions.py
# In functions.py
def create_lead(data):
    """
    Create or update a lead in the database based on provided data.
    Updates only fields provided in the chat without overwriting existing data with blanks.
    """
    user_id = data.get("user_id")
    if not user_id:
        return {"success": False, "message": "User ID is required."}

    # Check if the lead exists
    query = "SELECT * FROM leads WHERE user_id = %s"
    existing_lead = db_operations.fetch_data(query, (user_id,))

    if existing_lead:
        existing_lead = existing_lead[0]  # Get existing lead data
        update_fields = []
        update_values = []

        # Loop through the fields and update only if new values are provided
        fields = ["name", "phone", "email", "property_preferences", "budget", "location", "property_type", "bedrooms", "bathrooms"]
        for field in fields:
            new_value = data.get(field)
            if new_value not in [None, "", 0]:
                update_fields.append(f"{field} = %s")
                update_values.append(new_value)

        if update_fields:
            update_query = f"UPDATE leads SET {', '.join(update_fields)} WHERE user_id = %s"
            update_values.append(user_id)
            db_operations.execute_query(update_query, tuple(update_values))
            logging.info(f"✅ Lead updated successfully for User ID {user_id} with new data.")
        else:
            logging.info(f"⚠️ No new data to update for User ID {user_id}.")
    else:
        # Insert a new lead with available data
        insert_query = """
            INSERT INTO leads (user_id, name, phone, email, property_preferences, budget, location, property_type, bedrooms, bathrooms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        insert_params = (
            user_id,
            data.get("name", ""),
            data.get("phone", ""),
            data.get("email", ""),
            data.get("property_preferences", ""),
            data.get("budget", 0),
            data.get("location", ""),
            data.get("property_type", ""),
            data.get("bedrooms", 0),
            data.get("bathrooms", 0)
        )
        db_operations.execute_query(insert_query, insert_params)
        logging.info(f"✅ New lead created successfully for User ID {user_id}.")

    return {"success": True, "message": "Lead saved/updated successfully."}

def get_city_aliases_from_db():
    query = "SELECT id, name_en, name_ar FROM cities"
    cities = db_operations.fetch_data(query)
    city_map = {}

    for city in cities:
        # Create a keyword dictionary entry with various lowercase aliases
        aliases = [
            city['name_en'].lower(),
            city['name_ar'].lower(),
            city['name_en'].lower().replace("city", "").strip(),
            city['name_en'].lower().replace(" ", ""),
            city['name_en'].lower().replace("october", "6th of october"),
            city['name_en'].lower().replace("october", "6 october"),
        ]
        aliases = list(set(aliases))  # remove duplicates
        city_map[city['id']] = aliases
    return city_map

def find_city_ids_for_location(location_input, city_map):
    location_input = location_input.strip().lower()
    matched_city_ids = []

    for city_id, aliases in city_map.items():
        for alias in aliases:
            if alias in location_input:
                matched_city_ids.append(city_id)
                break  # stop checking aliases for this city once matched

    return matched_city_ids


import difflib
import db_operations
import json
from datetime import datetime

def property_search(arguments):
    try:
        # ✅ Extract search criteria
        budget = float(arguments.get('budget', 0))  # Budget is required
        location = arguments.get('location', '').strip().lower()  # Location is required

        # ✅ Dynamically find matching city IDs based on location
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Find city IDs based on the location input
        city_query = """
            SELECT id FROM cities
            WHERE LOWER(name_ar) LIKE %s OR LOWER(name_en) LIKE %s
        """
        cursor.execute(city_query, (f"%{location}%", f"%{location}%"))
        city_ids = [row['id'] for row in cursor.fetchall()]

        if not city_ids:
            print("⚠️ No city matched for the location input.")
            return {"source": "Database", "data": [], "message": "لم يتم العثور على مدينة مطابقة لهذا الموقع."}

        # ✅ Build the SQL query dynamically
        property_query = """
        SELECT * FROM units 
        WHERE CAST(price AS UNSIGNED) BETWEEN %s AND %s
        AND area_id IN ({})
        AND status = 1
        LIMIT 3;
        """.format(",".join(str(cid) for cid in city_ids))

        # ✅ Prepare query parameters
        params = (
            budget * 0.7,  # 70% of the budget
            budget * 1.2,  # 130% of the budget
        )

        # Log the final SQL query and parameters
        print(f"📝 Final SQL Query: {property_query}")
        print(f"📝 Query Parameters: {params}")

        # Execute the query
        cursor.execute(property_query, params)
        properties_found = cursor.fetchall()

        cursor.close()
        conn.close()

        # ✅ Convert datetime objects to strings
        def serialize_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        # Serialize the results
        properties_found_serialized = json.loads(json.dumps(properties_found, default=serialize_datetime))

        if properties_found_serialized:
            print("✅ Data fetched from MySQL")
            return {
                "source": "Database",
                "data": properties_found_serialized,
                "message": "تم العثور على بعض الخيارات التي تناسب طلبك:"
            }

        print("⚠️ No data found in MySQL for these parameters.")
        return {"source": "Database", "data": [], "message": "لم يتم العثور على نتائج في الوقت الحالي."}

    except Exception as e:
        print(f"🚨 Error in property_search: {e}")
        return {"error": str(e)}
def serialize_mysql_result(results):
    """
    Convert MySQL result datetimes or other non-serializable types to JSON-serializable formats.
    """
    for row in results:
        for key, value in row.items():
            if isinstance(value, (datetime.date, datetime.datetime)):
                row[key] = value.strftime('%Y-%m-%d %H:%M:%S')
    return results
def log_conversation_to_db(conversation_id, user_id, description):
    """
    Logs each message into the MySQL `conversations` table.
    - If a conversation exists, it updates the `description` JSON field.
    - If it's a new conversation, it inserts a new record.
    """

    # 1️⃣ Check if the conversation already exists
    check_query = "SELECT description FROM conversations WHERE conversation_id = %s AND user_id = %s"
    check_params = (conversation_id, user_id)
    result = db_operations.fetch_data(check_query, check_params)

    if result:
        # 2️⃣ If conversation exists, load previous messages
        conversation_json = result[0]["description"]
        conversation_data = json.loads(conversation_json)
    else:
        # 3️⃣ If no conversation exists, start a new conversation
        conversation_data = []

    # 4️⃣ Append the new message (description) to the conversation
    conversation_data.append({
        "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # Fix: Use datetime.now() directly
        "Description": description
    })

    # Convert conversation data to JSON format
    conversation_json = json.dumps(conversation_data, ensure_ascii=False)

    if result:
        # 5️⃣ Update the existing conversation
        update_query = "UPDATE conversations SET description = %s, updated_at = NOW() WHERE conversation_id = %s AND user_id = %s"
        update_params = (conversation_json, conversation_id, user_id)
        db_operations.execute_query(update_query, update_params)
    else:
        # 6️⃣ Insert a new conversation
        insert_query = "INSERT INTO conversations (conversation_id, user_id, description, created_at, updated_at) VALUES (%s, %s, %s, NOW(), NOW())"
        insert_params = (conversation_id, user_id, conversation_json)
        db_operations.execute_query(insert_query, insert_params)

    print(f"✅ Logged to MySQL: {description}")

import db_operations
def advanced_conversation_summary_from_db(client_id, conversation_id):
    """
    Fetch conversation from DB by conversation_id, summarize it, and send by email.
    """
    try:
        # 1️⃣ Fetch conversation from DB
        query = "SELECT description FROM conversations WHERE conversation_id = %s AND user_id = %s"
        params = (conversation_id, client_id)
        result = db_operations.fetch_data(query, params)

        if not result:
            return "❌ No conversation found for the given client and conversation ID."

        conversation_json = result[0]["description"]
        conversation_data = json.loads(conversation_json)

        # 2️⃣ Format conversation
        formatted_conversation = "\n".join(
            f"Client: {msg['Description']}" if "Client" in msg["Description"] else f"Bot: {msg['Description']}"
            for msg in conversation_data
        )

        # 3️⃣ Summarization prompt
        prompt = f"""
        أنت مساعد مبيعات AI. قم بتلخيص المحادثة التالية بين عميل وروبوت دردشة باللهجة المصرية.
        يجب أن يتضمن الملخص:
        - متطلبات العميل (الميزانية، الموقع، نوع العقار)
        - أي اعتراضات أو مخاوف
        - الرغبة في مقابلة أو معاينة
        - أي اهتمام بمطورين محددين.

        Conversation:
        {formatted_conversation}

        Summary:
        """

        # Debug: Print the prompt
        print(f"📋 Prompt for summarization: {prompt}")



        # Call OpenAI API to generate the summary
        response = openai.chat.completions.create(
            model="gpt-4-turbo",  # Use the appropriate model
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes conversations in Egyptian Arabic."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.2
        )

        # Extract the summary from the response
        summary = response.choices[0].message.content.strip()

        # Debug: Print the summary
        print(f"📝 Generated summary: {summary}")

        return summary

    except Exception as e:
        # Debug: Print the error
        print(f"🚨 Error generating summary: {e}")
        return f"Error generating summary: {e}"