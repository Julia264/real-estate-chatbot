import os
import logging
import mysql
import openai
import core_functions
import Assistant
import functions
import datetime
from flask import Flask, render_template, request, jsonify
from query_generator import generate_query, execute_query
import config

# Configure logging
logging.basicConfig(level=logging.INFO)

# Check OpenAI version compatibility
core_functions.check_openai_version()

# Create Flask app
app = Flask(__name__)
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("No OpenAI API key found in environment variables")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Create or load assistant
assistant_id = Assistant.create_assistant(client)


@app.route("/")
def index():
    return render_template("index.html")


@app.route('/start', methods=['GET'])
def start_conversation():
    logging.info("Starting a new conversation...")

    client_info = config.fetch_user_info_from_api()
    client_info["user_id"] = client_info.get("id")

    # Create a new thread
    thread = client.beta.threads.create()
    thread_id = thread.id
    logging.info(f"New thread created with ID: {thread_id}")

    # Store client info
    config.client_sessions[thread_id] = client_info

    # Create a lead
    functions.create_lead({
        "user_id": client_info["user_id"],
        "name": client_info["name"],
        "phone": client_info["phone"],
        "email": client_info["email"],
        "property_preferences": "",
        "budget": 0,
        "location": "",
        "property_type": "",
        "bedrooms": 0,
        "bathrooms": 0
    })

    return jsonify({
        "thread_id": thread_id,
        "client_info": client_info
    })


import mysql.connector
def fetch_data(query, params=None):
    """
    Executes a MySQL query and returns results.
    """
    conn = None
    try:
        conn = config.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        result = cursor.fetchall()
        return result
    except mysql.connector.Error as err:
        logging.error(f"MySQL Error: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/properties', methods=['GET'])
def get_properties():
    """
    API to fetch properties from the database.
    """
    query = "SELECT * FROM units LIMIT 10"  # Modify based on actual table
    properties = fetch_data(query)

    if not properties:
        return jsonify({"message": "No properties found."}), 404

    return jsonify(properties), 200


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    thread_id = data.get('thread_id')
    user_input = f"Current Date: {datetime.datetime.now().strftime('%B %d, %Y')}\n" + data.get('message', '')

    # Retrieve client info from memory if not provided
    client_info = data.get('client_info') or config.client_sessions.get(thread_id, {})

    # Ensure client info is valid
    if not client_info or not client_info.get("user_id"):
        logging.error("❌ Missing client info in /chat request")
        return jsonify({"error": "Missing client info"}), 400

    logging.info(f"Using stored client info for /chat: {client_info}")

    # Extract client details
    user_id = client_info.get("user_id")
    name = client_info.get("name", "Unknown")
    phone = client_info.get("phone", "Not Provided")
    email = client_info.get("email", "Not Provided")

    # Extract additional details from user input
    extracted_info = functions.extract_client_preferences(user_input)

    # Update lead with new details (directly in the database)
    lead_data = {
        "user_id": user_id,
        "name": name,
        "phone": phone,
        "email": email,
        "property_preferences": extracted_info.get("property_preferences", ""),
        "budget": extracted_info.get("budget", 0),
        "location": extracted_info.get("location", ""),
        "property_type": extracted_info.get("property_type", ""),
        "bedrooms": extracted_info.get("bedrooms", 0),
        "bathrooms": extracted_info.get("bathrooms", 0)
    }
    functions.create_lead(lead_data)

    # ✅ Log conversation in MySQL
    functions.log_conversation_to_db(thread_id, user_id, user_input)

    # Send user message to OpenAI assistant
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_input
    )

    # Process assistant response
    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
    core_functions.process_tool_calls(client, thread_id, run.id)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    response = messages.data[0].content[0].text.value

    # ✅ Log assistant response in MySQL
    functions.log_conversation_to_db(thread_id, user_id, response)

    return jsonify({"response": response})


def chatbot_response(user_input):
    """
    Processes user input, generates and executes the query, and returns a chatbot response.
    """
    query, error = generate_query(user_input)

    if error:
        return error

    results = fetch_data(query)

    if results:
        response = "🏡 **Available Properties:**\n"
        for row in results[:5]:  # Limit to 5 results
            name = row.get("name_en", "Unknown Property")
            price = row.get("price", "Price not listed")
            bedrooms = row.get("Bedrooms", "N/A")
            bathrooms = row.get("Bathrooms", "N/A")
            area = row.get("apartment_area", "N/A")

            response += f"\n🔹 **{name}**\n"
            response += f"📏 Area: {area} sqm\n"
            response += f"💰 Price: {price} EGP\n"
            response += f"🛏 Bedrooms: {bedrooms} | 🛁 Bathrooms: {bathrooms}\n"
            response += "-------------------------\n"

        return response

    return "❌ No matching properties found. Try refining your search."


if __name__ == '__main__':
    #print("🚀 Starting Flask API on http://0.0.0.0:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
