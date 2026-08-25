import type { OrgUser, Visibility } from "../../types";
import { GlobeIcon, LockIcon } from "./icons";
import MultiUserSelect from "./MultiUserSelect";

interface Props {
  visibility: Visibility;
  onVisibilityChange: (visibility: Visibility) => void;
  grantUserIds: string[];
  onGrantUserIdsChange: (ids: string[]) => void;
  users: OrgUser[];
  usersError?: string | null;
}

/**
 * First-class visibility control shared by the Providers and Call Agents forms: a clear
 * organization-wide vs. restricted-to-specific-people toggle, revealing a searchable multi-select
 * of users only in the restricted case. `users` is fetched by the caller from iam-service's
 * `GET /organizations/{id}/users` (see `src/api/iam.ts`) - voice-agent-service itself has no
 * user-listing endpoint of its own.
 */
export default function VisibilityPicker({
  visibility,
  onVisibilityChange,
  grantUserIds,
  onGrantUserIdsChange,
  users,
  usersError,
}: Props) {
  // voice-agent-service checks grants against the actor's `email_or_name` claim (an email for a
  // human principal), not their user id - see backend/voice-agent-service/app/services/
  // visibility.py::can_access. The grant value must be the email, not `user_id`.
  const userOptions = users.map((u) => ({ value: u.email, label: u.display_name || u.email, description: u.email }));

  return (
    <div className="visibility-picker">
      <span className="visibility-picker__label">Visibility</span>
      <div className="visibility-picker__options">
        <button
          type="button"
          className={`visibility-picker__option ${visibility === "organization" ? "visibility-picker__option--active" : ""}`}
          onClick={() => onVisibilityChange("organization")}
        >
          <GlobeIcon width={18} height={18} />
          <div>
            <div className="visibility-picker__option-title">Visible to everyone in this organization</div>
            <div className="hint-text">Anyone with read access can see and use this.</div>
          </div>
        </button>
        <button
          type="button"
          className={`visibility-picker__option ${visibility === "restricted" ? "visibility-picker__option--active" : ""}`}
          onClick={() => onVisibilityChange("restricted")}
        >
          <LockIcon width={18} height={18} />
          <div>
            <div className="visibility-picker__option-title">Visible only to specific people</div>
            <div className="hint-text">Choose exactly who can see and use this.</div>
          </div>
        </button>
      </div>

      {visibility === "restricted" && (
        <div className="visibility-picker__grant">
          <label htmlFor="grant-user-select">Grant access to</label>
          {usersError && <p className="error-text">{usersError}</p>}
          <MultiUserSelect options={userOptions} values={grantUserIds} onChange={onGrantUserIdsChange} />
          {grantUserIds.length === 0 && <p className="hint-text">No one has been granted access yet - add at least one person.</p>}
        </div>
      )}
    </div>
  );
}
