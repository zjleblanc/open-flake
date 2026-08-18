import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, getRecordPermissions, stateBadge, stateLabel, stateOptionsFor } from '../api/client';
import { DetailFieldGroup, ReadOnlyFieldInput } from '../components/DetailFieldControls';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import {
  ActivityIcon,
  FieldsIcon,
  HierarchyIcon,
  LockIcon,
  PropertiesIcon,
  SystemIcon,
} from '../components/DetailIcons';
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

const RESOURCE = 'catalog-request-items';
const LIST_PATH = '/requested-items';

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
  { key: 'stage', label: 'Stage' },
  { key: 'approval', label: 'Approval' },
  { key: 'quantity', label: 'Quantity' },
  { key: 'price', label: 'Price' },
  { key: 'cat_item', label: 'Catalog Item', refTarget: 'sc_cat_item' },
  { key: 'opened_by', label: 'Opened By', refTarget: 'user' },
  { key: 'assignment_group', label: 'Assignment Group', refTarget: 'group' },
  { key: 'assigned_to', label: 'Assigned To', refTarget: 'user' },
  { key: 'cmdb_ci', label: 'Configuration Item', refTarget: 'cmdb_ci' },
];

const SYSTEM_FIELDS: FieldConfig[] = [
  { key: 'sys_id', label: 'Sys ID' },
  { key: 'sys_created_on', label: 'Created' },
  { key: 'sys_updated_on', label: 'Updated' },
  { key: 'sys_created_by', label: 'Created By' },
  { key: 'sys_updated_by', label: 'Updated By' },
];

const SECTION = {
  system: 'ritm-section-system',
  general: 'ritm-section-general',
  references: 'ritm-section-references',
  variables: 'ritm-section-variables',
  activity: 'ritm-section-activity',
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

interface ParentRequestFieldProps {
  reqSysId: string;
  reqNumber?: string;
}

function ParentRequestField({ reqSysId, reqNumber }: ParentRequestFieldProps) {
  return (
    <div className="form-group form-group--readonly" style={{ marginBottom: 0 }}>
      <label htmlFor="ritm-parent-request">Parent Request</label>
      <div className="readonly-input-wrap">
        {reqSysId ? (
          <Link
            id="ritm-parent-request"
            to={`/requests/${reqSysId}`}
            className="readonly-input-link"
          >
            {reqNumber || reqSysId}
          </Link>
        ) : (
          <input
            id="ritm-parent-request"
            readOnly
            className="readonly-input"
            type="text"
            value="—"
          />
        )}
        <span className="readonly-input-lock" aria-hidden="true">
          <LockIcon size={14} />
        </span>
      </div>
    </div>
  );
}

export function RequestedItemDetailPage() {
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
  const parentReqSysId = data ? refSysId(data.request) : '';

  const { data: parentReq } = useQuery({
    queryKey: ['record', 'catalog-requests', parentReqSysId],
    queryFn: () => api.getRecord('catalog-requests', parentReqSysId),
    enabled: !!parentReqSysId,
  });

  const { data: siblingsData, isLoading: siblingsLoading } = useQuery({
    queryKey: ['records', 'catalog-request-items', 'request', parentReqSysId],
    queryFn: () => api.listRecords('catalog-request-items', { query: `request=${parentReqSysId}` }),
    enabled: !!parentReqSysId,
  });
  const siblingItems = useMemo(
    () => (siblingsData?.records ?? []).filter((record) => record.sys_id !== sysId),
    [siblingsData, sysId],
  );

  const { data: variables = [], isLoading: variablesLoading } = useQuery({
    queryKey: ['record-variables', RESOURCE, sysId],
    queryFn: () => api.listRecordVariables(RESOURCE, sysId!),
    enabled: !!sysId && !!permissions?.read,
  });

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

    items.push({
      id: SECTION.variables,
      title: 'Variables',
      icon: <FieldsIcon size={14} />,
      accent: 'accent',
      count: variablesLoading ? '…' : variables.length,
    });

    if (sysId && permissions?.read) {
      items.push({
        id: SECTION.activity,
        title: 'Activity',
        icon: <ActivityIcon size={14} />,
        accent: 'primary',
      });
    }

    if (parentReqSysId) {
      items.push({
        id: SECTION.references,
        title: 'References',
        icon: <HierarchyIcon size={14} />,
        accent: 'info',
        count: siblingsLoading ? '…' : siblingItems.length,
      });
    }

    return items;
  }, [
    parentReqSysId,
    permissions?.read,
    siblingItems.length,
    siblingsLoading,
    sysId,
    variables.length,
    variablesLoading,
  ]);

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Requested Items', to: LIST_PATH },
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
                  id={`ritm-${field.key}`}
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
              <DetailFieldGroup>
                <ParentRequestField reqSysId={parentReqSysId} reqNumber={parentReq?.number} />
                {displayedLockedFields.map((field) => {
                  const fieldSysId = field.refTarget ? refSysId(data[field.key]) : '';
                  return (
                    <ReadOnlyFieldInput
                      key={field.key}
                      id={`ritm-${field.key}`}
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
                      <label htmlFor={`ritm-${field.key}`}>{field.label}</label>
                      {field.type === 'select-state' ? (
                        <OFSelect
                          id={`ritm-${field.key}`}
                          value={form[field.key] ?? ''}
                          onChange={(value) => setForm({ ...form, [field.key]: value as string })}
                          options={stateOptionsFor(RESOURCE)}
                        />
                      ) : field.type === 'textarea' ? (
                        <textarea
                          id={`ritm-${field.key}`}
                          rows={3}
                          value={form[field.key] ?? ''}
                          onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        />
                      ) : (
                        <input
                          id={`ritm-${field.key}`}
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

          <ExpandableDetailSection
            id={SECTION.variables}
            title="Variables"
            icon={<FieldsIcon size={14} />}
            accent="accent"
            count={variablesLoading ? '…' : variables.length}
          >
            {variablesLoading && <p className="empty-state">Loading variables…</p>}
            {!variablesLoading && variables.length === 0 && (
              <p className="empty-state">No variables were submitted for this item</p>
            )}
            {!variablesLoading && variables.length > 0 && (
              <DetailFieldGroup>
                {variables.map((variable) => (
                  <ReadOnlyFieldInput
                    key={variable.sys_id}
                    id={`ritm-variable-${variable.sys_id}`}
                    label={variable.question_text}
                    value={variable.value}
                    multiline={variable.type === 'text_area'}
                    gridColumn={variable.type === 'text_area' ? '1 / -1' : undefined}
                  />
                ))}
              </DetailFieldGroup>
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

          {parentReqSysId && (
            <RelatedRecordsSection
              id={SECTION.references}
              icon={<HierarchyIcon size={14} />}
              accent="info"
              basePath={LIST_PATH}
              resource={RESOURCE}
              typeLabel="Sibling Item"
              records={siblingItems}
              isLoading={siblingsLoading}
              emptyMessage="No other referenced records on this request"
            />
          )}
        </div>
      </div>

      <DetailSectionNav sections={sectionNavItems} />
    </div>
  );
}
