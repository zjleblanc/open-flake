import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api, getRecordPermissions, stateBadge, stateLabel, stateOptionsFor } from '../api/client';
import { DetailFieldGroup, ReadOnlyFieldInput } from '../components/DetailFieldControls';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import {
  ActivityIcon,
  AttachmentsIcon,
  CommentsIcon,
  FieldsIcon,
  OverviewIcon,
  SystemIcon,
} from '../components/DetailIcons';
import { EmptyValue } from '../components/EmptyValue';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { usePageHeader } from '../components/PageHeaderContext';
import { RecordActivitySection } from '../components/RecordActivitySection';
import { RecordAttachmentsSection } from '../components/RecordAttachmentsSection';
import { RecordCommentsSection } from '../components/RecordCommentsSection';
import { RecordDetailHeaderActions } from '../components/RecordDetailHeaderActions';
import { RelatedRecordsSection } from '../components/RelatedRecordsSection';
import { OFSelect } from '../components/OFSelect';
import {
  isReferenceDeleted,
  referenceDisplayValue,
  referenceHref,
  refSysId,
  type RefTarget,
} from '../utils/referenceFields';
import '../components/Layout.css';

const RESOURCE = 'catalog-requests';
const LIST_PATH = '/requests';

interface FieldConfig {
  key: string;
  label: string;
  type?: 'textarea' | 'select-state';
  refTarget?: RefTarget;
}

const EDITABLE_FIELDS: FieldConfig[] = [
  { key: 'short_description', label: 'Short Description' },
  { key: 'description', label: 'Description', type: 'textarea' },
  { key: 'state', label: 'State', type: 'select-state' },
];

const LOCKED_FIELDS: FieldConfig[] = [
  { key: 'request_state', label: 'Request State' },
  { key: 'stage', label: 'Stage' },
  { key: 'approval', label: 'Approval' },
  { key: 'requested_for', label: 'Requested For', refTarget: 'user' },
  { key: 'requested_by', label: 'Requested By', refTarget: 'user' },
  { key: 'opened_by', label: 'Opened By', refTarget: 'user' },
  { key: 'assignment_group', label: 'Assignment Group', refTarget: 'group' },
  { key: 'assigned_to', label: 'Assigned To', refTarget: 'user' },
  { key: 'cmdb_ci', label: 'Configuration Item', refTarget: 'cmdb_ci' },
  { key: 'category', label: 'Category' },
  { key: 'subcategory', label: 'Subcategory' },
];

const SYSTEM_FIELDS: FieldConfig[] = [
  { key: 'sys_id', label: 'Sys ID' },
  { key: 'sys_created_on', label: 'Created' },
  { key: 'sys_updated_on', label: 'Updated' },
  { key: 'sys_created_by', label: 'Created By' },
  { key: 'sys_updated_by', label: 'Updated By' },
];

const SECTION = {
  details: 'req-section-details',
  items: 'req-section-items',
  system: 'req-section-system',
  attachments: 'req-section-attachments',
  comments: 'req-section-comments',
  activity: 'req-section-activity',
} as const;

const FIELD_LABELS: Record<string, string> = Object.fromEntries(
  [...EDITABLE_FIELDS, ...LOCKED_FIELDS].map((field) => [field.key, field.label]),
);

function buildEditableForm(data: Record<string, string>): Record<string, string> {
  const form: Record<string, string> = {};
  EDITABLE_FIELDS.forEach((field) => {
    form[field.key] = data[field.key] || '';
  });
  return form;
}

function formsEqual(a: Record<string, string>, b: Record<string, string>): boolean {
  return EDITABLE_FIELDS.every((field) => (a[field.key] ?? '') === (b[field.key] ?? ''));
}

function resolveLockedDisplay(field: FieldConfig, raw: unknown): unknown {
  if (field.type === 'select-state') {
    return stateLabel(String(raw), RESOURCE) || raw;
  }
  return raw;
}

export function RequestDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Record<string, string>>({});

  const { data, isLoading } = useQuery({
    queryKey: ['record', RESOURCE, sysId],
    queryFn: () => api.getRecord(RESOURCE, sysId!),
    enabled: !!sysId,
  });

  const permissions = data ? getRecordPermissions(data) : null;
  const canWrite = !!permissions?.write;

  const { data: attachments = [], isLoading: attachmentsLoading } = useQuery({
    queryKey: ['attachments', RESOURCE, sysId],
    queryFn: () => api.listAttachments(RESOURCE, sysId!),
    enabled: !!sysId && !!permissions?.read,
  });

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', RESOURCE, sysId],
    queryFn: () => api.listComments(RESOURCE, sysId!),
    enabled: !!sysId && !!(permissions?.comment || permissions?.write),
  });

  const { data: childItemsData, isLoading: childItemsLoading } = useQuery({
    queryKey: ['records', 'catalog-request-items', 'request', sysId],
    queryFn: () => api.listRecords('catalog-request-items', { query: `request=${sysId}` }),
    enabled: !!sysId,
  });
  const childItems = useMemo(() => childItemsData?.records ?? [], [childItemsData]);

  useEffect(() => {
    if (!data) return;
    setForm(buildEditableForm(data));
  }, [data]);

  const savedForm = useMemo(() => (data ? buildEditableForm(data) : {}), [data]);
  const isDirty = useMemo(() => !formsEqual(form, savedForm), [form, savedForm]);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateRecord(RESOURCE, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', RESOURCE, sysId] });
      queryClient.invalidateQueries({ queryKey: ['records', RESOURCE] });
    },
  });

  const recordTitle = data?.number || data?.sys_id || 'Loading…';
  const editableFields = canWrite ? EDITABLE_FIELDS : [];
  const displayedLockedFields = canWrite ? LOCKED_FIELDS : [...EDITABLE_FIELDS, ...LOCKED_FIELDS];
  const showEditableDivider = displayedLockedFields.length > 0 && editableFields.length > 0;

  const sectionNavItems = useMemo((): DetailSectionNavItem[] => {
    const items: DetailSectionNavItem[] = [
      {
        id: SECTION.details,
        title: 'Details',
        icon: <OverviewIcon size={14} />,
        accent: 'accent',
      },
      {
        id: SECTION.items,
        title: 'Requested Items',
        icon: <FieldsIcon size={14} />,
        accent: 'info',
        count: childItemsLoading ? '…' : childItems.length,
      },
      {
        id: SECTION.system,
        title: 'System',
        icon: <SystemIcon size={14} />,
        accent: 'primary',
      },
    ];

    if (sysId && permissions?.read) {
      items.push({
        id: SECTION.attachments,
        title: 'Attachments',
        icon: <AttachmentsIcon size={14} />,
        accent: 'info',
        count: attachmentsLoading ? '…' : attachments.length,
      });
    }

    if (sysId && (permissions?.comment || permissions?.write)) {
      items.push({
        id: SECTION.comments,
        title: 'Comments',
        icon: <CommentsIcon size={14} />,
        accent: 'accent',
        count: comments.length,
      });
    }

    if (sysId && permissions?.read) {
      items.push({
        id: SECTION.activity,
        title: 'Activity',
        icon: <ActivityIcon size={14} />,
        accent: 'primary',
      });
    }

    return items;
  }, [
    attachments.length,
    attachmentsLoading,
    childItems.length,
    childItemsLoading,
    comments.length,
    permissions?.comment,
    permissions?.read,
    permissions?.write,
    sysId,
  ]);

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Requests', to: LIST_PATH },
      { label: isLoading || !data ? 'Loading…' : recordTitle },
    ],
    [isLoading, data, recordTitle],
  );
  const headerBadge = useMemo(() => {
    if (isLoading || !data) return undefined;
    if (!data.state) return <EmptyValue />;
    return (
      <span className={`badge ${stateBadge(data.state, RESOURCE)}`}>
        {stateLabel(data.state, RESOURCE)}
      </span>
    );
  }, [isLoading, data]);
  const headerActions = useMemo(
    () =>
      !isLoading && data && sysId ? (
        <RecordDetailHeaderActions
          resource={RESOURCE}
          sysId={sysId}
          record={data}
          recordLabel={recordTitle}
          listPath={LIST_PATH}
          canWrite={canWrite}
        />
      ) : undefined,
    [isLoading, data, sysId, recordTitle, canWrite],
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
            id={SECTION.details}
            title="Details"
            icon={<OverviewIcon size={14} />}
            accent="accent"
            defaultOpen
          >
            <div className="detail-field-groups">
              {displayedLockedFields.length > 0 && (
                <DetailFieldGroup>
                  {displayedLockedFields.map((field) => {
                    const fieldSysId = field.refTarget ? refSysId(data[field.key]) : '';
                    return (
                      <ReadOnlyFieldInput
                        key={field.key}
                        id={`req-${field.key}`}
                        fieldKey={field.key}
                        label={field.label}
                        value={
                          field.refTarget
                            ? referenceDisplayValue(data, field.key)
                            : resolveLockedDisplay(field, data[field.key])
                        }
                        href={
                          field.refTarget && fieldSysId
                            ? referenceHref(field.refTarget, fieldSysId)
                            : undefined
                        }
                        deleted={field.refTarget ? isReferenceDeleted(data, field.key) : false}
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
                      <label htmlFor={`req-${field.key}`}>{field.label}</label>
                      {field.type === 'select-state' ? (
                        <OFSelect
                          id={`req-${field.key}`}
                          value={form[field.key] ?? ''}
                          onChange={(value) => setForm({ ...form, [field.key]: value as string })}
                          options={stateOptionsFor(RESOURCE)}
                        />
                      ) : field.type === 'textarea' ? (
                        <textarea
                          id={`req-${field.key}`}
                          rows={3}
                          value={form[field.key] ?? ''}
                          onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        />
                      ) : (
                        <input
                          id={`req-${field.key}`}
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

          <RelatedRecordsSection
            id={SECTION.items}
            title="Requested Items"
            icon={<FieldsIcon size={14} />}
            accent="info"
            basePath="/requested-items"
            resource="catalog-request-items"
            records={childItems}
            isLoading={childItemsLoading}
            emptyMessage="No requested items linked to this request yet"
          />

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
                  id={`req-${field.key}`}
                  fieldKey={field.key}
                  label={field.label}
                  value={data[field.key]}
                />
              ))}
            </DetailFieldGroup>
          </ExpandableDetailSection>

          {sysId && permissions?.read && (
            <RecordAttachmentsSection
              resource={RESOURCE}
              sysId={sysId}
              sectionId={SECTION.attachments}
              canManageAttachments={!!(permissions?.write || permissions?.delete)}
            />
          )}

          {sysId && (permissions?.comment || permissions?.write) && (
            <RecordCommentsSection
              resource={RESOURCE}
              sysId={sysId}
              sectionId={SECTION.comments}
              canComment={!!(permissions?.comment || permissions?.write)}
            />
          )}

          {sysId && permissions?.read && (
            <RecordActivitySection
              resource={RESOURCE}
              sysId={sysId}
              sectionId={SECTION.activity}
              fieldLabels={FIELD_LABELS}
            />
          )}
        </div>
      </div>

      <DetailSectionNav sections={sectionNavItems} />
    </div>
  );
}
