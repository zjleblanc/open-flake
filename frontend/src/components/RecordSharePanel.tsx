import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, getRecordPermissions, type RecordPermissions } from '../api/client';
import { EmptyValue } from './EmptyValue';
import { isEmptyDisplayValue } from '../utils/emptyDisplay';
import { ConfirmDialog } from './ConfirmDialog';
import { OFSelect } from './OFSelect';

function refValue(field: unknown): string {
  if (!field) return '';
  if (typeof field === 'object' && field !== null && 'value' in field) {
    return String((field as { value: string }).value);
  }
  return String(field);
}

function formatPermissions(perms: RecordPermissions): string[] {
  const labels: string[] = [];
  if (perms.write) labels.push('Write');
  else if (perms.comment) labels.push('Comment');
  else if (perms.read) labels.push('View');
  if (perms.delete && perms.write) labels.push('Delete');
  return labels.length > 0 ? labels : ['None'];
}

interface RecordSharePanelProps {
  resource: string;
  sysId: string;
  record: Record<string, unknown>;
  canWrite: boolean;
}

export function RecordSharePanel({ resource, sysId, record, canWrite }: RecordSharePanelProps) {
  const queryClient = useQueryClient();
  const permissions = getRecordPermissions(record);
  const [accessLevel, setAccessLevel] = useState<'view' | 'comment'>('view');
  const [granteeType, setGranteeType] = useState<'user' | 'group'>('user');
  const [granteeId, setGranteeId] = useState('');
  const [owner, setOwner] = useState(refValue(record.owner));
  const [ownerGroup, setOwnerGroup] = useState(refValue(record.owner_group));
  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);

  useEffect(() => {
    setOwner(refValue(record.owner));
    setOwnerGroup(refValue(record.owner_group));
  }, [record.owner, record.owner_group]);

  const { data: grants = [] } = useQuery({
    queryKey: ['grants', resource, sysId],
    queryFn: () => api.listGrants(resource, sysId),
    enabled: canWrite,
  });

  const users = useQuery({
    queryKey: ['records', 'users'],
    queryFn: () => api.listRecords('users'),
  });

  const groups = useQuery({
    queryKey: ['records', 'groups'],
    queryFn: () => api.listRecords('groups'),
  });

  const userLabels = Object.fromEntries(
    (users.data?.records || []).map((u) => [u.sys_id, u.user_name]),
  );
  const groupLabels = Object.fromEntries(
    (groups.data?.records || []).map((g) => [g.sys_id, g.name]),
  );

  const ownerMutation = useMutation({
    mutationFn: (payload: { owner?: string; owner_group?: string }) =>
      api.updateRecord(resource, sysId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', resource, sysId] });
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGrant(resource, sysId, {
        access_level: accessLevel,
        user_sys_id: granteeType === 'user' ? granteeId : undefined,
        group_sys_id: granteeType === 'group' ? granteeId : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grants', resource, sysId] });
      setGranteeId('');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (grantSysId: string) => api.deleteGrant(resource, sysId, grantSysId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['grants', resource, sysId] });
      setPendingDelete(null);
    },
  });

  const granteeOptions =
    granteeType === 'user'
      ? (users.data?.records || []).map((u) => ({ id: u.sys_id, label: u.user_name }))
      : (groups.data?.records || []).map((g) => ({ id: g.sys_id, label: g.name }));

  const ownerLabel = isEmptyDisplayValue(owner) ? null : userLabels[owner] || owner;
  const ownerGroupLabel = isEmptyDisplayValue(ownerGroup)
    ? null
    : groupLabels[ownerGroup] || ownerGroup;
  const permissionLabels = formatPermissions(permissions);

  return (
    <div className="share-panel">
      <section className="share-panel-section">
        <h3 className="share-panel-section-title">Your access</h3>
        <div className="share-permission-badges">
          {permissionLabels.map((label) => (
            <span key={label} className="share-permission-badge">
              {label}
            </span>
          ))}
        </div>
      </section>

      <section className="share-panel-section">
        <h3 className="share-panel-section-title">Ownership</h3>
        {canWrite ? (
          <div className="share-ownership-form">
            <div className="form-group">
              <label htmlFor={`owner-${sysId}`}>Owner</label>
              <OFSelect
                id={`owner-${sysId}`}
                autocomplete
                placeholder="None"
                value={owner}
                onChange={(value) => setOwner(value as string)}
                options={(users.data?.records || []).map((u) => ({
                  value: u.sys_id,
                  label: u.user_name,
                }))}
              />
            </div>
            <div className="form-group">
              <label htmlFor={`owner-group-${sysId}`}>Owner group</label>
              <OFSelect
                id={`owner-group-${sysId}`}
                autocomplete
                placeholder="None"
                value={ownerGroup}
                onChange={(value) => setOwnerGroup(value as string)}
                options={(groups.data?.records || []).map((g) => ({
                  value: g.sys_id,
                  label: g.name,
                }))}
              />
            </div>
            <button
              className="btn btn-secondary btn-sm"
              type="button"
              disabled={ownerMutation.isPending}
              onClick={() =>
                ownerMutation.mutate({
                  owner: owner || '',
                  owner_group: ownerGroup || '',
                })
              }
            >
              Save ownership
            </button>
          </div>
        ) : (
          <dl className="share-ownership-readonly">
            <div>
              <dt>Owner</dt>
              <dd>{ownerLabel ?? <EmptyValue />}</dd>
            </div>
            <div>
              <dt>Owner group</dt>
              <dd>{ownerGroupLabel ?? <EmptyValue />}</dd>
            </div>
          </dl>
        )}
      </section>

      {canWrite && (
        <section className="share-panel-section">
          <h3 className="share-panel-section-title">Additional access</h3>
          <p className="share-panel-intro text-muted text-sm">
            Grant view or comment access to other users and groups.
          </p>

          {grants.length === 0 ? (
            <p className="empty-state">No access grants yet</p>
          ) : (
            <ul className="sharing-grant-list">
              {grants.map((g) => {
                const grantee =
                  (g.user_sys_id && userLabels[g.user_sys_id]) ||
                  (g.group_sys_id && groupLabels[g.group_sys_id]) ||
                  g.user_sys_id ||
                  g.group_sys_id;
                const granteeKind = g.user_sys_id ? 'User' : 'Group';
                return (
                  <li key={g.sys_id} className="sharing-grant-item">
                    <div className="sharing-grant-info">
                      <span className="sharing-grant-level">{g.access_level}</span>
                      <span className="sharing-grant-name">
                        {granteeKind}: {grantee}
                      </span>
                    </div>
                    <button
                      className="btn btn-danger btn-sm"
                      type="button"
                      onClick={() =>
                        setPendingDelete({
                          id: g.sys_id,
                          label: `${granteeKind}: ${grantee}`,
                        })
                      }
                      disabled={deleteMutation.isPending}
                    >
                      Remove
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="sharing-grant-form">
            <div className="form-group">
              <label htmlFor={`grant-level-${sysId}`}>Access level</label>
              <OFSelect
                id={`grant-level-${sysId}`}
                value={accessLevel}
                onChange={(value) => setAccessLevel(value as 'view' | 'comment')}
                options={[
                  { value: 'view', label: 'View' },
                  { value: 'comment', label: 'Comment' },
                ]}
              />
            </div>
            <div className="form-group">
              <label htmlFor={`grantee-type-${sysId}`}>Grant to</label>
              <OFSelect
                id={`grantee-type-${sysId}`}
                value={granteeType}
                onChange={(value) => {
                  setGranteeType(value as 'user' | 'group');
                  setGranteeId('');
                }}
                options={[
                  { value: 'user', label: 'User' },
                  { value: 'group', label: 'Group' },
                ]}
              />
            </div>
            <div className="form-group">
              <label htmlFor={`grantee-id-${sysId}`}>
                {granteeType === 'user' ? 'User' : 'Group'}
              </label>
              <OFSelect
                id={`grantee-id-${sysId}`}
                autocomplete
                placeholder="Select…"
                value={granteeId}
                onChange={(value) => setGranteeId(value as string)}
                options={granteeOptions.map((o) => ({ value: o.id, label: o.label }))}
              />
            </div>
            <button
              className="btn btn-primary"
              type="button"
              disabled={!granteeId || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Add access
            </button>
          </div>
        </section>
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Remove access"
        message={
          pendingDelete
            ? `Are you sure you want to remove access for "${pendingDelete.label}"?`
            : ''
        }
        confirmLabel="Remove"
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
