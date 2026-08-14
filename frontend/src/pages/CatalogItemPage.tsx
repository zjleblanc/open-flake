import { FormEvent, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, type CatalogCondition, type CatalogVariable } from '../api/client';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { FieldTooltip } from '../components/FieldTooltip';
import { ReferenceSelect } from '../components/ReferenceSelect';
import { usePageHeader } from '../components/PageHeaderContext';
import { useAuth } from '../auth/AuthContext';
import './CatalogPages.css';

function evaluateCondition(condition: CatalogCondition, dependsValue: string | undefined): boolean {
  const current = dependsValue ?? '';
  switch (condition.operator) {
    case '=':
      return current === (condition.value || '');
    case '!=':
      return current !== (condition.value || '');
    case 'IN': {
      const allowed = (condition.value || '')
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean);
      return allowed.includes(current);
    }
    case 'NOT_IN': {
      const allowed = (condition.value || '')
        .split(',')
        .map((p) => p.trim())
        .filter(Boolean);
      return !allowed.includes(current);
    }
    case 'EMPTY':
      return current === '';
    case 'NOT_EMPTY':
      return current !== '';
    default:
      return false;
  }
}

function buildDependsOn(
  variable: CatalogVariable,
  conditions: CatalogCondition[],
  variablesById: Record<string, CatalogVariable>,
  values: Record<string, string>,
): string {
  const filterRules = conditions.filter(
    (c) => c.variable === variable.sys_id && c.condition_type === 'filter' && c.active,
  );
  if (!filterRules.length) return '';
  const pairs: string[] = [];
  for (const rule of filterRules) {
    const depends = variablesById[rule.depends_on];
    if (!depends) continue;
    const value = values[depends.name] ?? depends.default_value ?? '';
    pairs.push(`${depends.name}=${value}`);
  }
  return pairs.join('&');
}

export function CatalogItemPage() {
  const { itemId = '' } = useParams();
  const { hasPermission } = useAuth();
  const canAdmin = hasPermission('records.*.write');
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState<{ number: string; sysId: string } | null>(null);

  const {
    data,
    isLoading,
    error: loadError,
  } = useQuery({
    queryKey: ['catalog-item', itemId],
    queryFn: () => api.getCatalogItem(itemId),
    enabled: Boolean(itemId),
  });

  const item = data?.result;
  const variables = useMemo(() => item?.variables ?? [], [item?.variables]);
  const conditions = useMemo(() => item?.conditions ?? [], [item?.conditions]);
  const variablesById = useMemo(
    () => Object.fromEntries(variables.map((v) => [v.sys_id, v])),
    [variables],
  );

  const visibleVariables = useMemo(() => {
    return variables
      .slice()
      .sort((a, b) => a.order - b.order)
      .filter((variable) => {
        if (!variable.active) return false;
        const visibilityRules = conditions.filter(
          (c) => c.variable === variable.sys_id && c.condition_type === 'visibility' && c.active,
        );
        if (visibilityRules.length === 0) return !variable.hidden;
        return visibilityRules.some((rule) => {
          const depends = variablesById[rule.depends_on];
          const dependsValue = depends ? values[depends.name] : undefined;
          return evaluateCondition(rule, dependsValue);
        });
      });
  }, [variables, conditions, values, variablesById]);

  const isMandatory = (variable: CatalogVariable) => {
    const mandatoryRules = conditions.filter(
      (c) => c.variable === variable.sys_id && c.condition_type === 'mandatory' && c.active,
    );
    if (mandatoryRules.length === 0) return variable.mandatory;
    return mandatoryRules.some((rule) => {
      const depends = variablesById[rule.depends_on];
      const dependsValue = depends ? values[depends.name] : undefined;
      return evaluateCondition(rule, dependsValue);
    });
  };

  const headerActions = useMemo(
    () =>
      canAdmin ? (
        <Link to={`/catalog/admin/${itemId}`} className="btn btn-primary">
          Edit
        </Link>
      ) : null,
    [canAdmin, itemId],
  );

  usePageHeader({
    breadcrumbs: [
      { label: 'Service Catalog', to: '/catalog' },
      { label: item?.name || 'Catalog Item' },
    ],
    actions: headerActions,
  });

  const orderMutation = useMutation({
    mutationFn: () =>
      api.orderCatalogItem(itemId, {
        variables: Object.fromEntries(
          visibleVariables.map((v) => [v.name, values[v.name] ?? v.default_value ?? '']),
        ),
      }),
    onSuccess: (res) => {
      const result = res.result as {
        request_id?: string;
        request_number?: string;
        request?: { number?: string; sys_id?: string };
      };
      const number = result.request_number || result.request?.number || '';
      const sysId = result.request_id || result.request?.sys_id || '';
      setSuccess({ number, sysId });
      setError('');
    },
    onError: (err: Error) => {
      setError(err.message);
      setSuccess(null);
    },
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    for (const variable of visibleVariables) {
      if (!isMandatory(variable)) continue;
      const value = (values[variable.name] ?? variable.default_value ?? '').trim();
      if (!value) {
        setError(`${variable.question_text || variable.name} is required`);
        return;
      }
    }
    orderMutation.mutate();
  }

  if (isLoading) return <p className="empty-state">Loading item…</p>;
  if (loadError) return <p className="error">{(loadError as Error).message}</p>;
  if (!item) return <p className="error">Catalog item not found</p>;

  return (
    <div className="catalog-item-page">
      <section className="panel catalog-item-hero">
        <h2>{item.name}</h2>
        <p className="catalog-item-short">{item.short_description}</p>
        {item.description ? <MarkdownRenderer content={item.description} /> : null}
      </section>

      <section className="panel">
        <h3>Order Form</h3>
        <form onSubmit={onSubmit} className="catalog-order-form">
          {visibleVariables.map((variable) => (
            <div className="form-group" key={variable.sys_id}>
              {variable.help_text ? (
                <span className="field-label-with-tooltip">
                  <label htmlFor={`var-${variable.name}`}>
                    {variable.question_text || variable.name}
                    {isMandatory(variable) ? ' *' : ''}
                  </label>
                  <FieldTooltip ariaLabel={`${variable.question_text || variable.name} help`} rich>
                    {variable.help_text}
                  </FieldTooltip>
                </span>
              ) : (
                <label htmlFor={`var-${variable.name}`}>
                  {variable.question_text || variable.name}
                  {isMandatory(variable) ? ' *' : ''}
                </label>
              )}
              {variable.type === 'text_area' ? (
                <textarea
                  id={`var-${variable.name}`}
                  value={values[variable.name] ?? variable.default_value ?? ''}
                  readOnly={variable.read_only}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [variable.name]: e.target.value }))
                  }
                  rows={4}
                />
              ) : variable.type === 'select_box' ? (
                <select
                  id={`var-${variable.name}`}
                  value={values[variable.name] ?? variable.default_value ?? ''}
                  disabled={variable.read_only}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [variable.name]: e.target.value }))
                  }
                >
                  <option value="">Select…</option>
                  {(variable.choice_list || []).map((choice) => (
                    <option key={choice.value} value={choice.value}>
                      {choice.label || choice.value}
                    </option>
                  ))}
                </select>
              ) : variable.type === 'boolean' ? (
                <input
                  id={`var-${variable.name}`}
                  type="checkbox"
                  checked={(values[variable.name] ?? variable.default_value ?? '') === 'true'}
                  disabled={variable.read_only}
                  onChange={(e) =>
                    setValues((prev) => ({
                      ...prev,
                      [variable.name]: e.target.checked ? 'true' : 'false',
                    }))
                  }
                />
              ) : variable.type === 'reference' ? (
                <ReferenceSelect
                  id={`var-${variable.name}`}
                  itemId={itemId}
                  varName={variable.name}
                  value={values[variable.name] ?? variable.default_value ?? ''}
                  dependsOn={buildDependsOn(variable, conditions, variablesById, values)}
                  disabled={variable.read_only}
                  onChange={(val) => setValues((prev) => ({ ...prev, [variable.name]: val }))}
                />
              ) : (
                <input
                  id={`var-${variable.name}`}
                  type={
                    variable.type === 'email'
                      ? 'email'
                      : variable.type === 'url'
                        ? 'url'
                        : variable.type === 'date'
                          ? 'date'
                          : variable.type === 'integer'
                            ? 'number'
                            : 'text'
                  }
                  value={values[variable.name] ?? variable.default_value ?? ''}
                  readOnly={variable.read_only}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [variable.name]: e.target.value }))
                  }
                />
              )}
            </div>
          ))}

          {error ? <p className="error">{error}</p> : null}
          {success ? (
            <p className="alert alert-success">
              Request{' '}
              {success.sysId ? (
                <Link to={`/requests/${success.sysId}`}>{success.number}</Link>
              ) : (
                success.number
              )}{' '}
              created successfully.
            </p>
          ) : null}

          <button type="submit" className="btn btn-primary" disabled={orderMutation.isPending}>
            {orderMutation.isPending ? 'Submitting…' : 'Order Now'}
          </button>
        </form>
      </section>
    </div>
  );
}
