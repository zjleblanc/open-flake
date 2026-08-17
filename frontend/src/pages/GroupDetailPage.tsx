import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import {
  DetailFieldGroup,
  ReadOnlyFieldInput,
  ToggleSwitch,
} from '../components/DetailFieldControls';
import { DetailSectionNav, type DetailSectionNavItem } from '../components/DetailSectionNav';
import { ExpandableDetailSection } from '../components/ExpandableDetailSection';
import { GovernanceIcon, OverviewIcon, SystemIcon } from '../components/DetailIcons';
import { usePageHeader } from '../components/PageHeaderContext';
import { RecordDeleteButton } from '../components/RecordDeleteButton';
import { OFSelect } from '../components/OFSelect';
import { referenceHref, refSysId } from '../utils/referenceFields';
import '../components/Layout.css';

const RESOURCE = 'groups';
const LIST_PATH = '/access/groups';

interface FormState {
  name: string;
  description: string;
  type: string;
  email: string;
  owner: string;
  manager: string;
  parent: string;
  active: string;
}

const SECTION = {
  details: 'group-section-details',
  governance: 'group-section-governance',
  system: 'group-section-system',
} as const;

function buildForm(data: Record<string, string>): FormState {
  return {
    name: data.name || '',
    description: data.description || '',
    type: data.type || '',
    email: data.email || '',
    owner: refSysId(data.owner),
    manager: refSysId(data.manager),
    parent: refSysId(data.parent),
    active: data.active === 'false' ? 'false' : 'true',
  };
}

function formsEqual(a: FormState, b: FormState): boolean {
  return (Object.keys(a) as (keyof FormState)[]).every((key) => a[key] === b[key]);
}

export function GroupDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('groups.write');
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['record', RESOURCE, sysId],
    queryFn: () => api.getRecord(RESOURCE, sysId!),
    enabled: !!sysId,
  });

  const { data: usersData } = useQuery({
    queryKey: ['records', 'users'],
    queryFn: () => api.listRecords('users'),
    enabled: canWrite,
  });

  const { data: groupsData } = useQuery({
    queryKey: ['records', 'groups'],
    queryFn: () => api.listRecords('groups'),
    enabled: canWrite,
  });

  useEffect(() => {
    if (data) setForm(buildForm(data));
  }, [data]);

  const savedForm = useMemo(() => (data ? buildForm(data) : null), [data]);
  const isDirty = !!form && !!savedForm && !formsEqual(form, savedForm);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateRecord(RESOURCE, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', RESOURCE, sysId] });
      queryClient.invalidateQueries({ queryKey: ['records', 'groups'] });
    },
  });

  const recordTitle = data?.name || data?.sys_id || 'Loading…';
  const userOptions = (usersData?.records || []).map((u) => ({
    value: u.sys_id,
    label: u.user_name,
  }));
  const groupOptions = (groupsData?.records || [])
    .filter((g) => g.sys_id !== sysId)
    .map((g) => ({ value: g.sys_id, label: g.name }));

  const sectionNavItems = useMemo(
    (): DetailSectionNavItem[] => [
      { id: SECTION.details, title: 'Details', icon: <OverviewIcon size={14} />, accent: 'accent' },
      {
        id: SECTION.governance,
        title: 'Governance',
        icon: <GovernanceIcon size={14} />,
        accent: 'info',
      },
      { id: SECTION.system, title: 'System', icon: <SystemIcon size={14} />, accent: 'primary' },
    ],
    [],
  );

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Groups', to: LIST_PATH },
      { label: isLoading || !data ? 'Loading…' : recordTitle },
    ],
    [isLoading, data, recordTitle],
  );
  const headerActions = useMemo(
    () =>
      !isLoading && data && sysId && canWrite ? (
        <RecordDeleteButton
          resource={RESOURCE}
          sysId={sysId}
          recordLabel={recordTitle}
          listPath={LIST_PATH}
        />
      ) : undefined,
    [isLoading, data, sysId, canWrite, recordTitle],
  );

  usePageHeader({ breadcrumbs: headerBreadcrumbs, actions: headerActions });

  if (isLoading || !data || !form) {
    return <p className="empty-state">Loading…</p>;
  }

  const referenceField = (
    key: 'owner' | 'manager' | 'parent',
    label: string,
    target: 'user' | 'group',
    options: { value: string; label: string }[],
  ) => {
    const sysIdValue = refSysId(data[key]);
    if (canWrite) {
      return (
        <div className="form-group" key={key} style={{ marginBottom: 0 }}>
          <label htmlFor={`group-${key}`}>{label}</label>
          <OFSelect
            id={`group-${key}`}
            autocomplete
            placeholder="None"
            value={form[key]}
            onChange={(value) => setForm({ ...form, [key]: value as string })}
            options={options}
          />
        </div>
      );
    }
    return (
      <ReadOnlyFieldInput
        key={key}
        id={`group-${key}`}
        label={label}
        value={data[`${key}_display_value`] || sysIdValue}
        href={sysIdValue ? referenceHref(target, sysIdValue) : undefined}
      />
    );
  };

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
            <DetailFieldGroup>
              {(
                [
                  { key: 'name', label: 'Name' },
                  { key: 'description', label: 'Description' },
                  { key: 'type', label: 'Type' },
                  { key: 'email', label: 'Email' },
                ] as const
              ).map((field) =>
                canWrite ? (
                  <div className="form-group" key={field.key} style={{ marginBottom: 0 }}>
                    <label htmlFor={`group-${field.key}`}>{field.label}</label>
                    <input
                      id={`group-${field.key}`}
                      type="text"
                      value={form[field.key]}
                      onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    />
                  </div>
                ) : (
                  <ReadOnlyFieldInput
                    key={field.key}
                    id={`group-${field.key}`}
                    label={field.label}
                    value={data[field.key]}
                  />
                ),
              )}
              {canWrite && (
                <ToggleSwitch
                  id="group-active"
                  checked={form.active === 'true'}
                  onChange={(checked) => setForm({ ...form, active: checked ? 'true' : 'false' })}
                  label="Active"
                />
              )}
            </DetailFieldGroup>

            {canWrite && (
              <div style={{ marginTop: '1.25rem' }}>
                <button
                  className="btn btn-primary"
                  onClick={() => form && updateMutation.mutate({ ...form })}
                  disabled={!isDirty || updateMutation.isPending}
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            )}
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.governance}
            title="Governance"
            icon={<GovernanceIcon size={14} />}
            accent="info"
          >
            <DetailFieldGroup>
              {referenceField('owner', 'Owner', 'user', userOptions)}
              {referenceField('manager', 'Manager', 'user', userOptions)}
              {referenceField('parent', 'Parent Group', 'group', groupOptions)}
            </DetailFieldGroup>
          </ExpandableDetailSection>

          <ExpandableDetailSection
            id={SECTION.system}
            title="System"
            icon={<SystemIcon size={14} />}
            accent="primary"
          >
            <DetailFieldGroup>
              {(
                [
                  { key: 'sys_id', label: 'Sys ID' },
                  { key: 'sys_created_on', label: 'Created' },
                  { key: 'sys_updated_on', label: 'Updated' },
                  { key: 'sys_created_by', label: 'Created By' },
                  { key: 'sys_updated_by', label: 'Updated By' },
                ] as const
              ).map((field) => (
                <ReadOnlyFieldInput
                  key={field.key}
                  id={`group-${field.key}`}
                  fieldKey={field.key}
                  label={field.label}
                  value={data[field.key]}
                />
              ))}
            </DetailFieldGroup>
          </ExpandableDetailSection>
        </div>
      </div>

      <DetailSectionNav sections={sectionNavItems} />
    </div>
  );
}
