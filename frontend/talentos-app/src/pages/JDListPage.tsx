import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJDAnalyses } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { DocumentIcon, PlusIcon } from "../components/ui/icons";
import type { JDAnalysisSummary } from "../types";

const columns: Column<JDAnalysisSummary>[] = [
  { key: "code", header: "Code", render: (jd) => <Badge tone="neutral">{jd.jd_code}</Badge> },
  { key: "title", header: "Job title", render: (jd) => jd.job_title || "-" },
  { key: "skills", header: "Skills", render: (jd) => jd.skills_count, align: "right" },
  { key: "created_by", header: "Created by", render: (jd) => jd.created_by || "-" },
  { key: "created_at", header: "Created on", render: (jd) => formatDateTime(jd.created_at) },
];

export default function JDListPage() {
  const [jds, setJds] = useState<JDAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJDAnalyses()
      .then(setJds)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  return (
    <div className="page">
      <PageHeader
        eyebrow="Requirements"
        title="Job requirements"
        subtitle="Job descriptions analyzed into role context and weighted skill rubrics."
        actions={
          <Link to="/requirements/new">
            <Button icon={<PlusIcon width={16} height={16} />}>New requirement</Button>
          </Link>
        }
      />

      <Card>
        {error && <p className="error-text">{error}</p>}
        {jds === null ? (
          <SkeletonRows rows={5} columns={5} />
        ) : jds.length === 0 ? (
          <EmptyState
            icon={<DocumentIcon width={26} height={26} />}
            title="No requirements yet"
            description="Analyze a job description to extract role context and weighted skill rubrics."
            action={
              <Link to="/requirements/new">
                <Button>New requirement</Button>
              </Link>
            }
          />
        ) : (
          <Table
            columns={columns}
            rows={jds}
            getRowKey={(jd) => jd.id}
            getRowHref={(jd) => `/requirements/${jd.id}`}
          />
        )}
      </Card>
    </div>
  );
}
