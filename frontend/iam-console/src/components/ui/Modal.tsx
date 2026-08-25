import type { ReactNode } from "react";
import { useEffect } from "react";
import { CloseIcon } from "./icons";

interface Props {
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  onClose?: () => void;
  /** When true, hides the close (X) button and ignores backdrop/Escape dismissal - for the
   * one-time secret reveal flow, where "I lost it, show it again" isn't an option and the user
   * must explicitly acknowledge they've copied it. */
  dismissible?: boolean;
}

export default function Modal({ title, children, footer, onClose, dismissible = true }: Props) {
  useEffect(() => {
    if (!dismissible || !onClose) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [dismissible, onClose]);

  return (
    <div className="modal-backdrop" onClick={dismissible ? onClose : undefined}>
      <div className="modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header">
          <h2 className="modal__title">{title}</h2>
          {dismissible && onClose && (
            <button type="button" className="modal__close" onClick={onClose} aria-label="Close">
              <CloseIcon width={18} height={18} />
            </button>
          )}
        </div>
        <div className="modal__body">{children}</div>
        {footer && <div className="modal__footer">{footer}</div>}
      </div>
    </div>
  );
}
