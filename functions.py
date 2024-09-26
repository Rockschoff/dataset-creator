import streamlit as st
import json
import requests
import urllib
from bs4 import BeautifulSoup
import time

def get_cfr_results(search_terms):
    encoded_search_terms = urllib.parse.quote(search_terms)
    url = f"https://www.ecfr.gov/api/search/v1/results?query={encoded_search_terms}&per_page=25&page=1&order=relevance&paginate_by=results"
    headers = {
        'Accept': 'application/json'
    }
    st.write("Searching CFR:", search_terms)
    try:
        response = requests.get(url, headers=headers)
        if not response.ok:
            raise Exception(f"HTTP error! status: {response.status_code}")
        data = response.json()
        hierarchy_text = []
        for ele in data.get('results', []):
            full_text_excerpt = ele.get('full_text_excerpt', '')
            hierarchy_headings = ele.get('hierarchy_headings', [])
            hierarchy_headings_json = json.dumps(hierarchy_headings)
            text = full_text_excerpt + hierarchy_headings_json
            hierarchy_text.append(text)
        return "\n".join(hierarchy_text)
    except Exception as e:
        st.error(f'There was an error with the fetch operation: {e}')
        return "Error Getting response from CFR"

def fetch_site_content(url):
    fda_domains = ['https://www.fda.gov', 'https://fda.gov']
    is_fda_domain = any(url.startswith(domain) for domain in fda_domains)

    if not is_fda_domain:
        return "Site content not available"

    st.write(f"Fetching site content from {url}")
    try:
        response = requests.get(url)
        if not response.ok:
            raise Exception(f"Failed to fetch content from {url}")
        html = response.text

        # Parse the HTML to extract <p> tags
        soup = BeautifulSoup(html, 'html.parser')
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
        # Join the non-empty paragraphs with a newline
        return '\n'.join(paragraphs)
    except Exception as e:
        st.error(f'Error fetching site content: {e}')
        return 'Failed to retrieve content'

def get_fda_results(search_terms):
    # Replace these with your actual API key and Search Engine ID
    apiKey = st.secrets['GOOGLE_SEARCH_KEY']
    cx = st.secrets['GOOGLE_SEARCH_ENGINE_ID']

    if not apiKey or not cx:
        st.error('Google API key and Search Engine ID must be set in environment variables.')
        return 'API credentials not provided.'

    num_results = 5
    encoded_query = urllib.parse.quote(search_terms)
    url = f"https://www.googleapis.com/customsearch/v1?key={apiKey}&cx={cx}&q={encoded_query}&num={num_results}"

    st.write("Searching FDA website:", search_terms)
    try:
        response = requests.get(url)
        if not response.ok:
            raise Exception(f"Error: {response.status_code} - {response.text}")
        data = response.json()
        ans = []

        if 'items' in data:
            for item in data['items']:
                title = item.get('title', '')
                link = item.get('link', '')
                snippet = item.get('snippet', '')

                site_content = fetch_site_content(link)
                ans.append({
                    'title': title,
                    'link': link,
                    'snippet': snippet,
                    'site_content': site_content,
                })
            # Limit the total length of the results
            MAX_LENGTH = 110000
            total_length = len(json.dumps(ans))
            while total_length > MAX_LENGTH:
                st.write(f"Trimming results. Current length: {total_length}")
                # Find the index with the longest site_content
                max_index = max(range(len(ans)), key=lambda i: len(ans[i]['site_content']))
                excess = total_length - MAX_LENGTH
                content_length = len(ans[max_index]['site_content'])
                if content_length <= excess:
                    ans[max_index]['site_content'] = ''
                else:
                    ans[max_index]['site_content'] = ans[max_index]['site_content'][:content_length - excess]
                total_length = len(json.dumps(ans))
            return json.dumps(ans)
        else:
            st.write('No results found.')
            return '[]'
    except Exception as e:
        st.error(f'Error fetching data: {e}')
        return '[]'

def bot_response(client, messages, ASSISTANTID , MODEL)->str:

    # self.system_message= self.system_message+ f"{st.session_state.app.generate_app_state()}" + """ Please make good use of this infomration to answer the user queries"""
    run = client.beta.threads.create_and_run(
        assistant_id=ASSISTANTID,
        model = MODEL,
        thread =  {
            "messages": messages
            },
        # instructions=system_message,
        
    )
    def wait_on_run(run):
        
        while run.status == "queued" or run.status == "in_progress":
            print("Waiting")
            run = client.beta.threads.runs.retrieve(
                thread_id=run.thread_id,
                run_id=run.id,
            )
            time.sleep(0.5)
        return run
    run = wait_on_run(run)
    messages = client.beta.threads.messages.list(thread_id=run.thread_id)
    # print(messages.data[0])
    ans = messages.data[0].content[0].text.value 
    return ans
