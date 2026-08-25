import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listResumeAnalyses } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { LockIcon, PlusIcon, UsersIcon } from "../components/ui/icons";
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
  { key: "created_at", header: "Uploaded on", sortable: true, render: (r) => formatDateTime(r.created_at) },
];

export default function ResumeListPage() {
  const canRead = hasPermission(PERMISSIONS.APPLICANTS_READ);
  const canWrite = hasPermission(PERMISSIONS.APPLICANTS_WRITE);

  const [resumes, setResumes] = useState<ResumeAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  useEffect(() => {
    if (!canRead) return;
    listResumeAnalyses()
      .then(setResumes)
      .catch((err) => setError(extractErrorMessage(err)));
  }, [canRead]);

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  // Client-side search/sort over the full list - fine at today's per-org scale; a list that grows
  // large in production would want server-side search/pagination instead (see listResumeAnalyses).
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const base = !q
      ? resumes || []
      : (resumes || []).filter(
          (r) => r.resume_code.toLowerCase().includes(q) || (r.candidate_name || "").toLowerCase().includes(q),
        );
    return sortRows(base, sortKey, sortDir, {
      created_at: (r) => r.created_at,
    });
  }, [resumes, search, sortKey, sortDir]);

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader eyebrow="Applicants" title="Applicant resumes" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view applicants (talentos.intake.applicants.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Applicants"
        title="Applicant resumes"
        subtitle="Resumes analyzed into candidate profile, skills, and experience."
        actions={
          canWrite && (
            <Link to="/applicants/new">
              <Button icon={<PlusIcon width={16} height={16} />}>New applicant</Button>
            </Link>
          )
        }
      />

      {resumes && resumes.length > 0 && (
        <Card>
          <div className="filter-bar">
            <div className="filter-bar__field" style={{ minWidth: 240 }}>
              <label htmlFor="resume-search">Search</label>
              <SearchInput id="resume-search" value={search} onChange={setSearch} placeholder="Search by code or candidate name" />
            </div>
          </div>
        </Card>
      )}

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
              canWrite && (
                <Link to="/applicants/new">
                  <Button>New applicant</Button>
                </Link>
              )
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState icon={<UsersIcon width={26} height={26} />} title="No applicants match your search" />
        ) : (
          <Table
            columns={columns}
            rows={filtered}
            getRowKey={(r) => r.id}
            getRowHref={(r) => `/applicants/${r.id}`}
            sortKey={sortKey}
            sortDirection={sortDir}
            onSort={toggleSort}
          />
        )}
      </Card>
    </div>
  );
}
