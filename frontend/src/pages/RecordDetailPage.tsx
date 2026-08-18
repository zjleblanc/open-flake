import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api, getRecordPermissions, stateBadge, stateLabel, stateOptionsFor } from '../api/client';
import { DetailFieldGroup, ReadOnlyFieldInput } from '../components/DetailFieldControls';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import { ActivityIcon, PropertiesIcon, SystemIcon } from '../components/DetailIcons';
import { EmptyValue } from '../components/EmptyValue';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { usePageHeader } from '../components/PageHeaderContext';
import { RecordActivityFeed } from '../components/RecordActivityFeed';
import { RecordDetailHeaderActions } from '../components/RecordDetailHeaderActions';
import { OFSelect } from '../components/OFSelect';
import '../components/Layout.css';

export interface DetailFieldConfig {
  key: string;
  label: string;
  type?: string;
  readOnly?: boolean;
}

interface RecordDetailProps {
  resource: string;
  title: string;
  listPath: string;
  fields: DetailFieldConfig[];
}

const SYSTEM_FIELDS: DetailFieldConfig[] = [
  { key: 'sys_id', label: 'Sys ID' },
  { key: 'sys_created_on', label: 'Created' },
  { key: 'sys_updated_on', label: 'Updated' },
  { key: 'sys_created_by', label: 'Created By' },
  { key: 'sys_updated_by', label: 'Updated By' },
];

const SECTION = {
  system: 'record-section-system',
  general: 'record-section-general',
  activity: 'record-section-activity',
} as const;

function formatReadOnlyValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object' && value !== null && 'value' in value) {
    return String((value as { value: string }).value);
  }
  return String(value);
}

export function RecordDetailPage({ resource, title, listPath, fields }: RecordDetailProps) {
  const { sysId } = useParams<{ sysId: string }>();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ['record', resource, sysId],
    queryFn: () => api.getRecord(resource, sysId!),
    enabled: !!sysId,
  });

  useEffect(() => {
    if (!data) return;
    const nextForm: Record<string, string> = {};
    fields.forEach((field) => {
      if (!field.readOnly) {
        nextForm[field.key] = data[field.key] || '';
      }
    });
    setForm(nextForm);
  }, [data, fields]);

  const savedForm = useMemo(() => {
    if (!data) return {};
    const nextForm: Record<string, string> = {};
    fields.forEach((field) => {
      if (!field.readOnly) {
        nextForm[field.key] = data[field.key] || '';
      }
    });
    return nextForm;
  }, [data, fields]);

  const isDirty = useMemo(() => {
    for (const field of fields) {
      if (field.readOnly) continue;
      if ((form[field.key] ?? '') !== (savedForm[field.key] ?? '')) return true;
    }
    return false;
  }, [form, savedForm, fields]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateRecord(resource, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', resource, sysId] });
      queryClient.invalidateQueries({ queryKey: ['records', resource] });
      queryClient.invalidateQueries({ queryKey: ['activity', resource, sysId] });
    },
  });

  const recordTitle = data?.number || data?.name || data?.sys_id || 'Loading…';
  const permissions = data ? getRecordPermissions(data) : null;
  const canWrite = !!permissions?.write;
  const editableFields = fields.filter((field) => canWrite && !field.readOnly);
  const lockedFields = fields.filter((field) => !canWrite || field.readOnly);
  const showEditableDivider = lockedFields.length > 0 && editableFields.length > 0;

  const sectionNavItems = useMemo((): DetailSectionNavItem[] => {
    const items: DetailSectionNavItem[] = [
      {
        id: SECTION.system,
        title: 'System',
        icon: <SystemIcon size={14} />,
        accent: 'primary',
      },
      {
        id: SECTION.general,
        title: 'General',
        icon: <PropertiesIcon size={14} />,
        accent: 'accent',
      },
    ];

    if (sysId && permissions?.read) {
      items.push({
        id: SECTION.activity,
        title: 'Activity',
        icon: <ActivityIcon size={14} />,
        accent: 'primary',
      });
    }

    return items;
  }, [permissions?.read, sysId]);

  const headerBreadcrumbs = useMemo(
    () => [
      { label: title, to: listPath },
      { label: isLoading || !data ? 'Loading…' : recordTitle },
    ],
    [title, listPath, isLoading, data, recordTitle],
  );
  const headerBadge = useMemo(() => {
    if (isLoading || !data) return undefined;
    if (!data.state) return <EmptyValue />;
    return (
      <span className={`badge ${stateBadge(data.state, resource)}`}>
        {stateLabel(data.state, resource)}
      </span>
    );
  }, [isLoading, data, resource]);
  const headerActions = useMemo(
    () =>
      !isLoading && data && sysId ? (
        <RecordDetailHeaderActions
          resource={resource}
          sysId={sysId}
          record={data}
          recordLabel={recordTitle}
          listPath={listPath}
          canWrite={canWrite}
        />
      ) : undefined,
    [isLoading, data, sysId, resource, recordTitle, listPath, canWrite],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, badge: headerBadge, actions: headerActions });

  if (isLoading || !data) {
    return <p className="empty-state">Loading…</p>;
  }

  return (
    <div className="detail-page-layout">
      <div className="detail-page-main">
        <div className="detail-sections-stack">
          <ExpandableDetailSection
            id={SECTION.system}
            title="System"
            icon={<SystemIcon size={14} />}
            accent="primary"
          >
            <DetailFieldGroup>
              {SYSTEM_FIELDS.map((field) => (
                <ReadOnlyFieldInput
                  key={field.key}
                  id={`field-${field.key}`}
                  fieldKey={field.key}
                  label={field.label}
                  value={data[field.key]}
                />
              ))}
            </DetailFieldGroup>
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.general}
            title="General"
            icon={<PropertiesIcon size={14} />}
            accent="accent"
            defaultOpen
          >
            <div className="detail-field-groups">
              {lockedFields.length > 0 && (
                <DetailFieldGroup>
                  {lockedFields.map((field) => {
                    const raw = data[field.key];
                    const display =
                      field.type === 'select-state'
                        ? stateLabel(String(raw), resource) || formatReadOnlyValue(raw)
                        : raw;

                    return (
                      <ReadOnlyFieldInput
                        key={field.key}
                        id={`field-${field.key}`}
                        fieldKey={field.key}
                        label={field.label}
                        value={display}
                        multiline={field.type === 'textarea'}
                        gridColumn={field.type === 'textarea' ? '1 / -1' : undefined}
                      />
                    );
                  })}
                </DetailFieldGroup>
              )}

              {editableFields.length > 0 && (
                <DetailFieldGroup dividerTop={showEditableDivider}>
                  {editableFields.map((field) => (
                    <div
                      className="form-group"
                      key={field.key}
                      style={{
                        marginBottom: 0,
                        gridColumn: field.type === 'textarea' ? '1 / -1' : undefined,
                      }}
                    >
                      <label htmlFor={`field-${field.key}`}>{field.label}</label>
                      {field.type === 'select-state' ? (
                        <OFSelect
                          id={`field-${field.key}`}
                          value={form[field.key] ?? ''}
                          onChange={(value) => setForm({ ...form, [field.key]: value as string })}
                          options={stateOptionsFor(resource)}
                        />
                      ) : field.type === 'textarea' ? (
                        <textarea
                          id={`field-${field.key}`}
                          rows={3}
                          value={form[field.key] ?? ''}
                          onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        />
                      ) : (
                        <input
                          id={`field-${field.key}`}
                          type="text"
                          value={form[field.key] ?? ''}
                          onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        />
                      )}
                    </div>
                  ))}
                </DetailFieldGroup>
              )}
            </div>

            {canWrite && editableFields.length > 0 && (
              <div style={{ marginTop: '1.25rem' }}>
                <button
                  className="btn btn-primary"
                  onClick={() => updateMutation.mutate(form)}
                  disabled={!isDirty || updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            )}
          </ExpandableDetailSection>

          {sysId && permissions?.read && (
            <RecordActivityFeed
              resource={resource}
              sysId={sysId}
              sectionId={SECTION.activity}
              fieldLabels={Object.fromEntries(fields.map((field) => [field.key, field.label]))}
              canComment={!!(permissions?.comment || permissions?.write)}
              canManageAttachments={!!(permissions?.write || permissions?.delete)}
            />
          )}
        </div>
      </div>

      <DetailSectionNav sections={sectionNavItems} />
    </div>
  );
}
