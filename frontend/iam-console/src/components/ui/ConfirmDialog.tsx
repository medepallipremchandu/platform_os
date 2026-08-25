import Button from "./Button";
import Modal from "./Modal";

interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/** Shared confirmation dialog for destructive actions (revoke a service principal, remove a role
 * assignment, delete a custom role) so every "are you sure?" prompt looks and behaves the same. */
export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  danger = true,
  loading = false,
  onConfirm,
  onCancel,
}: Props) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p>{message}</p>
    </Modal>
  );
}
