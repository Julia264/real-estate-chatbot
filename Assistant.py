import os
import core_functions
import json
import config

def create_assistant(client):
    assistant_file_path = r'C:\Users\Dell\Desktop\last_versionnnnnnn\assistant.json'

    # If there is an assistant.json file, load the assistant
    if os.path.exists(assistant_file_path):
        with open(assistant_file_path, 'r') as file:
            assistant_data = json.load(file)
            assistant_id = assistant_data['assistant_id']
            print("Loaded existing assistant ID.")
    else:
        # Merge examples into the instructions
        instructions_with_examples = f"{config.assistant_instructions}\n\n### Examples:\n{config.examples}"

        # Create a new assistant
        assistant = client.beta.assistants.create(
            instructions=instructions_with_examples,
            model="gpt-4-turbo",
            tools=[
                {"type": "file_search"},
                config.schedule_viewing_tool,
                config.create_lead_tool,
                config.property_search_tool,
                config.search_new_launches_tool
            ]
        )

        # Print and save the assistant ID
        print(f"Assistant ID: {assistant.id}")
        with open(assistant_file_path, 'w') as file:
            json.dump({'assistant_id': assistant.id}, file)
            print("Created a new assistant and saved the ID.")

        assistant_id = assistant.id

    return assistant_id
