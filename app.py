# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash
import google.generativeai as genai
from dotenv import load_dotenv
import pdfplumber
import docx
import markdown

# Load environment variables from .env file
load_dotenv()

# --- Flask App Configuration ---
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key')
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size

# --- Gemini API Configuration ---
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model_flash = genai.GenerativeModel('gemini-1.5-flash-latest')
model_pro = genai.GenerativeModel('gemini-1.5-pro-latest')

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx'}

def extract_text_from_file(file_path):
    text = ""
    if file_path.endswith('.pdf'):
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except Exception as e:
            return f"Error extracting text from PDF: {e}"
    elif file_path.endswith('.docx'):
        try:
            doc = docx.Document(file_path)
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            return f"Error extracting text from DOCX: {e}"
    return text

# --- LLM Prompts (Paste your prompts here) ---
# Paste your RESUME_ANALYZER_PROMPT here.
RESUME_ANALYZER_PROMPT = """
You are a senior business analyst and career coach. Your task is to analyze the following resume for a business analyst or data analyst role.

Based on the provided resume text below, perform the following three tasks and present the output in a clear, easy-to-read Markdown format. Use bold headings and bullet points.

1.  **Resume Score & Justification**
    - Give a score from 1 to 100 based on the resume's effectiveness.
    - Provide a brief, bulleted justification for this score.

2.  **Tips for Improvement**
    - Provide 3-5 concrete, actionable tips to improve the resume's clarity and impact.
    - Focus on areas like structure, grammar, professional tone, and missing sections.

3.  **Keyword and Quantifiable Impact Suggestions**
    - **Missing Keywords:** Identify 3-5 crucial industry keywords (e.g., SQL, Tableau, Power BI, Python, R, predictive modeling, A/B testing, ETL, dashboarding) that are missing or underutilized.
    - **Quantifiable Impact:** For each project or experience bullet point, suggest how to rephrase it to include quantifiable results or metrics. Provide specific, numbered examples for each section of the resume.

**Resume Text:**
{resume_text}

"""

# Paste your RESUME_BUILDER_PROMPT here.
RESUME_BUILDER_PROMPT = """
You are a professional YAML code agent specializing in generating a single, complete RenderCV configuration file for the 'sb2nov' theme.

Based on the provided user information, you must generate a well-structured YAML code block. The code should start with `cv:` and end correctly, with no extra conversational text or code fences (like ```yaml).

**YAML Code Generation Instructions:**
- **Professional Summary:** Generate a concise, 2-3 sentence professional summary based on the provided user details, focusing on business/data analyst skills. This should be the very first section in `cv.sections`.
- **Order of Sections:** The sections in the generated YAML must be in this exact order: `professional_summary`, `experience`, `education`, `projects`, `skills`, `interests`, `languages`.
- **Formatting:** Use 2-space indentation. Ensure all lists (`-`) and key-value pairs are formatted correctly.
- **Single Page Fit:** Include the provided `design` block with the reduced margins to ensure the CV fits on a single page.

**User Information to convert to YAML:**
Name: {name}
Email: {email}
Phone: {phone}
LinkedIn: {linkedin}
GitHub: {github}
Education: {education}
Experience: {experience}
Projects: {projects}
Skills: {skills}
Interests: {interests}
Languages: {languages}

**Output the complete YAML code block, and nothing else.**

cv:
  name: {name}
  location: Location
  email: {email}
  phone: {phone}
  social_networks:
    - network: LinkedIn
      username: {linkedin}
    - network: GitHub
      username: {github}
  sections:
    professional_summary:
      - '[Generate a 2-3 sentence professional summary based on the user data above. Start with "I am a..."]'
    experience:
      {experience}
    education:
      {education}
    projects:
      {projects}
    skills:
      {skills}
    interests:
      - bullet: {interests}
    languages:
      - bullet: {languages}
design:
  theme: sb2nov
  page:
    size: us-letter
    top_margin: 1cm
    bottom_margin: 1cm
    left_margin: 1cm
    right_margin: 1cm
    show_page_numbering: false
    show_last_updated_date: false
  header:
    name_font_size: 20pt
    vertical_space_between_name_and_connections: 0.4cm
    vertical_space_between_connections_and_first_section: 0.4cm
    alignment: center
  section_titles:
    font_size: 1.2em
    line_thickness: 0.5pt
    vertical_space_above: 0.3cm
    vertical_space_below: 0.2cm
  entries:
    vertical_space_between_entries: 0.6em
    short_second_row: true
  highlights:
    top_margin: 0.15cm
    left_margin: 0.4cm
    vertical_space_between_highlights: 0.2cm
    horizontal_space_between_bullet_and_highlight: 0.5em
  text:
    font_size: 9pt
    leading: 0.5em
    """

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/builder', methods=['GET', 'POST'])
def builder():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        linkedin = request.form.get('linkedin')
        github = request.form.get('github')
        education_text = request.form.get('education')
        experience_text = request.form.get('experience')
        projects_text = request.form.get('projects')
        skills_text = request.form.get('skills')
        interests_text = request.form.get('interests')
        languages_text = request.form.get('languages')
        
        prompt = RESUME_BUILDER_PROMPT.format(
            name=name, email=email, phone=phone, linkedin=linkedin, github=github,
            education=education_text, experience=experience_text, projects=projects_text, skills=skills_text,
            interests=interests_text, languages=languages_text
        )
        
        try:
            response = model_flash.generate_content(prompt)
            yaml_code = response.text
            return render_template('builder.html', yaml_code=yaml_code)
        except Exception as e:
            flash(f"Error generating resume: {e}", 'danger')
            return redirect(url_for('builder'))
            
    return render_template('builder.html')

@app.route('/analyzer', methods=['GET', 'POST'])
def analyzer():
    analysis_results = None
    if request.method == 'POST':
        if 'resume_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['resume_file']
        
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            
            resume_text = extract_text_from_file(filepath)
            
            os.remove(filepath)
            
            if "Error" in resume_text:
                flash(f"Error processing file: {resume_text}", 'danger')
                return redirect(url_for('analyzer'))

            prompt = RESUME_ANALYZER_PROMPT.format(resume_text=resume_text)

            try:
                response = model_pro.generate_content(prompt)
                analysis_results = markdown.markdown(response.text)
            except Exception as e:
                flash(f"Error analyzing resume: {e}", 'danger')
                return redirect(url_for('analyzer'))
        else:
            flash('Invalid file type. Please upload a PDF or DOCX.', 'danger')
            return redirect(request.url)
    
    return render_template('analyzer.html', results=analysis_results)

if __name__ == '__main__':
    app.run(debug=True)