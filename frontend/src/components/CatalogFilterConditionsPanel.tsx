import { FormEvent, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type CatalogCondition, type CatalogVariable } from '../api/client';
import { ReferenceFilterBuilder } from './ReferenceFilterBuilder';
import { parseFilterRows, serializeFilterRows, type FilterRow } from './filterBuilderUtils';
import { ConfirmDialog } from './ConfirmDialog';
import { OFSelect } from './OFSelect';
import { EditIcon, DeleteIcon } from './DetailIcons';

const CONDITION_OPERATORS = ['=', '!=', 'IN', 'NOT_IN', 'EMPTY', 'NOT_EMPTY'];

interface CatalogFilterConditionsPanelProps {
  itemId: string;
  variables: CatalogVariable[];
  onToast: (message: string, type?: 'success' | 'error') => void;
}

type ConditionForm = {
  variableId: string;
  dependsOn: string;
  operator: string;
  value: string;
  filterRows: FilterRow[];
};

const emptyConditionForm = (variableId = ''): ConditionForm => ({
  variableId,
  dependsOn: '',
  operator: '=',
  value: '',
  filterRows: [],
});

export function CatalogFilterConditionsPanel({
  itemId,
  variables,
  onToast,
}: CatalogFilterConditionsPanelProps) {
  const queryClient = useQueryClient();
  const referenceVariables = variables.filter((v) => v.type === 'reference');
  const [selectedVarId, setSelectedVarId] = useState('');
  const [form, setForm] = useState<ConditionForm>(emptyConditionForm());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);

  useEffect(() => {
    if (!selectedVarId && referenceVariables.length) {
      setSelectedVarId(referenceVariables[0].sys_id);
    } else if (selectedVarId && !referenceVariables.some((v) => v.sys_id === selectedVarId)) {
      setSelectedVarId(referenceVariables[0]?.sys_id || '');
    }
  }, [referenceVariables, selectedVarId]);

  const selectedVariable = referenceVariables.find((v) => v.sys_id === selectedVarId);

  const conditionsQuery = useQuery({
    queryKey: ['catalog-admin-conditions', itemId, selectedVarId],
    queryFn: () => api.adminListConditions(itemId, selectedVarId),
    enabled: Boolean(itemId && selectedVarId),
  });

  const conditions = (conditionsQuery.data?.result || []).filter(
    (c) => c.condition_type === 'filter',
  );

  const createMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      api.adminCreateCondition(itemId, selectedVarId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['catalog-admin-conditions', itemId, selectedVarId],
      });
      setForm(emptyConditionForm(selectedVarId));
      setEditingId(null);
      setError('');
      onToast('Rule created.');
    },
    onError: (err: Error) => setError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ condId, payload }: { condId: string; payload: Record<string, unknown> }) =>
      api.adminUpdateCondition(itemId, selectedVarId, condId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['catalog-admin-conditions', itemId, selectedVarId],
      });
      setForm(emptyConditionForm(selectedVarId));
      setEditingId(null);
      setError('');
      onToast('Rule updated.');
    },
    onError: (err: Error) => setError(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (condId: string) => api.adminDeleteCondition(itemId, selectedVarId, condId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['catalog-admin-conditions', itemId, selectedVarId],
      });
      setPendingDelete(null);
      onToast('Rule deleted.');
    },
    onError: (err: Error) => onToast(err.message, 'error'),
  });

  if (referenceVariables.length === 0) {
    return null;
  }

  function startEdit(condition: CatalogCondition) {
    setEditingId(condition.sys_id);
    setForm({
      variableId: selectedVarId,
      dependsOn: condition.depends_on,
      operator: condition.operator || '=',
      value: condition.value || '',
      filterRows: parseFilterRows(condition.filter_override),
    });
    setError('');
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.dependsOn) {
      setError('Depends-on field is required');
      return;
    }
    const filterOverride = serializeFilterRows(form.filterRows);
    if (!filterOverride) {
      setError('At least one filter override row is required');
      return;
    }
    const payload = {
      condition_type: 'filter',
      depends_on: form.dependsOn,
      operator: form.operator,
      value: form.operator === 'EMPTY' || form.operator === 'NOT_EMPTY' ? null : form.value,
      filter_override: filterOverride,
      active: true,
    };
    if (editingId) {
      updateMutation.mutate({ condId: editingId, payload });
    } else {
      createMutation.mutate(payload);
    }
  }

  const otherVariables = variables.filter((v) => v.sys_id !== selectedVarId);
  const pending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="catalog-filter-conditions-panel">
      <div className="section-header-row">
        <div>
          <h4>Dynamic Rules</h4>
        </div>
      </div>

      <div className="form-group">
        <label htmlFor="filter-cond-variable">Reference Variable</label>
        <OFSelect
          id="filter-cond-variable"
          value={selectedVarId}
          onChange={(value) => {
            const nextVarId = value as string;
            setSelectedVarId(nextVarId);
            setEditingId(null);
            setForm(emptyConditionForm(nextVarId));
            setError('');
          }}
          options={referenceVariables.map((variable) => ({
            value: variable.sys_id,
            label: variable.reference_table
              ? `${variable.reference_table} → ${variable.name}`
              : variable.name,
          }))}
        />
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Operator</th>
            <th>Value</th>
            <th>Override Filter</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {conditions.length === 0 ? (
            <tr>
              <td colSpan={5} className="empty-state">
                No rules yet
              </td>
            </tr>
          ) : (
            conditions.map((condition) => {
              const depends = variables.find((v) => v.sys_id === condition.depends_on);
              return (
                <tr key={condition.sys_id}>
                  <td>{depends?.question_text || depends?.name || condition.depends_on}</td>
                  <td>{condition.operator}</td>
                  <td>{condition.value || '—'}</td>
                  <td>
                    <code className="code-inline">{condition.filter_override || '—'}</code>
                  </td>
                  <td className="catalog-row-actions">
                    <button
                      type="button"
                      className="btn-icon"
                      aria-label={`Edit rule for ${depends?.question_text || depends?.name || condition.depends_on}`}
                      onClick={() => startEdit(condition)}
                    >
                      <EditIcon size={14} />
                    </button>
                    <button
                      type="button"
                      className="btn-icon btn-icon-danger"
                      aria-label={`Delete rule for ${depends?.question_text || depends?.name || condition.depends_on}`}
                      onClick={() =>
                        setPendingDelete({
                          id: condition.sys_id,
                          label:
                            depends?.question_text ||
                            depends?.name ||
                            condition.depends_on ||
                            'this rule',
                        })
                      }
                    >
                      <DeleteIcon size={14} />
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>

      <form onSubmit={onSubmit} className="catalog-builder-form catalog-condition-form">
        <h4>{editingId ? 'Edit Rule' : 'Add Rule'}</h4>
        <div className="catalog-form-grid">
          <div className="form-group">
            <label htmlFor="filter-cond-depends">Depends On</label>
            <OFSelect
              id="filter-cond-depends"
              placeholder="Select field…"
              value={form.dependsOn}
              onChange={(value) => setForm((p) => ({ ...p, dependsOn: value as string }))}
              options={otherVariables.map((variable) => ({
                value: variable.sys_id,
                label: variable.question_text || variable.name,
              }))}
            />
          </div>
          <div className="form-group">
            <label htmlFor="filter-cond-operator">Operator</label>
            <OFSelect
              id="filter-cond-operator"
              value={form.operator}
              onChange={(value) => setForm((p) => ({ ...p, operator: value as string }))}
              options={CONDITION_OPERATORS.map((op) => ({ value: op, label: op }))}
            />
          </div>
          {form.operator !== 'EMPTY' && form.operator !== 'NOT_EMPTY' ? (
            <div className="form-group">
              <label htmlFor="filter-cond-value">Value</label>
              <input
                id="filter-cond-value"
                value={form.value}
                onChange={(e) => setForm((p) => ({ ...p, value: e.target.value }))}
                placeholder="Comparison value"
              />
            </div>
          ) : null}
          <div className="form-group catalog-form-span">
            <label>Filter</label>
            <ReferenceFilterBuilder
              table={selectedVariable?.reference_table || ''}
              rows={form.filterRows}
              onChange={(filterRows) => setForm((p) => ({ ...p, filterRows }))}
              disabled={pending}
            />
          </div>
        </div>
        {error ? <p className="error">{error}</p> : null}
        <div className="catalog-form-actions">
          {editingId ? (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setEditingId(null);
                setForm(emptyConditionForm(selectedVarId));
                setError('');
              }}
            >
              Cancel
            </button>
          ) : null}
          <button type="submit" className="btn btn-primary" disabled={pending}>
            {pending ? 'Saving…' : 'Save Rule'}
          </button>
        </div>
      </form>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete rule"
        message={
          pendingDelete
            ? `Are you sure you want to permanently delete the rule for "${pendingDelete.label}"? This action cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
