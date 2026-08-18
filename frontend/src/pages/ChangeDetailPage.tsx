import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api, getRecordPermissions, stateBadge, stateLabel, stateOptionsFor } from '../api/client';
import { DetailFieldGroup, ReadOnlyFieldInput } from '../components/DetailFieldControls';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import { ActivityIcon, HierarchyIcon, PropertiesIcon, SystemIcon } from '../components/DetailIcons';
import { EmptyValue } from '../components/EmptyValue';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { usePageHeader } from '../components/PageHeaderContext';
import { RecordActivityFeed } from '../components/RecordActivityFeed';
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
  system: 'chg-section-system',
  general: 'chg-section-general',
  references: 'chg-section-references',
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
      queryClient.invalidateQueries({ queryKey: ['activity', RESOURCE, sysId] });
    },
  });

  const recordTitle = data?.number || data?.sys_id || 'Loading…';
  const editableFields = canWrite ? EDITABLE_FIELDS : [];
  const displayedLockedFields = canWrite ? LOCKED_FIELDS : [...EDITABLE_FIELDS, ...LOCKED_FIELDS];
  const showEditableDivider = displayedLockedFields.length > 0 && editableFields.length > 0;

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

    items.push({
      id: SECTION.references,
      title: 'References',
      icon: <HierarchyIcon size={14} />,
      accent: 'info',
      count: changeTasksLoading ? '…' : changeTasks.length,
    });

    return items;
  }, [changeTasks.length, changeTasksLoading, permissions?.read, sysId]);

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

          <ExpandableDetailSection
            id={SECTION.general}
            title="General"
            icon={<PropertiesIcon size={14} />}
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

          {sysId && permissions?.read && (
            <RecordActivityFeed
              resource={RESOURCE}
              sysId={sysId}
              sectionId={SECTION.activity}
              fieldLabels={FIELD_LABELS}
              canComment={!!(permissions?.comment || permissions?.write)}
              canManageAttachments={!!(permissions?.write || permissions?.delete)}
            />
          )}

          <RelatedRecordsSection
            id={SECTION.references}
            icon={<HierarchyIcon size={14} />}
            accent="info"
            basePath={CHANGE_TASKS_LIST_PATH}
            resource={CHANGE_TASKS_RESOURCE}
            typeLabel="Change Task"
            records={changeTasks}
            isLoading={changeTasksLoading}
            emptyMessage="No referenced records linked to this change yet"
          />
        </div>
      </div>

      <DetailSectionNav sections={sectionNavItems} />
    </div>
  );
}
