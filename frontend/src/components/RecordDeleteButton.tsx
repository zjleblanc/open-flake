import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, type CascadePreview } from '../api/client';
import { buildCascadeSummary } from '../utils/cascadeSummary';
import { ConfirmDialog } from './ConfirmDialog';
import './Layout.css';

interface RecordDeleteButtonProps {
  resource: string;
  sysId: string;
  recordLabel: string;
  listPath: string;
}

function summarize(recordLabel: string, preview?: CascadePreview): string {
  const fallback = `Are you sure you want to permanently delete "${recordLabel}"? This action cannot be undone.`;
  if (!preview) return fallback;
  const cascadeParts = preview.cascade_children.map((child) => `${child.count} ${child.label}`);
  return buildCascadeSummary(
    `Deleting "${recordLabel}"`,
    cascadeParts,
    preview.peripheral,
    fallback,
  );
}

export function RecordDeleteButton({
  resource,
  sysId,
  recordLabel,
  listPath,
}: RecordDeleteButtonProps) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const previewQuery = useQuery({
    queryKey: ['cascade-preview', resource, sysId],
    queryFn: () => api.getCascadePreview(resource, sysId),
    enabled: confirmOpen,
    staleTime: 0,
  });

  const deleteMutation = useMutation({
    mutationFn: (refMode?: 'clear' | 'cascade') => api.deleteRecord(resource, sysId, refMode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['records', resource] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      navigate(listPath);
    },
    onError: (deleteError: Error) => {
      setError(deleteError.message || 'Failed to delete record.');
    },
  });

  const preview = previewQuery.data;
  const looseReferences = preview?.loose_references ?? [];
  const hasLooseReferences = looseReferences.length > 0;
  const isBusy = deleteMutation.isPending || (confirmOpen && previewQuery.isLoading);

  const message = (
    <>
      <p>{summarize(recordLabel, preview)}</p>
      {hasLooseReferences && (
        <>
          <p>The following records reference this item:</p>
          <ul className="cascade-reference-groups">
            {looseReferences.map((group) => (
              <li key={`${group.table}-${group.field}`}>
                <p className="cascade-reference-group-label">{group.label}</p>
                <ul className="cascade-reference-group-items">
                  {group.records.slice(0, 5).map((record) => (
                    <li key={record.sys_id}>{record.label}</li>
                  ))}
                </ul>
                {group.records.length > 5 && (
                  <p className="cascade-reference-more">+{group.records.length - 5} more</p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );

  return (
    <>
      <button
        type="button"
        className="btn btn-danger-solid"
        onClick={() => {
          setError(null);
          setConfirmOpen(true);
        }}
        disabled={deleteMutation.isPending}
      >
        Delete
      </button>
      <ConfirmDialog
        open={confirmOpen}
        title="Delete record"
        message={message}
        error={error}
        wide={hasLooseReferences}
        confirmLabel={hasLooseReferences ? 'Delete and clear references' : 'Delete'}
        pendingLabel="Deleting…"
        onConfirm={() => deleteMutation.mutate(hasLooseReferences ? 'clear' : undefined)}
        extraActions={
          hasLooseReferences
            ? [
                {
                  label: 'Delete all',
                  pendingLabel: 'Deleting…',
                  onClick: () => deleteMutation.mutate('cascade'),
                },
              ]
            : undefined
        }
        onCancel={() => {
          setError(null);
          setConfirmOpen(false);
        }}
        isPending={isBusy}
      />
    </>
  );
}
