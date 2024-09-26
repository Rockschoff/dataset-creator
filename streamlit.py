import streamlit as st
import pandas as pd
import requests
import urllib.parse
import json
import os
from bs4 import BeautifulSoup
from functions import get_fda_results, get_cfr_results,bot_response
from pymongo import MongoClient
from bson.objectid import ObjectId
import openai  # Import OpenAI library

# MongoDB connection setup
client = MongoClient(st.secrets["MONGODB_URI"])
db = client['finetuning']  # Database name
collection = db['v1']      # Collection name

# Initialize session state for data points
if "data_points" not in st.session_state:
    # Load data points from MongoDB
    data = list(collection.find())
    # Convert ObjectId to string for Streamlit compatibility
    for item in data:
        item['_id'] = str(item['_id'])
    st.session_state['data_points'] = data

# Function to generate bot response using OpenAI API
def generate_bot_response_from_llm(data_point):
    import openai
    import time

    # Get the API key and Assistant ID from Streamlit secrets
    OPENAI_APIKEY = st.secrets["OPENAI_APIKEY"]
    ASSISTANTID = st.secrets["ASSISTANTID"]

    if not OPENAI_APIKEY or not ASSISTANTID:
        st.error("OpenAI API key and Assistant ID must be set in Streamlit secrets.")
        return

    openai.api_key = OPENAI_APIKEY

    # Prepare the messages
    # Include the FDA and CFR search terms and results in the system prompt or context
   

    context = f"""FDA Search Terms: {data_point['fda_search_terms']}
FDA Search Results: {data_point['fda_search_results']}
CFR Search Terms: {data_point['cfr_search_terms']}
CFR Search Results: {data_point['cfr_search_results']}"""

    messages = [
        
        {"role": "user", "content": context+ data_point['question']}
    ]

    try:
        # Make the API call to get the assistant's response
        response = bot_response(openai , messages , ASSISTANTID , "gpt-4o")

        assistant_message = response
        data_point['llm_response'] = assistant_message

        # Update the response in MongoDB
        collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'llm_response': assistant_message}})

    except Exception as e:
        st.error(f"Error generating response: {e}")
        data_point['llm_response'] = ""

# Function to add a new data point
def add_data_point():
    new_data_point = {
        'question': '',
        'cfr_search_terms': '',
        'fda_search_terms': '',
        'cfr_search_results': '',
        'fda_search_results': '',
        'llm_response': ''
    }
    # Insert into MongoDB and get the inserted ID
    result = collection.insert_one(new_data_point)
    new_data_point['_id'] = str(result.inserted_id)
    st.session_state['data_points'].append(new_data_point)

# Button to add a new data point
st.title("Finetuning Dataset Creator")
if st.button("Add New Data Point"):
    add_data_point()

# For each data point, create an expander to edit it
for idx, data_point in enumerate(st.session_state['data_points']):
    with st.expander(f"Data Point {idx+1}", expanded=False):
        # Editable fields
        question = st.text_input("Question", value=data_point.get('question', ''), key=f'question_{data_point["_id"]}')
        cfr_search_terms = st.text_input("CFR SEARCH TERMS (comma separated)", value=data_point.get('cfr_search_terms', ''), key=f'cfr_search_terms_{data_point["_id"]}')
        fda_search_terms = st.text_input("FDA SEARCH TERMS (comma separated)", value=data_point.get('fda_search_terms', ''), key=f'fda_search_terms_{data_point["_id"]}')
        
        # Update the data point in MongoDB when fields change
        if question != data_point.get('question', ''):
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'question': question}})
            data_point['question'] = question
        if cfr_search_terms != data_point.get('cfr_search_terms', ''):
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'cfr_search_terms': cfr_search_terms}})
            data_point['cfr_search_terms'] = cfr_search_terms
            # Automatically populate CFR search results
            cfr_search_results = get_cfr_results(cfr_search_terms)
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'cfr_search_results': cfr_search_results}})
            data_point['cfr_search_results'] = cfr_search_results
        else:
            cfr_search_results = data_point.get('cfr_search_results', '')

        if fda_search_terms != data_point.get('fda_search_terms', ''):
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'fda_search_terms': fda_search_terms}})
            data_point['fda_search_terms'] = fda_search_terms
            # Automatically populate FDA search results
            fda_search_results = get_fda_results(fda_search_terms)
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'fda_search_results': fda_search_results}})
            data_point['fda_search_results'] = fda_search_results
        else:
            fda_search_results = data_point.get('fda_search_results', '')
        
        # Display CFR Search Results
        if cfr_search_results:
            st.write("CFR Search Results:")
            st.write(cfr_search_results[:500])

        # Display FDA Search Results
        if fda_search_results:
            st.write("FDA Search Results:")
            st.write(fda_search_results[:500])

        # Generate bot response
        if st.button("Generate Bot Response from LLM", key=f'generate_bot_response_{data_point["_id"]}'):
            generate_bot_response_from_llm(data_point)
            # The response is already updated in the function

        st.write("BOT RESPONSE:")
        llm_response = st.text_area("", value=data_point.get('llm_response', ''), key=f'llm_response_{data_point["_id"]}')
        if llm_response != data_point.get('llm_response', ''):
            collection.update_one({'_id': ObjectId(data_point['_id'])}, {'$set': {'llm_response': llm_response}})
            data_point['llm_response'] = llm_response
        
        # Delete data point
        if st.button("Delete Data Point", key=f'delete_{data_point["_id"]}'):
            collection.delete_one({'_id': ObjectId(data_point['_id'])})
            st.session_state['data_points'].pop(idx)
            st.experimental_rerun()

# Display the dataset
st.header("Dataset Preview")
if st.button("Show Dataset"):
    df = pd.DataFrame(st.session_state['data_points'])
    st.write(df)

# Export the dataset as CSV
if st.button("Export Dataset as CSV"):
    df = pd.DataFrame(st.session_state['data_points'])
    # Exclude the '_id' field from CSV
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])
    csv = df.to_csv(index=False)
    st.download_button(label="Download CSV", data=csv, file_name='dataset.csv', mime='text/csv')
