import sys
import os
import json
from datetime import datetime
import requests
from PyPDF2 import PdfReader
import trifalatura
import openai

MAX_CHARS_PER_PASS = 800  # Adjust as necessary based on typical use case and API constraints

PROMPT_TEXT = """
Based on the following text, generate {n_questions} educational flashcards. Each flashcard should include a question, an answer, and a category. The output must be formatted as a JSON list of objects.

Text snippet:
"{section}"

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
            return trifalatura.extract(response.text), 'html'
        elif 'pdf' in content_type:
            reader = PdfReader(response.content)
            text = ''.join([page.extract_text() for page in reader.pages if page.extract_text() is not None])
            return text, 'pdf'
        else:
            raise ValueError("Unsupported file type")
    except Exception as e:
        print(f"Error processing the document: {e}")
        sys.exit(1)

def generate_questions(text, n_questions, api_key):
    openai.api_key = api_key
    sections = [text[i:i+MAX_CHARS_PER_PASS] for i in range(0, len(text), MAX_CHARS_PER_PASS)]
    all_questions = []

    for index, section in enumerate(sections):
        print(f"Generating questions for section {index + 1}/{len(sections)}...")
        try:
            prompt_text = f"Generate {n_questions} detailed educational flashcards including question, answer, and category based on the following text: {section}"
            response = openai.Completion.create(
                engine="text-davinci-002",
                prompt=PROMPT_TEXT.format(),
                max_tokens=1500,
                n=n_questions
            )
            all_questions.extend(json.loads(response.choices[0].text))
        except Exception as e:
            print(f"Error generating questions for section {index + 1}: {e}")
            continue  # Continue with next section even if one fails

    return all_questions

def save_flashcards(flashcards, deckid, source_url, source_title):
    file_path = f"{deckid}.json"
    today_date = datetime.now().isoformat()
    print("Saving flashcards...")

    try:
        if os.path.exists(file_path):
            with open(file_path, 'r+') as file:
                existing_data = json.load(file)
                current_id_suffix = len(existing_data["cards"]) + 1
                for card in flashcards:
                    card['id'] = f"{deckid}-{current_id_suffix}"
                    card['deckid'] = deckid
                    card['sourceurl'] = source_url
                    card['sourcetitle'] = source_title
                    card['date'] = today_date
                    current_id_suffix += 1
                existing_data["cards"].extend(flashcards)
                file.seek(0)
                json.dump(existing_data, file, indent=4)
        else:
            for i, card in enumerate(flashcards, 1):
                card['id'] = f"{deckid}-{i}"
                card['deckid'] = deckid
                card['sourceurl'] = source_url
                card['sourcetitle'] = source_title
                card['date'] = today_date
            initial_data = {
                "title": source_title,
                "cards": flashcards
            }
            with open(file_path, 'w') as file:
                json.dump(initial_data, file, indent=4)
    except Exception as e:
        print(f"Error saving flashcards: {e}")
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
