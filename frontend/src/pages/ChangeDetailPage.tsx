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
  referenceDisplayValue,
  referenceHref,
  refSysId,
  type RefTarget,
} from '../utils/referenceFields';
import '../components/Layout.css';

const RESOURCE = 'change-requests';
const LIST_PATH = '/changes';
const CHANGE_TASKS_RESOURCE = 'change-tasks';
const CHANGE_TASKS_LIST_PATH = '/change-tasks';

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
  { key: 'priority', label: 'Priority' },
  { key: 'risk', label: 'Risk' },
  { key: 'type', label: 'Type' },
  { key: 'category', label: 'Category' },
  { key: 'chg_model', label: 'Change Model' },
  { key: 'requested_by', label: 'Requested By', refTarget: 'user' },
  { key: 'assigned_to', label: 'Assigned To', refTarget: 'user' },
  { key: 'assignment_group', label: 'Assignment Group', refTarget: 'group' },
  { key: 'cmdb_ci', label: 'Configuration Item', refTarget: 'cmdb_ci' },
  { key: 'business_service', label: 'Business Service', refTarget: 'cmdb_ci' },
];

const SYSTEM_FIELDS: FieldConfig[] = [
  { key: 'sys_id', label: 'Sys ID' },
  { key: 'sys_created_on', label: 'Created' },
  { key: 'sys_updated_on', label: 'Updated' },
  { key: 'sys_created_by', label: 'Created By' },
  { key: 'sys_updated_by', label: 'Updated By' },
];

const SECTION = {
  details: 'chg-section-details',
  tasks: 'chg-section-tasks',
  system: 'chg-section-system',
  attachments: 'chg-section-attachments',
  comments: 'chg-section-comments',
  activity: 'chg-section-activity',
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

export function ChangeDetailPage() {
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

  const { data: changeTasksData, isLoading: changeTasksLoading } = useQuery({
    queryKey: ['records', CHANGE_TASKS_RESOURCE, 'change_request', sysId],
    queryFn: () => api.listRecords(CHANGE_TASKS_RESOURCE, { query: `change_request=${sysId}` }),
    enabled: !!sysId,
  });
  const changeTasks = useMemo(() => changeTasksData?.records ?? [], [changeTasksData]);

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
        id: SECTION.tasks,
        title: 'Change Tasks',
        icon: <FieldsIcon size={14} />,
        accent: 'info',
        count: changeTasksLoading ? '…' : changeTasks.length,
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
    changeTasks.length,
    changeTasksLoading,
    comments.length,
    permissions?.comment,
    permissions?.read,
    permissions?.write,
    sysId,
  ]);

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Change Requests', to: LIST_PATH },
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
                        id={`chg-${field.key}`}
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
                      <label htmlFor={`chg-${field.key}`}>{field.label}</label>
                      {field.type === 'select-state' ? (
                        <OFSelect
                          id={`chg-${field.key}`}
                          value={form[field.key] ?? ''}
                          onChange={(value) => setForm({ ...form, [field.key]: value as string })}
                          options={stateOptionsFor(RESOURCE)}
                        />
                      ) : field.type === 'textarea' ? (
                        <textarea
                          id={`chg-${field.key}`}
                          rows={3}
                          value={form[field.key] ?? ''}
                          onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        />
                      ) : (
                        <input
                          id={`chg-${field.key}`}
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
            id={SECTION.tasks}
            title="Change Tasks"
            icon={<FieldsIcon size={14} />}
            accent="info"
            basePath={CHANGE_TASKS_LIST_PATH}
            resource={CHANGE_TASKS_RESOURCE}
            records={changeTasks}
            isLoading={changeTasksLoading}
            emptyMessage="No change tasks linked to this change yet"
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
                  id={`chg-${field.key}`}
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
