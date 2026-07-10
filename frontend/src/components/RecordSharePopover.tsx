import { useEffect, useState } from 'react';
import { ShareIcon } from './DetailIcons';
import { Portal } from './Portal';
import { RecordSharePanel } from './RecordSharePanel';
import './Layout.css';

interface RecordSharePopoverProps {
  resource: string;
  sysId: string;
  record: Record<string, unknown>;
  canWrite: boolean;
}

export function RecordSharePopover({ resource, sysId, record, canWrite }: RecordSharePopoverProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open]);

  return (
    <div className="share-popover-root">
      <button
        type="button"
        className={`share-popover-trigger${open ? ' active' : ''}`}
        aria-label="Share and access"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((prev) => !prev)}
      >
        <ShareIcon size={18} />
      </button>

      {open && (
        <Portal>
          <div className="share-popover-overlay" role="presentation" onClick={() => setOpen(false)}>
            <div
              className="share-popover"
              role="dialog"
              aria-label="Share and access"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="share-popover-header">
                <h2>Share</h2>
                <button
                  type="button"
                  className="share-popover-close"
                  aria-label="Close"
                  onClick={() => setOpen(false)}
                >
                  ×
                </button>
              </div>
              <RecordSharePanel
                resource={resource}
                sysId={sysId}
                record={record}
                canWrite={canWrite}
              />
            </div>
          </div>
        </Portal>
      )}
    </div>
  );
}
