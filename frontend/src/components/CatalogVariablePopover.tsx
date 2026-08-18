import { FormEvent, useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type CatalogVariable } from '../api/client';
import { Portal } from './Portal';
import { OFSelect } from './OFSelect';
import { TableTreeSelect } from './TableTreeSelect';
import { FieldTooltip } from './FieldTooltip';
import { ReferenceFilterBuilder } from './ReferenceFilterBuilder';
import { parseFilterRows, serializeFilterRows, type FilterRow } from './filterBuilderUtils';
import '../pages/CatalogPages.css';
import './Layout.css';

const VARIABLE_TYPES = [
  'string',
  'text_area',
  'integer',
  'boolean',
  'select_box',
  'multi_select',
  'reference',
  'date',
  'email',
  'url',
];

type VariableForm = {
  name: string;
  question_text: string;
  type: string;
  mandatory: boolean;
  order: number;
  choice_list_text: string;
  help_text: string;
  reference_table: string;
  reference_display_field: string;
  filter_rows: FilterRow[];
};

const emptyForm = (): VariableForm => ({
  name: '',
  question_text: '',
  type: 'string',
  mandatory: false,
  order: 100,
  choice_list_text: '',
  help_text: '',
  reference_table: '',
  reference_display_field: '',
  filter_rows: [],
});

function parseChoiceList(text: string): { value: string; label: string }[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [value, ...rest] = line.split('|');
      const label = rest.join('|').trim() || value.trim();
      return { value: value.trim(), label };
    });
}

function formatChoiceList(choices: { value: string; label: string }[] | undefined): string {
  if (!choices?.length) return '';
  return choices
    .map((choice) =>
      choice.label && choice.label !== choice.value
        ? `${choice.value}|${choice.label}`
        : choice.value,
    )
    .join('\n');
}

function variableToForm(variable: CatalogVariable): VariableForm {
  return {
    name: variable.name || '',
    question_text: variable.question_text || '',
    type: variable.type || 'string',
    mandatory: Boolean(variable.mandatory),
    order: variable.order ?? 100,
    choice_list_text: formatChoiceList(variable.choice_list),
    help_text: variable.help_text || '',
    reference_table: variable.reference_table || '',
    reference_display_field: variable.reference_display_field || '',
    filter_rows: parseFilterRows(variable.reference_filter),
  };
}

function toPayload(form: VariableForm) {
  const isReference = form.type === 'reference';
  return {
    name: form.name,
    question_text: form.question_text,
    type: form.type,
    mandatory: form.mandatory,
    order: form.order,
    help_text: form.help_text,
    choice_list:
      form.type === 'select_box' || form.type === 'multi_select'
        ? parseChoiceList(form.choice_list_text)
        : [],
    reference_table: isReference ? form.reference_table || null : null,
    reference_filter: isReference ? serializeFilterRows(form.filter_rows) || null : null,
    reference_display_field: isReference ? form.reference_display_field || null : null,
  };
}

interface CatalogVariablePopoverProps {
  open: boolean;
  mode: 'add' | 'edit';
  itemId: string;
  variable?: CatalogVariable | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}

export function CatalogVariablePopover({
  open,
  mode,
  itemId,
  variable = null,
  onClose,
  onSaved,
}: CatalogVariablePopoverProps) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<VariableForm>(emptyForm);
  const [error, setError] = useState('');

  const tablesQuery = useQuery({
    queryKey: ['catalog-admin-tables'],
    queryFn: () => api.adminListTables(),
    enabled: open && form.type === 'reference',
  });

  const fieldsQuery = useQuery({
    queryKey: ['catalog-admin-table-fields', form.reference_table],
    queryFn: () => api.adminListTableFields(form.reference_table),
    enabled: open && form.type === 'reference' && Boolean(form.reference_table),
  });

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && variable) {
      setForm(variableToForm(variable));
    } else {
      setForm(emptyForm());
    }
    setError('');
  }, [open, mode, variable]);

  useEffect(() => {
    if (!open) return;
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open, onClose]);

  const createMutation = useMutation({
    mutationFn: () => api.adminCreateVariable(itemId, toPayload(form)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-variables', itemId] });
      onSaved('Variable created.');
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: () => api.adminUpdateVariable(itemId, variable!.sys_id, toPayload(form)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['catalog-admin-variables', itemId] });
      onSaved('Variable updated.');
      onClose();
    },
    onError: (err: Error) => setError(err.message),
  });

  if (!open) return null;

  const pending = createMutation.isPending || updateMutation.isPending;
  const title = mode === 'edit' ? 'Edit Variable' : 'Add Variable';
  const tables = tablesQuery.data?.result || [];
  const fields = fieldsQuery.data?.result || [];

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.name.trim()) {
      setError('Field name is required');
      return;
    }
    if (form.type === 'reference' && !form.reference_table.trim()) {
      setError('Reference table is required');
      return;
    }
    if (mode === 'edit') {
      updateMutation.mutate();
    } else {
      createMutation.mutate();
    }
  }

  return (
    <Portal>
      <div className="share-popover-overlay" role="presentation" onClick={onClose}>
        <div
          className="share-popover catalog-form-popover catalog-form-popover-wide"
          role="dialog"
          aria-modal="true"
          aria-label={title}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="share-popover-header">
            <h2>{title}</h2>
            <button
              type="button"
              className="share-popover-close"
              aria-label="Close"
              onClick={onClose}
            >
              ×
            </button>
          </div>

          <form onSubmit={onSubmit} className="catalog-builder-form">
            <div className="catalog-form-grid">
              <div className="form-group">
                <label htmlFor="popover-var-name">Field Name</label>
                <input
                  id="popover-var-name"
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="popover-var-label">Display Label</label>
                <input
                  id="popover-var-label"
                  value={form.question_text}
                  onChange={(e) => setForm((p) => ({ ...p, question_text: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="popover-var-type">Type</label>
                <OFSelect
                  id="popover-var-type"
                  value={form.type}
                  onChange={(value) => {
                    const type = value as string;
                    setForm((p) => ({
                      ...p,
                      type,
                      filter_rows:
                        type === 'reference' && !p.filter_rows.length
                          ? []
                          : type === 'reference'
                            ? p.filter_rows
                            : [],
                    }));
                  }}
                  options={VARIABLE_TYPES.map((type) => ({ value: type, label: type }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="popover-var-order">Order</label>
                <input
                  id="popover-var-order"
                  type="number"
                  value={form.order}
                  onChange={(e) => setForm((p) => ({ ...p, order: Number(e.target.value) || 100 }))}
                />
              </div>
              {(form.type === 'select_box' || form.type === 'multi_select') && (
                <div className="form-group catalog-form-span">
                  <label htmlFor="popover-var-choices">Choices (one per line: value|label)</label>
                  <textarea
                    id="popover-var-choices"
                    className="code-block"
                    rows={4}
                    value={form.choice_list_text}
                    onChange={(e) => setForm((p) => ({ ...p, choice_list_text: e.target.value }))}
                    placeholder={'rhel_10|RHEL 10\nrhel_9|RHEL 9'}
                  />
                </div>
              )}
              {form.type === 'reference' && (
                <>
                  <div className="form-group catalog-form-span">
                    <label htmlFor="popover-var-ref-table">Reference Table</label>
                    <TableTreeSelect
                      id="popover-var-ref-table"
                      tables={tables}
                      value={form.reference_table}
                      onChange={(nextTable) => {
                        setForm((p) => ({
                          ...p,
                          reference_table: nextTable,
                          filter_rows: nextTable === p.reference_table ? p.filter_rows : [],
                          reference_display_field:
                            nextTable === p.reference_table ? p.reference_display_field : '',
                        }));
                      }}
                    />
                    {tablesQuery.isLoading ? (
                      <p className="catalog-help-text">Loading tables…</p>
                    ) : null}
                  </div>
                  <div className="form-group catalog-form-span">
                    <span className="field-label-with-tooltip">
                      <label htmlFor="popover-var-ref-display-field">Display Property</label>
                      <FieldTooltip ariaLabel="Display Property help">
                        The property shown to shoppers and sent as the resolved value in webhooks.
                        Defaults to "name" when left blank.
                      </FieldTooltip>
                    </span>
                    <OFSelect
                      id="popover-var-ref-display-field"
                      autocomplete
                      disabled={!form.reference_table}
                      placeholder="name (default)"
                      value={form.reference_display_field}
                      onChange={(value) =>
                        setForm((p) => ({ ...p, reference_display_field: value as string }))
                      }
                      options={fields.map((field) => ({ value: field.name, label: field.name }))}
                    />
                    {fieldsQuery.isLoading ? (
                      <p className="catalog-help-text">Loading fields…</p>
                    ) : null}
                  </div>
                  <div className="form-group catalog-form-span">
                    <label>Filters</label>
                    <ReferenceFilterBuilder
                      table={form.reference_table}
                      rows={form.filter_rows}
                      onChange={(filter_rows) => setForm((p) => ({ ...p, filter_rows }))}
                      disabled={pending}
                    />
                  </div>
                </>
              )}
              <div className="form-group catalog-form-span">
                <div className="form-check">
                  <input
                    id="popover-var-mandatory"
                    type="checkbox"
                    checked={form.mandatory}
                    onChange={(e) => setForm((p) => ({ ...p, mandatory: e.target.checked }))}
                  />
                  <label htmlFor="popover-var-mandatory">Mandatory</label>
                </div>
              </div>
            </div>

            {error ? <p className="error">{error}</p> : null}

            <div className="catalog-form-actions">
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={pending}>
                {pending ? 'Saving…' : mode === 'edit' ? 'Save' : 'Add'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Portal>
  );
}
