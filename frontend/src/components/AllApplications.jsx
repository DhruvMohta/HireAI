import React, { useEffect, useState } from 'react';
import "../styles/applications.css";
import ApplicatioCard from './ApplicationCard';

export default function AllApplications () {
    const [applications, setApplications] = useState([]);

    useEffect(() => {
        fetch("http://127.0.0.1:5000/api/applications")
            .then((res) => res.json())
            .then((data) => setApplications(data))
            .catch((error) => console.error('Error fetching applications:', error));
    }, []);

    const deleteApplication = (id) => {
        fetch(`http://127.0.0.1:5000/api/applications/${id}`, {
            method: 'DELETE',
        })
        .then(response => {
            if (response.ok) {
                setApplications(applications.filter(app => app.id !== id));
            } else {
                console.error('Failed to delete the application');
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
    };

    return (
        <div className="applications-container">
            <h1>Your Applications</h1>
            {applications.length > 0 ? (
                <div className="applications-grid">
                    {applications.map((app) => (
                        <ApplicatioCard app={app} deleteApplication={() => deleteApplication(app.id)}/>
                ))}
            </div>
        ) : (
            <div className="no-applications">
                <p>You haven't submitted any applications yet.</p>
                <a href="/jobs" className="btn primary">Browse Jobs</a>
            </div>
        )}
    </div>
);}