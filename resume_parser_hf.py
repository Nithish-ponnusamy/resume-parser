import PyPDF2
import re
import json
from datetime import datetime
from transformers import pipeline
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb+srv://Sujith:SujithAdmin@cluster0.phnidou.mongodb.net/AlumniConnect?retryWrites=true&w=majority")
DB_NAME = "AlumniConnect"
COLLECTION_NAME = "resume_data"

# Predefined list of common skills
common_skills = [
    'JavaScript', 'Python', 'Java', 'C++', 'C#', 'SQL', 'React', 'Node.js', 'Angular', 'Vue.js',
    'Django', 'Flask', 'Ruby', 'PHP', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Terraform',
    'Machine Learning', 'Deep Learning', 'Data Analysis', 'Data Science', 'Project Management',
    'UI/UX Design', 'Agile', 'Scrum', 'DevOps', 'Cybersecurity', 'Blockchain', 'TypeScript',
    'HTML', 'CSS', 'Git', 'Linux', 'Networking', 'Database Management', 'Cloud Computing'
]

# Regex patterns for contact info validation
email_regex = r'[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}'
labeled_email_regex = r'(?:email|e-mail|contact)\s*[:\s]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
phone_regex = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
linkedin_regex = r'(https?://)?([w]{0,3}\.)?linkedin\.com/(in|profile)/[\w-]+/?'

# Initialize Hugging Face NER pipeline
ner_pipeline = pipeline("ner", model="dslim/bert-base-NER", grouped_entities=True)

def validate_file_path(file_path):
    """Validate that the file exists and is a PDF."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not file_path.lower().endswith('.pdf'):
        raise ValueError("File must be a PDF")

def extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file using PyPDF2."""
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error reading PDF: {e}")
        raise

def extract_entities_with_huggingface(text):
    """Extract entities (skills, contact, employment) using Hugging Face NER and heuristics."""
    try:
        # Run NER on the text
        ner_results = ner_pipeline(text)
        
        # Initialize extracted data
        entities = {
            "skills": [],
            "contact": {"email": "Not found", "phone": "Not found", "linkedin": "Not found"},
            "currentEmployment": "Not found",
            "entities_detected": {"persons": [], "organizations": [], "locations": []}
        }

        # Extract persons, organizations, and locations from NER results
        for entity in ner_results:
            if entity['entity_group'] == 'PER':
                entities["entities_detected"]["persons"].append(entity['word'])
            elif entity['entity_group'] == 'ORG':
                entities["entities_detected"]["organizations"].append(entity['word'])
            elif entity['entity_group'] == 'LOC':
                entities["entities_detected"]["locations"].append(entity['word'])

        # Extract skills by matching common_skills (case-insensitive)
        text_lower = text.lower()
        entities["skills"] = [skill for skill in common_skills if skill.lower() in text_lower]
        if not entities["skills"]:
            entities["skills"] = ["None identified"]

        # Extract current employment using heuristic
        lines = text.split('\n')
        work_section_keywords = ['experience', 'employment', 'work history', 'professional experience']
        present_keywords = ['present', 'current', 'now', 'ongoing']
        in_work_section = False

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in work_section_keywords):
                in_work_section = True
            if in_work_section:
                if (any(keyword in line_lower for keyword in present_keywords) or
                    re.search(r'\b(20\d{2})\s*[-–—]\s*(present|current|now|ongoing)\b', line_lower, re.I)):
                    entities["currentEmployment"] = lines[i - 1].strip() or lines[i].strip() or "Current role found"
                    break

        return entities
    except Exception as e:
        print(f"Error processing text with Hugging Face: {e}")
        raise

def save_to_mongodb(data):
    """Save resume data to MongoDB."""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Insert data
        result = collection.insert_one(data)
        print(f"Data inserted into MongoDB with ID: {result.inserted_id}")
        
        # Close connection
        client.close()
        return result.inserted_id
    except ConnectionFailure as e:
        print(f"Failed to connect to MongoDB: {e}")
        raise
    except OperationFailure as e:
        print(f"MongoDB operation failed: {e}")
        raise
    except Exception as e:
        print(f"Error saving to MongoDB: {e}")
        raise

def extract_resume_data(pdf_path):
    """Extract resume data combining Hugging Face NER and regex validation."""
    try:
        validate_file_path(pdf_path)
        print(f"Extracting data from: {pdf_path}")

        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)

        # Debug: Save raw text to file
        with open('raw_text.txt', 'w', encoding='utf-8') as f:
            f.write(text)
        print('Raw text snippet (first 500 chars):', text[:500])

        # Extract entities using Hugging Face
        resume_data = extract_entities_with_huggingface(text)

        # Regex validation for contact info
        email_match = re.search(email_regex, text, re.I) or re.search(labeled_email_regex, text, re.I)
        phone_match = re.search(phone_regex, text)
        linkedin_match = re.search(linkedin_regex, text, re.I)

        # Update contact info with regex results
        resume_data["contact"].update({
            "email": email_match.group(1) if email_match and email_match.group(1) else email_match.group(0) if email_match else "Not found",
            "phone": phone_match.group(0) if phone_match else "Not found",
            "linkedin": linkedin_match.group(0) if linkedin_match else "Not found"
        })

        # Add extraction timestamp
        resume_data["extractedAt"] = datetime.now().isoformat()

        return resume_data
    except Exception as e:
        print(f"Error extracting resume data: {e}")
        raise

def process_resume(pdf_path):
    """Main function to process the resume, save JSON, and store in MongoDB."""
    try:
        print(f"Processing resume: {pdf_path}")
        resume_data = extract_resume_data(pdf_path)
        print('Extracted Data:', json.dumps(resume_data, indent=2))

        # Save extracted data to JSON file
        with open('resume_data.json', 'w', encoding='utf-8') as f:
            json.dump(resume_data, f, indent=2)
        print('Extracted data saved to resume_data.json')

        # Save to MongoDB
        inserted_id = save_to_mongodb(resume_data)
        print(f"Resume data stored in MongoDB with ID: {inserted_id}")

        return resume_data
    except Exception as e:
        print(f"Error processing resume: {e}")
        raise

if __name__ == "__main__":
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "./Resume.pdf"
    process_resume(pdf_path)