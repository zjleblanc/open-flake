import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { Portal } from './Portal';
import './Layout.css';

export interface ConfirmDialogAction {
  label: string;
  pendingLabel?: string;
  onClick: () => void;
  variant?: 'danger' | 'secondary';
}

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: ReactNode;
  error?: string | null;
  confirmLabel?: string;
  pendingLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending?: boolean;
  /** Extra choice buttons rendered between Cancel and the primary confirm action. */
  extraActions?: ConfirmDialogAction[];
  /** Widen the dialog for content-heavy messages (e.g. cascade delete previews). */
  wide?: boolean;
}

export function ConfirmDialog({
  open,
  title,
  message,
  error,
  confirmLabel = 'Delete',
  pendingLabel,
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  isPending = false,
  extraActions,
  wide = false,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!open) return;

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape' && !isPending) onCancel();
    }

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open, isPending, onCancel]);

  if (!open) return null;

  const busyLabel = pendingLabel || `${confirmLabel}…`;

  return (
    <Portal>
      <div
        className="confirm-dialog-overlay"
        role="presentation"
        onClick={isPending ? undefined : onCancel}
      >
        <div
          className={wide ? 'confirm-dialog confirm-dialog--wide' : 'confirm-dialog'}
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-dialog-title"
          aria-describedby="confirm-dialog-message"
          onClick={(event) => event.stopPropagation()}
        >
          <h2 id="confirm-dialog-title" className="confirm-dialog-title">
            {title}
          </h2>
          <div id="confirm-dialog-message" className="confirm-dialog-message">
            {message}
          </div>
          {error && <p className="confirm-dialog-error">{error}</p>}
          <div className="confirm-dialog-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onCancel}
              disabled={isPending}
            >
              {cancelLabel}
            </button>
            {extraActions?.map((action) => (
              <button
                key={action.label}
                type="button"
                className={
                  action.variant === 'secondary' ? 'btn btn-secondary' : 'btn btn-danger-solid'
                }
                onClick={action.onClick}
                disabled={isPending}
              >
                {isPending ? action.pendingLabel || `${action.label}…` : action.label}
              </button>
            ))}
            <button
              type="button"
              className="btn btn-danger-solid"
              onClick={onConfirm}
              disabled={isPending}
            >
              {isPending ? busyLabel : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </Portal>
  );
}
