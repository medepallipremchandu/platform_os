import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAgents } from "../api/agentBuilder";
import { extractErrorMessage } from "../api/client";
import Badge from "../components/ui/Badge";
import Button from "../components/ui/Button";
import Card from "../components/ui/Card";
import EmptyState from "../components/ui/EmptyState";
import PageHeader from "../components/ui/PageHeader";
import { SkeletonRows } from "../components/ui/Skeleton";
import Table, { type Column } from "../components/ui/Table";
import { PlusIcon, SparkleIcon } from "../components/ui/icons";
import { formatDateTime } from "../lib/format";
import type { AgentStatus, AgentSummary } from "../types";

function statusTone(status: AgentStatus) {
  return status === "published" ? "success" : "neutral";
}

const columns: Column<AgentSummary>[] = [
  { key: "code", header: "Code", render: (a) => <Badge tone="neutral">{a.agent_code}</Badge> },
  { key: "name", header: "Name", render: (a) => a.name },
  { key: "model", header: "Primary model", render: (a) => a.primary_model.name },
  { key: "status", header: "Status", render: (a) => <Badge tone={statusTone(a.status)}>{a.status}</Badge> },
  { key: "created_by", header: "Created by", render: (a) => a.created_by || "-" },
  { key: "created_at", header: "Created on", render: (a) => formatDateTime(a.created_at) },
];

export default function AgentListPage() {
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  return (
    <div className="page">
      <PageHeader
        title="Agents"
        subtitle="Reusable AI tasks: a prompt template bound to a model, with limits - the AI layer every other service calls through."
        actions={
          <Link to="/agents/new">
            <Button icon={<PlusIcon width={16} height={16} />}>New agent</Button>
          </Link>
        }
      />

      <Card>
        {error && <p className="error-text">{error}</p>}
        {agents === null ? (
          <SkeletonRows rows={4} columns={6} />
        ) : agents.length === 0 ? (
          <EmptyState
            icon={<SparkleIcon width={26} height={26} />}
            title="No agents yet"
            description="Create an agent: pick a model, write a prompt template, and publish it to get an invoke credential."
            action={
              <Link to="/agents/new">
                <Button>New agent</Button>
              </Link>
            }
          />
        ) : (
          <Table
            columns={columns}
            rows={agents}
            getRowKey={(a) => a.id}
            getRowHref={(a) => `/agents/${a.id}`}
          />
        )}
      </Card>
    </div>
  );
}
