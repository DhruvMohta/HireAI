
export type JobOffer = {
    date_posted: string;
    deadline: string;
    description: string;
    experience_level: string;
    id: number;
    job_type: string;
    location: string;
    requirements: string[];
    salary: string;
    title: string;
};

export type Application = {
    id: string;
    applicant_id: string;
    first_name: string;
    last_name: string;
    email: string;
    phone_number: string;
    job_id: string;
    cv_path: string;
    status: string;
    score: number;
    date_applied: string;
    job_title: string;
    job_location: string;
    job_type: string;
    experience_level: string;
}