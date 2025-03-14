import React from "react";

export default function ApplicationCard({ app, deleteApplication }) {
    return (
        <div className="application-card" key={app.id}>
                <div className="card-header">
                    <h2>{app.job_title}</h2>
                    <span className={`status-badge status-${app.status.toLowerCase()}`}>
                        {app.status}
                    </span>
                </div>
                <div className="card-body">
                    <div className="detail-row">
                        <span className="label">Location:</span>
                        <span>{app.job_location}</span>
                    </div>
                    <div className="detail-row">
                        <span className="label">Type:</span>
                        <span>{app.job_type}</span>
                    </div>
                    <div className="detail-row">
                        <span className="label">Experience:</span>
                        <span>{app.experience_level}</span>
                    </div>
                    <div className="detail-row">
                        <span className="label">Applied:</span>
                        <span>{new Date(app.date_applied).toLocaleDateString()}</span>
                    </div>
                <div className="card-body">
                    <div className="section-title">Applicant Information</div>
                    <div className="detail-row">
                        <span className="label">Name:</span>
                        <span>{app.first_name} {app.last_name}</span>
                    </div>
                    <div className="detail-row">
                        <span className="label">Email:</span>
                        <span>{app.email}</span>
                    </div>
                    <div className="detail-row">
                        <span className="label">Phone:</span>
                        <span>{app.phone_number}</span>
                    </div>  
                </div>
                <div className="score-container">
                    <div className="score-header">
                        <span className="label">Match Score:</span>
                        <span className="score-value">{app.score}%</span>
                    </div>
                    <div className="score-bar">
                        <div className="score-fill" style={{width: `${app.score}%`}}></div>
                    </div>
                </div>
            </div>
            <div className="card-footer">
                <a href={`/applications/${app.id}`} className="btn primary">View Details</a>
                {app.cv_path && (
                    <a href={app.cv_path} className="btn secondary" target="_blank">
                        View CV
                    </a>
                )}
                <a href="#" className="btn bg-red-600 text-white" onClick={deleteApplication}>
                    Delete
                </a>
            </div>
        </div>
    )
}