import { useState } from "react";
import Button from "./ui/Button";
import Modal from "./ui/Modal";
import { AlertCircleIcon, CheckCircleIcon, CopyIcon } from "./ui/icons";

interface Props {
  title: string;
  clientId: string;
  clientSecret: string;
  onAcknowledge: () => void;
}

/** One-time secret reveal, used identically after creating a service principal and after
 * rotating its secret - iam-service only ever returns the plaintext secret once and stores a
 * hash, so this is the only chance the operator gets to copy it. */
export default function SecretRevealModal({ title, clientId, clientSecret, onAcknowledge }: Props) {
  const [copied, setCopied] = useState(false);

  async function copySecret() {
    try {
      await navigator.clipboard.writeText(clientSecret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API can be unavailable (e.g. an insecure context) - the value is still
      // selectable/copyable by hand from the <code> element.
    }
  }

  return (
    <Modal title={title} dismissible={false} footer={<Button onClick={onAcknowledge}>I&apos;ve copied this secret</Button>}>
      <p className="secret-reveal__warning">
        <AlertCircleIcon width={18} height={18} />
        This is the only time this client secret will be shown. Copy it now and store it somewhere
        safe - iam-service keeps only a hash and cannot show it again.
      </p>
      <div className="secret-reveal__field">
        <label>Client ID</label>
        <div className="secret-reveal__value">
          <code>{clientId}</code>
        </div>
      </div>
      <div className="secret-reveal__field">
        <label>Client secret</label>
        <div className="secret-reveal__value">
          <code>{clientSecret}</code>
          <Button
            variant="secondary"
            size="sm"
            className="secret-reveal__copy"
            onClick={copySecret}
            icon={copied ? <CheckCircleIcon width={15} height={15} /> : <CopyIcon width={15} height={15} />}
          >
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
