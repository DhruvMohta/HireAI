import os
import re
import json
from PyPDF2 import PdfReader
import google.generativeai as genai

# Load Gemini API Key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def extract_entities_with_gemini(pdf_path):
    """
    Extracts entities from a PDF CV using the Gemini API.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        dict: Extracted CV details or None if an error occurs.
    """

    try:
        # Extract text from PDF
        reader = PdfReader(pdf_path)
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

        # Prepare the prompt for Gemini
        prompt = f"""
        Extract the following information from the CV below:

        CV Text:
        {text}

        Information to extract:
        - Name
        - Email address
        - Phone number
        - Education (list each degree with institution and dates)
        - Work Experience (list each role with company and dates)
        - Skills (list technical and soft skills)

        Return the information in JSON format.
        """

        # Call Gemini API
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)

        # Process response
        extracted_data = json.loads(response.text.strip().removeprefix("```json").removesuffix("```").strip())
        return extracted_data

    except json.JSONDecodeError:
        print("Error decoding JSON:", response.text)
        return None

    except Exception as e:
        print("An error occurred:", e)
        return None


def get_highest_education(extracted_info):
    """
    Extracts the highest education level as a string (e.g., "PhD", "Master", "Bachelor").

    Args:
        extracted_info (dict): Extracted CV details.

    Returns:
        str: The highest education level title or "Unknown" if not found.
    """

    if not extracted_info or "Education" not in extracted_info:
        return "Unknown"

    # Mapping education levels from lowest to highest
    education_levels = {
        "diploma": 0,
        "bachelor": 1,
        "master": 2,
        "phd": 3
    }
    
    highest_education = "Unknown"
    highest_rank = -1

    # Ensure education entries exist and are a list
    education_entries = extracted_info["Education"]
    if isinstance(education_entries, list):
        for entry in education_entries:
            if isinstance(entry, dict) and "Degree" in entry:
                degree = entry["Degree"].lower()
                for key, rank in education_levels.items():
                    if key in degree and rank > highest_rank:
                        highest_rank = rank
                        highest_education = key.capitalize()  # Keep title format (e.g., "PhD")

    return highest_education


def assign_candidate_score(pdf_path, job_details):
    try:
        """
        Assigns a score (out of 50) to the candidate based on extracted CV details and job requirements.

        Args:
            extracted_info (dict): Extracted CV details.
            job_details (dict): Dictionary containing job requirements (education, experience, skills).

        Returns:
            int: Total candidate score out of 50, or 0 if they don’t meet the education requirement.
        """

        extracted_info = extract_entities_with_gemini(pdf_path)

        if not extracted_info:
            return 0  # If extraction failed, return 0

        # Extract job requirements
        required_education = job_details.get("education", "").lower()
        required_experience = job_details.get("experience", 0)
        required_skills = set(map(str.lower, job_details.get("skills", [])))

        # 1. Get highest education level
        # highest_education = get_highest_education(extracted_info)

        highest_education = get_highest_education(extracted_info)

        # 2. Check if education is related
        # if not is_related_degree(highest_education):
        #     return 0

        # Map education levels for comparison
        education_levels = {"Diploma": 0, "Bachelor": 1, "Master": 2, "PhD": 3}
        min_required_rank = education_levels.get(required_education.capitalize(), 0)
        candidate_rank = education_levels.get(highest_education, -1)

        # 2. Education Requirement Check (Eliminator)
        # if candidate_rank < min_required_rank:
        #     return 0  # Candidate is automatically disqualified

        # 3. Higher Education Bonus (Max 5 points)
        score = 0
        if candidate_rank > min_required_rank:
            if candidate_rank == 3 and min_required_rank == 2:  # PhD when Master's is required
                score += 5
            elif candidate_rank == 2 and min_required_rank == 1:  # Master's when Bachelor's is required
                score += 3

        # 4. Work Experience (Max 25 points)
        experience = extracted_info.get("Work Experience", [])
        years_of_experience = 0

        for job in experience:
            match = re.search(r"(\d+)\s*years?", job, re.IGNORECASE)
            if match:
                years_of_experience = max(years_of_experience, int(match.group(1)))

        if years_of_experience >= 5:
            score += 25
        elif 3 <= years_of_experience < 5:
            score += 20
        elif 1 <= years_of_experience < 3:
            score += 12
        elif years_of_experience < 1:
            score += 5

        # 5. Skills Matching (Max 12.5 points)
        candidate_skills = set(map(str.lower, extracted_info.get("Skills", [])))
        matching_skills = required_skills.intersection(candidate_skills)
        skill_score = min(len(matching_skills) * 2.5, 12.5)  # 2.5 points per matching skill
        score += skill_score

        # 6. Contact Details (Max 7.5 points)
        email = extracted_info.get("Email address")
        phone = extracted_info.get("Phone number")
        if email and phone:
            print("Email and phone found")
            score += 7.5
        elif email or phone:
            print("Email or phone found")
            score += 5

        print('score:', score)
        return round(score, 2)  # Round to 2 decimal places
    except Exception as e:
        print(f"An error occurred: {e}")
        return 0


def is_related_degree(degree):
    """
    Determines if a degree is related to Computer Science.

    Args:
        degree (str): Extracted degree name.

    Returns:
        bool: True if the degree is related, False otherwise.
    """
    related_fields = [
        "computer science", "software engineering", "information technology",
        "electrical engineering", "electronics", "data science", "cybersecurity"
    ]
    degree_lower = degree.lower()
    
    return any(field in degree_lower for field in related_fields)

if __name__ == "__main__":
    # --- Example Job Posting ---
    job_posting = {
        "title": "Bomboclaat Engineer",
        "location": "Leuven, BE",
        "job_type": "Full-time",
        "education": "bachelor",
        "experience": 3,  # 3+ years required
        "skills": ["Patience", "Sleep deprivation", "Software Development"]
    }

    # --- Example CV Processing ---
    pdf_file_path = "Kiran Dinesh CV.pdf"  # Replace with actual CV file path

    extracted_info = extract_entities_with_gemini(pdf_file_path)

    if extracted_info:
        candidate_score = assign_candidate_score(extracted_info, job_posting)
        print(f"Candidate Score for {job_posting['title']}: {candidate_score}/50")
        print(f"Highest Education: {get_highest_education(extracted_info)}")
    else:
        print("Could not extract information.")