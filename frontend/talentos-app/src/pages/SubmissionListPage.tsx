import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listSubmissions } from "../api/intake";
import { extractErrorMessage } from "../api/client";
import { formatDateTime } from "../lib/format";
import { hasPermission, PERMISSIONS } from "../lib/permissions";
import { sortRows, type SortDirection } from "../lib/sort";
import { toneForScore } from "../lib/tone";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import SearchInput from "../components/ui/SearchInput";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { LockIcon, PlusIcon, SubmissionIcon } from "../components/ui/icons";
import type { SubmissionSummary } from "../types";

type MatchTier = "" | "strong" | "moderate" | "weak";

const columns: Column<SubmissionSummary>[] = [
  { key: "code", header: "Code", render: (s) => <Badge tone="neutral">{s.submission_code}</Badge> },
  { key: "jd", header: "Requirement", render: (s) => `${s.jd_code} - ${s.job_title || "-"}` },
  { key: "applicant", header: "Applicant", render: (s) => `${s.resume_code} - ${s.candidate_name || "-"}` },
  {
    key: "match",
    header: "Match",
    sortable: true,
    sortKey: "overall_match_percentage",
    render: (s) =>
      s.overall_match_percentage != null ? (
        <Badge tone={toneForScore(s.overall_match_percentage)}>{s.overall_match_percentage}%</Badge>
      ) : (
        "-"
      ),
  },
  { key: "created_at", header: "Created on", sortable: true, render: (s) => formatDateTime(s.created_at) },
];

// Mirrors lib/tone.ts's toneForScore thresholds (75%+ success/"strong", 45-74% warning/"moderate",
// below that danger/"weak") so this filter's tiers line up with the same badge coloring shown in
// the table.
function matchesTier(pct: number | null, tier: MatchTier): boolean {
  if (!tier) return true;
  if (pct == null) return false;
  if (tier === "strong") return pct >= 75;
  if (tier === "moderate") return pct >= 45 && pct < 75;
  return pct < 45;
}

export default function SubmissionListPage() {
  const canRead = hasPermission(PERMISSIONS.SUBMISSIONS_READ);
  const canWrite = hasPermission(PERMISSIONS.SUBMISSIONS_WRITE);

  const [submissions, setSubmissions] = useState<SubmissionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [matchTier, setMatchTier] = useState<MatchTier>("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  useEffect(() => {
    if (!canRead) return;
    listSubmissions()
      .then(setSubmissions)
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

  // Client-side search/filter/sort over the full list - fine at today's per-org scale; a list
  // that grows large in production would want server-side search/pagination instead (see
  // listSubmissions).
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const base = (submissions || []).filter((s) => {
      if (!matchesTier(s.overall_match_percentage, matchTier)) return false;
      if (!q) return true;
      return (
        s.jd_code.toLowerCase().includes(q) ||
        (s.job_title || "").toLowerCase().includes(q) ||
        s.resume_code.toLowerCase().includes(q) ||
        (s.candidate_name || "").toLowerCase().includes(q)
      );
    });
    return sortRows(base, sortKey, sortDir, {
      created_at: (s) => s.created_at,
      overall_match_percentage: (s) => s.overall_match_percentage,
    });
  }, [submissions, search, matchTier, sortKey, sortDir]);

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader eyebrow="Submissions" title="Requirement x applicant submissions" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view submissions (talentos.intake.submissions.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Submissions"
        title="Requirement x applicant submissions"
        subtitle="Pair a requirement with an applicant to run an enterprise-grade match analysis."
        actions={
          canWrite && (
            <Link to="/submissions/new">
              <Button icon={<PlusIcon width={16} height={16} />}>New submission</Button>
            </Link>
          )
        }
      />

      {submissions && submissions.length > 0 && (
        <Card>
          <div className="filter-bar">
            <div className="filter-bar__field" style={{ minWidth: 240 }}>
              <label htmlFor="submission-search">Search</label>
              <SearchInput
                id="submission-search"
                value={search}
                onChange={setSearch}
                placeholder="Search by code, requirement, or candidate"
              />
            </div>
            <div className="filter-bar__field">
              <label htmlFor="submission-match-tier">Match</label>
              <select
                id="submission-match-tier"
                value={matchTier}
                onChange={(e) => setMatchTier(e.target.value as MatchTier)}
              >
                <option value="">All</option>
                <option value="strong">Strong (75%+)</option>
                <option value="moderate">Moderate (45-74%)</option>
                <option value="weak">Weak (&lt;45%)</option>
              </select>
            </div>
          </div>
        </Card>
      )}

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
              canWrite && (
                <Link to="/submissions/new">
                  <Button>New submission</Button>
                </Link>
              )
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState icon={<SubmissionIcon width={26} height={26} />} title="No submissions match your filters" />
        ) : (
          <Table
            columns={columns}
            rows={filtered}
            getRowKey={(s) => s.id}
            getRowHref={(s) => `/submissions/${s.id}`}
            sortKey={sortKey}
            sortDirection={sortDir}
            onSort={toggleSort}
          />
        )}
      </Card>
    </div>
  );
}
