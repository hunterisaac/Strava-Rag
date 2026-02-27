import csv
import ollama
from datetime import datetime
import chromadb
import json
import pandas as pd 
client = chromadb.PersistentClient(path="./strava_vectordb")
collection = client.get_or_create_collection("strava-data")

i = 0
if collection.count() > 0:
    print("Database already exists. Skipping import.")
    pass 
else:
    with open("strava_data_copy.csv", newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            iso_string = str(row['start_date_local'])
            dt_obj = datetime.fromisoformat(iso_string)
            readable_date = dt_obj.strftime("%A, %B %d, %Y")
            heartrate = ''
            if row['average_heartrate'] and {row['max_heartrate']} != None:
                #heartrate = f"My average heartrate was {row['average_heartrate']} during the trip. My max heartrate was {row['max_heartrate']} during the trip. "
                heartrate = f"My average heartrate was {row['average_heartrate']} and my max heartrate was {row['max_heartrate']}."
            #narrative = f"The trip is {row['name']} The method of travel is {row['type']}. The distance covered in meters is {row['distance']}. The total time the activity took to complete was {row['moving_time']} seconds. The average speed of the trip is {row['average_speed']} m/s. The max speed of the trip was {row['max_speed']} m/s. {heartrate} This trip took place on {readable_date}"
            narrative = f"On {readable_date}, I went on a {row['name']}. The {row['type']} covered {row['distance']} meters in {row['moving_time']} seconds. My average speed was {row['average_speed']} m/s and my max speed was {row['max_speed']} m/s. {heartrate}"
            response = ollama.embeddings(model="nomic-embed-text", prompt=narrative)
            vector = response["embedding"]
            print(narrative)
            row['month'] = dt_obj.strftime("%B") 
            row['year'] = dt_obj.year             
            row['day_of_week'] = dt_obj.strftime("%A")
            if "Run" in narrative:
                row['type'] = "Run"
            if "Hike" in narrative:
                row['type'] = "Hike"
            if "Swim" in narrative:
                row['type'] = "Swim"
            if "Ride" in narrative:
                row['type'] = "Ride"
            if "Walk" in narrative:
                row['type'] = "Walk"
            if "Snowboard" in narrative:
                row['type'] = "Snowboard"
            if "Morning" in narrative:
                row['time_of_day'] = "Morning"
            if "Afternoon" in narrative:
                row['time_of_day'] = "Afternoon"
            if "Evening" in narrative:
                row['time_of_day'] = "Evening"
            print('metadata', row)


            collection.add(
                ids=[f"activity_{i}"], 
                embeddings=[vector],
                documents=[narrative],
                metadatas=[row] 
            )
            i += 1
def build_where(question):
    extract_prompt = f"""
    Extract fitness activity entities from the user's question.
    
    Rules:
    1. Return a JSON LIST of objects.
    2. Each object must contain ONLY ONE key-value pair.
    3. Use these keys: 'type' (ex: Run, Hike, Swim, Snowboard, Walk, Ride), 'month' (e.g., November), 'year' (e.g., 2023) 'time_of_day' (ex: Afternoon, Morning, or Evening).
    4. If an entity is not mentioned, do NOT include its key in the list.
    5. Return ONLY the JSON list. No preamble.
    6. If the key-value in the statement is None, don't include it AT ALL!.

    Question: {question}
    """
    response = ollama.generate(model="llama3", prompt=extract_prompt, format="json")
    value = json.loads(response['response'])
    formatted_list = []
    
    print(value)
    for key, val in value.items():
        if val is not None and val != "":
            formatted_list.append({key: val})
            
    print("where clause", formatted_list)
    return formatted_list
def build_tool(question):
    router_prompt = f"""
    You are a routing assistant for a fitness app. 
    Decide if the user's question requires the 'total' tool.

    VALID COLUMNS: start_date_local, type, distance, moving_time, total_elevation_gain, average_speed, max_speed, average_heartrate

    TOOL:
    1. total: Use if the user wants a sum of a column.
    Args: {{ "column": "string" }}

    Return ONLY JSON in this format:
    {{
    "tool_name": "total" or "none",
    "args": {{ "column": "column_name" }}
    }}

    Question: {question}
    """
    response = ollama.generate(model="llama3", prompt=router_prompt, format="json")
    value = json.loads(response['response'])
    tools = []
    print("tool-response:", value)
    if value.get("tool_name") == "total":
        column = value.get("args", {}).get("column")
        if column:
            df = pd.read_csv("strava_data.csv")
            if column in df.columns:
                total_value = int(df[column].sum())
                tools.append(f"The total sum of the {column} column: {total_value}")
            else:
                print(f"Error: Column {column} not found in CSV.")
    print(tools)
    return tools
def ask_strava(question):
    q_response = ollama.embeddings(model="nomic-embed-text", prompt=question)
    q_vector = q_response["embedding"]
    jsons = build_where(question)

    if len(jsons) == 1:
        where_clause = jsons[0]
    elif len(jsons) > 1:
        where_clause = {"$and": jsons}
    print(where_clause)
    results = collection.query(
        query_embeddings=[q_vector],
        n_results=9,
        where = where_clause
    )
    
    

    context = "\n".join(results['documents'][0])
    toolss = build_tool(question)
    prompt = f"""
    You are a personal fitness assistant. Use the following Strava activity data 
    to answer the user's question. If the data isn't there, say you don't know.
    
    Here is possibly relevant Context:
    {context}
    Here are the Tool results that an llm deemed vital to this question:
    {toolss}
    Question: {question}
    """
    print(prompt)

    final_answer = ollama.generate(model="llama3", prompt=prompt)
    return final_answer['response']



#print(ask_strava("how much total time running have i done overall"))
#print(ask_strava("Give me info about a few hikes."))
print(ask_strava("Tell me the date where I biked the farthest distance"))
#print(ask_strava("Tell me the longest activity."))

       
