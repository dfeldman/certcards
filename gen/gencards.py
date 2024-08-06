import sys
import os
import json
from datetime import datetime
import requests
from PyPDF2 import PdfReader
import trafilatura
from openai import OpenAI
import traceback

MAX_CHARS_PER_PASS = 10000  # Adjust as necessary based on typical use case and API constraints

PROMPT_TEXT = """
Based on the following text, generate {n_questions} educational flashcards. Each flashcard should include a question, an answer, and a category. The output must be formatted as a JSON list of objects.

Text snippet:
"{text}"

The array of results should look like this:
[{{
    "question": "What is the main theme discussed in the text?",
    "answer": "The main theme is the impact of technology on society.",
    "category": "Technology"
}},
...
]

DO NOT INCLUDE ANY OTHER TEXT. ONLY OUTPUT JSON. 

Ensure that the questions vary in difficulty and cover different aspects of the text. The categories should be broad enough to encompass similar questions but specific enough to provide meaningful classification.
"""

def download_document(url):
    print("Downloading document...")
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error downloading the document: {e}")
        sys.exit(1)
    
    content_type = response.headers.get('Content-Type', '')
    
    try:
        if 'html' in content_type:
            return trafilatura.extract(response.text), 'html'
        elif 'pdf' in content_type:
            reader = PdfReader(response.content)
            text = ''.join([page.extract_text() for page in reader.pages if page.extract_text() is not None])
            return text, 'pdf'
        else:
            raise ValueError("Unsupported file type")
    except Exception as e:
        print(f"Error processing the document: {e}")
        traceback.print_exc()
        sys.exit(1)

def generate_questions(text, n_questions, api_key):
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    #openai.api_key = api_key
    sections = [text[i:i+MAX_CHARS_PER_PASS] for i in range(0, len(text), MAX_CHARS_PER_PASS)]
    all_questions = []
    prompt_text = PROMPT_TEXT.format(n_questions=n_questions, text=text, api_key=api_key)

    for index, section in enumerate(sections):
        print(f"Generating questions for section {index + 1}/{len(sections)}...")
        try:
            #prompt_text = f"Generate {n_questions} detailed educational flashcards including question, answer, and category based on the following text: {section}"
            prompt_text = PROMPT_TEXT.format(n_questions=n_questions, text=text, api_key=api_key)
            print(prompt_text)
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a creative assistant."},
                    {"role": "user", "content": prompt_text}
                ]
            )
            
            if not (response and response.choices and len(response.choices) > 0):
                raise Exception("Failed to generate conversation.")
            print(response.choices[0].message.content)
            all_questions.extend(json.loads(response.choices[0].message.content))
        except Exception as e:
            print(f"Error generating questions for section {index + 1}: {e}")
            traceback.print_exc()
            continue  # Continue with next section even if one fails

    # Todo validate output
    return all_questions

def save_flashcards(flashcards, deckid, source_url, source_title):
    file_path = f"{deckid}.json"
    today_date = datetime.now().isoformat()
    print("Saving flashcards...", flashcards)

    try:
        if os.path.exists(file_path):
            with open(file_path, 'r+') as file:
                existing_data = json.load(file)
                current_id_suffix = len(existing_data["cards"]) + 1
                for card in flashcards:
                    print("X")
                    print(card)
                    print("Y")
                    card['id'] = f"{deckid}-{current_id_suffix}"
                    card['deckid'] = deckid
                    card['sourceUrl'] = source_url
                    card['sourceTitle'] = source_title
                    card['date'] = today_date
                    current_id_suffix += 1
                existing_data["cards"].extend(flashcards)
                file.seek(0)
                json.dump(existing_data, file, indent=4)
        else:
            for i, card in enumerate(flashcards, 1):
                print(i, card)
                card['id'] = f"{deckid}-{i}"
                card['deckid'] = deckid
                card['sourceUrl'] = source_url
                card['sourceTitle'] = source_title
                card['date'] = today_date
            initial_data = {
                "title": source_title,
                "cards": flashcards
            }
            with open(file_path, 'w') as file:
                json.dump(initial_data, file, indent=4)
    except Exception as e:
        print(f"Error saving flashcards: {e}")
        traceback.print_exc()
        sys.exit(1)

def main(deckid, url, title, n_questions):
    text, doc_type = download_document(url)
    flashcards = generate_questions(text, n_questions, os.getenv('OPENAI_API_KEY'))
    save_flashcards(flashcards, deckid, url, title)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python3 gencards.py <deckid> <url> <title> <n_questions>")
        sys.exit(1)
    try:
        deckid, url, title, n_questions = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    except ValueError:
        print("Error: n_questions must be an integer.")
        sys.exit(1)
    main(deckid, url, title, n_questions)
    print("Operation completed successfully.")
