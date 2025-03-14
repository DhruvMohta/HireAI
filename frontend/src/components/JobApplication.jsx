import React, { useState, useEffect } from 'react';
// import type { JobOffer } from '../lib/types';
import "../styles/jobApplication.css";
import { API_URL } from '../lib/constants';

const JobApplication = ( { id } ) => {
    const [jobOffer, setJobOffer] = useState(null);
    const [fileName, setFileName] = useState('No file chosen');


    useEffect(() => {
        const fetchJobOffer = async () => {
            try {
                const response = await fetch(`${API_URL}/api/jobs/${id}`);
                const data = await response.json();
                setJobOffer(data);
            } catch (error) {
                console.error('Error fetching job offer:', error);
            }
        };

        fetchJobOffer();
    }, [id]);

    const handleFileChange = (event) => {
        const file = event.target.files[0];
        setFileName(file ? file.name : 'No file chosen');
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);

        try {
            const response = await fetch(`${API_URL}/apply/${id}`, {
                method: 'POST',
                body: formData,
            });

            if (response.ok) {
                alert('Application sent successfully!');
            } else {
                alert('Failed to send application.');
            }
        } catch (error) {
            console.error('Error submitting form:', error);
            alert('An error occurred while sending the application.');
        }
    };

    if (!jobOffer) {
        return <div>Loading...</div>;
    }

    const { title, location } = jobOffer;

    return (
        <div className="job-application-container">
            <h1>Job Application as {title} in {location}</h1>
            <form className="application-form" id="applicationForm" onSubmit={handleSubmit} encType="multipart/form-data">
                <section className="form-section">
                    <h2>Personal Information</h2>
                    <div className="form-grid">
                        <div className="form-group">
                            <label htmlFor="firstName">First Name</label>
                            <input type="text" id="firstName" name="firstName" required />
                        </div>
                        <div className="form-group">
                            <label htmlFor="lastName">Last Name</label>
                            <input type="text" id="lastName" name="lastName" required />
                        </div>
                    </div>
                    <div className="form-group">
                        <label htmlFor="email">Email Address</label>
                        <input type="email" id="email" name="email" required />
                    </div>
                    <div className="form-group">
                        <label htmlFor="phone">Phone Number</label>
                        <input type="tel" id="phone" name="phone" required />
                    </div>
                </section>

                <section className="form-section">
                    <h2>Documents</h2>
                    <div className="form-group">
                        <label htmlFor="resume" className="file-label">
                            <div className="file-input-container">
                                <span className="file-button">Choose File</span>
                                <span className="file-name">{fileName}</span>
                            </div>
                            <input type="file" id="resume" name="resume" accept=".pdf,.doc,.docx" onChange={handleFileChange} />
                        </label>
                        <span className="file-help-text">Upload your resume (PDF, DOC, DOCX)</span>
                    </div>
                </section>

                <div className="form-actions">
                    <button type="submit" className="submit-button">Submit Application</button>
                </div>
            </form>
        </div>
    );
};

export default JobApplication;
