import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listJDAnalyses } from "../api/intake";
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
import { DocumentIcon, LockIcon, PlusIcon } from "../components/ui/icons";
import type { JDAnalysisSummary } from "../types";

const columns: Column<JDAnalysisSummary>[] = [
  { key: "code", header: "Code", render: (jd) => <Badge tone="neutral">{jd.jd_code}</Badge> },
  { key: "title", header: "Job title", sortable: true, render: (jd) => jd.job_title || "-" },
  { key: "skills", header: "Skills", render: (jd) => jd.skills_count, align: "right" },
  { key: "created_by", header: "Created by", render: (jd) => jd.created_by || "-" },
  { key: "created_at", header: "Created on", sortable: true, render: (jd) => formatDateTime(jd.created_at) },
];

export default function JDListPage() {
  const canRead = hasPermission(PERMISSIONS.REQUIREMENTS_READ);
  const canWrite = hasPermission(PERMISSIONS.REQUIREMENTS_WRITE);

  const [jds, setJds] = useState<JDAnalysisSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<string | null>("created_at");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  useEffect(() => {
    if (!canRead) return;
    listJDAnalyses()
      .then(setJds)
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
  // large in production would want server-side search/pagination instead (see listJDAnalyses).
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const base = !q
      ? jds || []
      : (jds || []).filter(
          (jd) => jd.jd_code.toLowerCase().includes(q) || (jd.job_title || "").toLowerCase().includes(q),
        );
    return sortRows(base, sortKey, sortDir, {
      title: (jd) => jd.job_title,
      created_at: (jd) => jd.created_at,
    });
  }, [jds, search, sortKey, sortDir]);

  if (!canRead) {
    return (
      <div className="page">
        <PageHeader eyebrow="Requirements" title="Job requirements" />
        <Card>
          <EmptyState
            icon={<LockIcon width={26} height={26} />}
            title="Access denied"
            description="Your account doesn't have permission to view requirements (talentos.intake.requirements.read)."
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="page">
      <PageHeader
        eyebrow="Requirements"
        title="Job requirements"
        subtitle="Job descriptions analyzed into role context and weighted skill rubrics."
        actions={
          canWrite && (
            <Link to="/requirements/new">
              <Button icon={<PlusIcon width={16} height={16} />}>New requirement</Button>
            </Link>
          )
        }
      />

      {jds && jds.length > 0 && (
        <Card>
          <div className="filter-bar">
            <div className="filter-bar__field" style={{ minWidth: 240 }}>
              <label htmlFor="jd-search">Search</label>
              <SearchInput id="jd-search" value={search} onChange={setSearch} placeholder="Search by code or job title" />
            </div>
          </div>
        </Card>
      )}

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
              canWrite && (
                <Link to="/requirements/new">
                  <Button>New requirement</Button>
                </Link>
              )
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState icon={<DocumentIcon width={26} height={26} />} title="No requirements match your search" />
        ) : (
          <Table
            columns={columns}
            rows={filtered}
            getRowKey={(jd) => jd.id}
            getRowHref={(jd) => `/requirements/${jd.id}`}
            sortKey={sortKey}
            sortDirection={sortDir}
            onSort={toggleSort}
          />
        )}
      </Card>
    </div>
  );
}
