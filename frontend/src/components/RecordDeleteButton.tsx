import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { buildPermanentItems, permanentTotal } from '../utils/cascadeSummary';
import { ConfirmDialog } from './ConfirmDialog';
import './Layout.css';

interface RecordDeleteButtonProps {
  resource: string;
  sysId: string;
  recordLabel: string;
  listPath: string;
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
  const permanentItems = buildPermanentItems(
    preview?.cascade_children ?? [],
    preview?.peripheral ?? {},
  );
  const hasPermanentItems = permanentItems.length > 0;
  const permanentCount = permanentTotal(permanentItems);
  const referenceCount = looseReferences.reduce((sum, group) => sum + group.records.length, 0);
  const isBusy = deleteMutation.isPending || (confirmOpen && previewQuery.isLoading);
  const isWide = hasPermanentItems || hasLooseReferences;

  const message = (
    <>
      <p className="confirm-dialog-warning">This action cannot be undone.</p>
      <div className="confirm-dialog-sections">
        {hasPermanentItems && (
          <div className="confirm-dialog-section">
            <h3 className="confirm-dialog-section-title">
              Permanently deleted
              <span className="confirm-dialog-section-count">{permanentCount}</span>
            </h3>
            <ul className="cascade-reference-groups">
              {permanentItems.map((item) => (
                <li key={item.key}>
                  <p className="cascade-reference-group-label">
                    {item.records.length > 0 ? item.label : `${item.count} ${item.label}`}
                  </p>
                  {item.records.length > 0 && (
                    <ul className="cascade-reference-group-items">
                      {item.records.map((record) => (
                        <li key={record.sys_id}>
                          {record.relationship ? (
                            record.relationship.direction === 'outgoing' ? (
                              <>
                                <span className="cascade-relationship-this">this</span>{' '}
                                <span className="badge badge-accent">
                                  {record.relationship.type}
                                </span>
                                {' \u2192 '}
                                {record.label}
                              </>
                            ) : (
                              <>
                                {record.label}{' '}
                                <span className="badge badge-accent">
                                  {record.relationship.type}
                                </span>
                                {' \u2192 '}
                                <span className="cascade-relationship-this">this</span>
                              </>
                            )
                          ) : (
                            record.label
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                  {item.count > item.records.length && (
                    <p className="cascade-reference-more">
                      +{item.count - item.records.length} more
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {hasLooseReferences && (
          <div className="confirm-dialog-section">
            <h3 className="confirm-dialog-section-title">
              Referenced by
              <span className="confirm-dialog-section-count">{referenceCount}</span>
            </h3>
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
          </div>
        )}
      </div>
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
        title={`Delete "${recordLabel}"?`}
        message={message}
        error={error}
        wide={isWide}
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
