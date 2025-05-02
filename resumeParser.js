require('dotenv').config();
const fs = require('fs');
const pdf = require('pdf-parse');
const axios = require('axios');

// Predefined list of common skills (expanded)
const commonSkills = [
  'JavaScript', 'Python', 'Java', 'C++', 'C#', 'SQL', 'React', 'Node.js', 'Angular', 'Vue.js',
  'Django', 'Flask', 'Ruby', 'PHP', 'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Terraform',
  'Machine Learning', 'Deep Learning', 'Data Analysis', 'Data Science', 'Project Management',
  'UI/UX Design', 'Agile', 'Scrum', 'DevOps', 'Cybersecurity', 'Blockchain', 'TypeScript'
];

// Regex patterns for validation
const emailRegex = /[\w.%+-]+@[\w.-]+\.[a-zA-Z]{2,}/i;
const labeledEmailRegex = /(?:email|e-mail|contact)\s*[:\s]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i;
const phoneRegex = /(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/;
const linkedinRegex = /(https?:\/\/)?([w]{0,3}\.)?linkedin\.com\/(in|profile)\/[\w-]+\/?/i;

// xAI API configuration
const XAI_API_URL = 'https://api.x.ai/v1/grok';
const XAI_API_KEY = process.env.XAI_API_KEY;

// Function to validate file existence
function validateFilePath(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
  if (!filePath.toLowerCase().endsWith('.pdf')) {
    throw new Error('File must be a PDF');
  }
}

// Function to call xAI Grok 3 API
async function queryGrok(text) {
  try {
    const prompt = `
      You are an expert resume parser. Extract the following from the resume text:
      1. Skills (technical and soft skills, prioritize from: ${commonSkills.join(', ')}).
      2. Contact info (email, phone, LinkedIn URL).
      3. Current employment (most recent job title and company, look for keywords like 'present', 'current', or date ranges like '2023 - Present').

      Return the response in JSON format:
      {
        "skills": [],
        "contact": {
          "email": "",
          "phone": "",
          "linkedin": ""
        },
        "currentEmployment": ""
      }

      Resume text:
      ${text}
    `;

    const response = await axios.post(
      XAI_API_URL,
      {
        model: 'grok-3',
        prompt: prompt,
        max_tokens: 1000,
        temperature: 0.7
      },
      {
        headers: {
          'Authorization': `Bearer ${XAI_API_KEY}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return JSON.parse(response.data.choices[0].text);
  } catch (error) {
    console.error('Error querying Grok API:', error.message);
    throw error;
  }
}

// Function to extract and validate data from resume
async function extractResumeData(pdfPath) {
  try {
    validateFilePath(pdfPath);
    console.log(`Extracting data from: ${pdfPath}`);

    // Read PDF file
    const dataBuffer = fs.readFileSync(pdfPath);
    const pdfData = await pdf(dataBuffer);
    const text = pdfData.text;

    // Debug: Save raw text to file
    fs.writeFileSync('raw_text.txt', text);
    console.log('Raw text snippet (first 500 chars):', text.substring(0, 500));

    // Query Grok API for structured data
    const grokData = await queryGrok(text);

    // Fallback regex validation for contact info
    const emailMatch = text.match(emailRegex) || text.match(labeledEmailRegex);
    const phoneMatch = text.match(phoneRegex);
    const linkedinMatch = text.match(linkedinRegex);

    // Merge Grok data with regex validation
    const resumeData = {
      skills: grokData.skills.length > 0 ? grokData.skills : ['None identified'],
      contact: {
        email: grokData.contact.email || (emailMatch ? (emailMatch[1] || emailMatch[0]) : 'Not found'),
        phone: grokData.contact.phone || (phoneMatch ? phoneMatch[0] : 'Not found'),
        linkedin: grokData.contact.linkedin || (linkedinMatch ? linkedinMatch[0] : 'Not found')
      },
      currentEmployment: grokData.currentEmployment || 'Not found',
      extractedAt: new Date()
    };

    return resumeData;
  } catch (error) {
    console.error('Error extracting resume data:', error.message);
    throw error;
  }
}

// Main function to process resume
async function processResume(pdfPath) {
  try {
    console.log(`Processing resume: ${pdfPath}`);
    const resumeData = await extractResumeData(pdfPath);
    console.log('Extracted Data:', JSON.stringify(resumeData, null, 2));

    // Save extracted data to file
    fs.writeFileSync('resume_data.json', JSON.stringify(resumeData, null, 2));
    console.log('Extracted data saved to resume_data.json');
    return resumeData;
  } catch (error) {
    console.error('Error processing resume:', error.message);
    throw error;
  }
}

// Run the script with command-line argument or default path
const pdfPath = process.argv[2] || './Resume.pdf';
processResume(pdfPath)
  .catch(err => console.error('Failed to process resume:', err.message));