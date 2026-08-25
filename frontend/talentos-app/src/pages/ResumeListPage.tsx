import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listResumeAnalyses } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { PlusIcon, UsersIcon } from "../components/ui/icons";
import type { ResumeAnalysisSummary } from "../types";

const columns: Column<ResumeAnalysisSummary>[] = [
  { key: "code", header: "Code", render: (r) => <Badge tone="neutral">{r.resume_code}</Badge> },
  { key: "candidate", header: "Candidate", render: (r) => r.candidate_name || "-" },
  {
    key: "experience",
    header: "Experience",
    render: (r) => (r.total_experience_years != null ? `${r.total_experience_years} yrs` : "-"),
  },
  { key: "created_by", header: "Uploaded by", render: (r) => r.created_by || "-" },
  { key: "created_at", header: "Uploaded on", render: (r) => formatDateTime(r.created_at) },
];

export default function ResumeListPage() {
  const [resumes, setResumes] = useState<ResumeAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listResumeAnalyses()
      .then(setResumes)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Applicants"
        title="Applicant resumes"
        subtitle="Resumes analyzed into candidate profile, skills, and experience."
        actions={
          <Link to="/applicants/new">
            <Button icon={<PlusIcon width={16} height={16} />}>New applicant</Button>
          </Link>
        }
      />

      <Card>
        {error && <p className="error-text">{error}</p>}
        {resumes === null ? (
          <SkeletonRows rows={5} columns={5} />
        ) : resumes.length === 0 ? (
          <EmptyState
            icon={<UsersIcon width={26} height={26} />}
            title="No applicants yet"
            description="Upload a resume (PDF or DOCX) to extract a structured candidate profile."
            action={
              <Link to="/applicants/new">
                <Button>New applicant</Button>
              </Link>
            }
          />
        ) : (
          <Table
            columns={columns}
            rows={resumes}
            getRowKey={(r) => r.id}
            getRowHref={(r) => `/applicants/${r.id}`}
          />
        )}
      </Card>
    </div>
  );
}
