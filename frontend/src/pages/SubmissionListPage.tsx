import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listSubmissions } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { toneForScore } from "../lib/tone";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { PlusIcon, SubmissionIcon } from "../components/ui/icons";
import type { SubmissionSummary } from "../types";

const columns: Column<SubmissionSummary>[] = [
  { key: "code", header: "Code", render: (s) => <Badge tone="neutral">{s.submission_code}</Badge> },
  { key: "jd", header: "Requirement", render: (s) => `${s.jd_code} - ${s.job_title || "-"}` },
  { key: "applicant", header: "Applicant", render: (s) => `${s.resume_code} - ${s.candidate_name || "-"}` },
  {
    key: "match",
    header: "Match",
    render: (s) =>
      s.overall_match_percentage != null ? (
        <Badge tone={toneForScore(s.overall_match_percentage)}>{s.overall_match_percentage}%</Badge>
      ) : (
        "-"
      ),
  },
  { key: "created_at", header: "Created on", render: (s) => formatDateTime(s.created_at) },
];

export default function SubmissionListPage() {
  const [submissions, setSubmissions] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listSubmissions()
      .then(setSubmissions)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Submissions"
        title="Requirement x applicant submissions"
        subtitle="Pair a requirement with an applicant to run an enterprise-grade match analysis."
        actions={
          <Link to="/submissions/new">
            <Button icon={<PlusIcon width={16} height={16} />}>New submission</Button>
          </Link>
        }
      />

      <Card>
        {error && <p className="error-text">{error}</p>}
        {submissions === null ? (
          <SkeletonRows rows={5} columns={5} />
        ) : submissions.length === 0 ? (
          <EmptyState
            icon={<SubmissionIcon width={26} height={26} />}
            title="No submissions yet"
            description="Pair a requirement with an applicant to see how well they match."
            action={
              <Link to="/submissions/new">
                <Button>New submission</Button>
              </Link>
            }
          />
        ) : (
          <Table
            columns={columns}
            rows={submissions}
            getRowKey={(s) => s.id}
            getRowHref={(s) => `/submissions/${s.id}`}
          />
        )}
      </Card>
    </div>
  );
}
