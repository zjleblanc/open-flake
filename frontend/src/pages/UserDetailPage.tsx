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
import { OverviewIcon, SystemIcon } from '../components/DetailIcons';
import { usePageHeader } from '../components/PageHeaderContext';
import { RecordDeleteButton } from '../components/RecordDeleteButton';
import { OFSelect } from '../components/OFSelect';
import { isReferenceDeleted, referenceHref, refSysId } from '../utils/referenceFields';
import '../components/Layout.css';

const RESOURCE = 'users';
const LIST_PATH = '/access/users';

interface FormState {
  first_name: string;
  last_name: string;
  email: string;
  department: string;
  title: string;
  manager: string;
  active: string;
}

const SECTION = {
  profile: 'user-section-profile',
  system: 'user-section-system',
} as const;

function buildForm(data: Record<string, string>): FormState {
  return {
    first_name: data.first_name || '',
    last_name: data.last_name || '',
    email: data.email || '',
    department: data.department || '',
    title: data.title || '',
    manager: refSysId(data.manager),
    active: data.active === 'false' ? 'false' : 'true',
  };
}

function formsEqual(a: FormState, b: FormState): boolean {
  return (Object.keys(a) as (keyof FormState)[]).every((key) => a[key] === b[key]);
}

export function UserDetailPage() {
  const { sysId } = useParams<{ sysId: string }>();
  const { hasPermission } = useAuth();
  const canWrite = hasPermission('users.write');
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

  useEffect(() => {
    if (data) setForm(buildForm(data));
  }, [data]);

  const savedForm = useMemo(() => (data ? buildForm(data) : null), [data]);
  const isDirty = !!form && !!savedForm && !formsEqual(form, savedForm);

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.updateRecord(RESOURCE, sysId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['record', RESOURCE, sysId] });
      queryClient.invalidateQueries({ queryKey: ['records', 'users'] });
    },
  });

  const recordTitle = data?.user_name || data?.sys_id || 'Loading…';
  const managerOptions = (usersData?.records || [])
    .filter((u) => u.sys_id !== sysId)
    .map((u) => ({ value: u.sys_id, label: u.user_name }));

  const sectionNavItems = useMemo(
    (): DetailSectionNavItem[] => [
      { id: SECTION.profile, title: 'Profile', icon: <OverviewIcon size={14} />, accent: 'accent' },
      { id: SECTION.system, title: 'System', icon: <SystemIcon size={14} />, accent: 'primary' },
    ],
    [],
  );

  const headerBreadcrumbs = useMemo(
    () => [
      { label: 'Users', to: LIST_PATH },
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

  const managerSysId = refSysId(data.manager);

  return (
    <div className="detail-page-layout">
      <div className="detail-page-main">
        <div className="detail-sections-stack">
          <ExpandableDetailSection
            id={SECTION.profile}
            title="Profile"
            icon={<OverviewIcon size={14} />}
            accent="accent"
            defaultOpen
          >
            <div className="detail-field-groups">
              <DetailFieldGroup>
                <ReadOnlyFieldInput id="user-user_name" label="Username" value={data.user_name} />
                {canWrite ? (
                  <div className="form-group" style={{ marginBottom: 0 }}>
                    <label htmlFor="user-manager">Manager</label>
                    <OFSelect
                      id="user-manager"
                      autocomplete
                      placeholder="None"
                      value={form.manager}
                      onChange={(value) => setForm({ ...form, manager: value as string })}
                      options={managerOptions}
                    />
                  </div>
                ) : (
                  <ReadOnlyFieldInput
                    id="user-manager"
                    label="Manager"
                    value={data.manager_display_value || managerSysId}
                    href={managerSysId ? referenceHref('user', managerSysId) : undefined}
                    deleted={isReferenceDeleted(data, 'manager')}
                  />
                )}
              </DetailFieldGroup>

              <DetailFieldGroup dividerTop>
                {(
                  [
                    { key: 'first_name', label: 'First Name' },
                    { key: 'last_name', label: 'Last Name' },
                    { key: 'email', label: 'Email' },
                    { key: 'department', label: 'Department' },
                    { key: 'title', label: 'Title' },
                  ] as const
                ).map((field) =>
                  canWrite ? (
                    <div className="form-group" key={field.key} style={{ marginBottom: 0 }}>
                      <label htmlFor={`user-${field.key}`}>{field.label}</label>
                      <input
                        id={`user-${field.key}`}
                        type="text"
                        value={form[field.key]}
                        onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                      />
                    </div>
                  ) : (
                    <ReadOnlyFieldInput
                      key={field.key}
                      id={`user-${field.key}`}
                      label={field.label}
                      value={data[field.key]}
                    />
                  ),
                )}
                {canWrite && (
                  <ToggleSwitch
                    id="user-active"
                    checked={form.active === 'true'}
                    onChange={(checked) => setForm({ ...form, active: checked ? 'true' : 'false' })}
                    label="Active"
                  />
                )}
              </DetailFieldGroup>
            </div>

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
                  id={`user-${field.key}`}
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
