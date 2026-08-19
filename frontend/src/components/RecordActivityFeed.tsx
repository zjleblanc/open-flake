import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, stateLabel, type ActivityChange, type ActivityEntry } from '../api/client';
import { useUserPreferences } from '../settings/UserPreferencesContext';
import type { DateDisplayFormat } from '../settings/userPreferences';
import {
  formatFileSize,
  getPreviewKind,
  type AttachmentRecord,
  type PreviewKind,
} from '../utils/attachmentUtils';
import { ActivityIcon } from './DetailIcons';
import { ConfirmDialog } from './ConfirmDialog';
import { ExpandableDetailSection } from './ExpandableDetailSection';
import { JournalFieldRenderer } from './JournalFieldRenderer';

interface RecordActivityFeedProps {
  resource: string;
  sysId: string;
  sectionId?: string;
  canComment: boolean;
  canManageAttachments: boolean;
  /** Known field key -> human label overrides; falls back to a humanized snake_case key. */
  fieldLabels?: Record<string, string>;
}

type FeedEntry =
  | { kind: 'created'; id: string; user: string; timestamp: string }
  | { kind: 'update'; id: string; user: string; timestamp: string; changes: ActivityChange[] }
  | { kind: 'comment'; id: string; user: string; timestamp: string; comment: string }
  | {
      kind: 'attachment';
      id: string;
      user: string;
      timestamp: string;
      attachment: AttachmentRecord;
    };

function humanizeFieldName(key: string): string {
  return key
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function fieldLabel(key: string, fieldLabels?: Record<string, string>): string {
  return fieldLabels?.[key] || humanizeFieldName(key);
}

/**
 * Journal-style fields (ServiceNow work_notes/comments/close_notes convention) are audited
 * like any other field, but read poorly as an old -> new diff. Instead the activity feed
 * renders them as a message bubble with the note text (and a type label, except for plain
 * `comments` which read fine as an unlabeled message).
 */
const JOURNAL_FIELD_LABELS: Record<string, string | null> = {
  work_notes: 'Work Note',
  close_notes: 'Close Note',
  comments: null,
};

function isJournalField(field: string): boolean {
  return field in JOURNAL_FIELD_LABELS;
}

/**
 * Journal fields are free-text and typically edited by appending to the end, so the raw
 * `new_value` accumulates everything ever written. Show only what was actually added in
 * this update -- the text after the old value's common prefix -- so the feed reads as a
 * log of changes rather than repeating the whole note on every edit. Falls back to the
 * full new value when the edit wasn't a simple append (e.g. earlier text was rewritten).
 */
function journalChangeDelta(oldValue: string, newValue: string): string {
  if (!oldValue) return newValue;
  if (newValue.startsWith(oldValue)) {
    const added = newValue.slice(oldValue.length).trim();
    if (added) return added;
  }
  return newValue;
}

function changeValueLabel(
  field: string,
  value: string,
  resource: string,
  displayValue?: string,
): string {
  if (!value) return '—';
  if (field === 'state') return stateLabel(value, resource);
  if (displayValue) return displayValue;
  return value;
}

const RELATIVE_TIME_UNITS: { limit: number; divisor: number; unit: Intl.RelativeTimeFormatUnit }[] =
  [
    { limit: 60, divisor: 1, unit: 'second' },
    { limit: 3600, divisor: 60, unit: 'minute' },
    { limit: 86400, divisor: 3600, unit: 'hour' },
    { limit: 604800, divisor: 86400, unit: 'day' },
  ];

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

/**
 * Friendly timestamp for the activity feed: relative for recent entries (timezone-agnostic,
 * since it's just an elapsed-time delta), falling back to an absolute date/time rendered in
 * UTC or the browser's local timezone per the user's "raw"/"local" date display preference.
 */
function formatFriendlyTimestamp(timestamp: string, format: DateDisplayFormat): string {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;

  const diffSeconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));

  if (diffSeconds < 10) return 'Just now';

  for (const { limit, divisor, unit } of RELATIVE_TIME_UNITS) {
    if (diffSeconds < limit) {
      return relativeTimeFormatter.format(-Math.round(diffSeconds / divisor), unit);
    }
  }

  const useUtc = format === 'raw';
  const sameYear = date.getUTCFullYear() === new Date().getUTCFullYear();
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: sameYear ? undefined : 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: useUtc ? 'UTC' : undefined,
    timeZoneName: useUtc ? 'short' : undefined,
  });
}

/** Full timestamp shown as a tooltip so exact times remain available on hover. */
function formatExactTimestamp(timestamp: string, format: DateDisplayFormat): string {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return timestamp;
  const useUtc = format === 'raw';
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: useUtc ? 'UTC' : undefined,
  });
}

function initialsFor(user: string): string {
  const trimmed = (user || 'System').trim();
  const parts = trimmed.split(/[\s._-]+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

function toActivityEntries(entries: ActivityEntry[]): FeedEntry[] {
  return entries.map((entry) => {
    if (entry.type === 'comment') {
      return {
        kind: 'comment',
        id: entry.id,
        user: entry.user,
        timestamp: entry.timestamp,
        comment: entry.comment ?? '',
      };
    }
    if (entry.type === 'update') {
      return {
        kind: 'update',
        id: entry.id,
        user: entry.user,
        timestamp: entry.timestamp,
        changes: entry.changes ?? [],
      };
    }
    return { kind: 'created', id: entry.id, user: entry.user, timestamp: entry.timestamp };
  });
}

function toAttachmentEntries(attachments: AttachmentRecord[]): FeedEntry[] {
  return attachments.map((attachment) => ({
    kind: 'attachment',
    id: attachment.sys_id,
    user: attachment.sys_created_by || '',
    timestamp: attachment.sys_created_on,
    attachment,
  }));
}

interface AttachmentPreviewProps {
  resource: string;
  sysId: string;
  attachment: AttachmentRecord;
  previewKind: PreviewKind;
}

function AttachmentPreview({ resource, sysId, attachment, previewKind }: AttachmentPreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadPreview() {
      try {
        const blob = await api.fetchAttachmentBlob(resource, sysId, attachment.sys_id);
        if (cancelled) return;

        if (previewKind === 'text') {
          const text = await blob.text();
          if (!cancelled) {
            setTextContent(text.slice(0, 8000));
          }
          return;
        }

        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        setPreviewUrl(url);
      } catch {
        if (!cancelled) {
          setLoadError(true);
        }
      }
    }

    void loadPreview();

    return () => {
      cancelled = true;
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [resource, sysId, attachment.sys_id, previewKind]);

  if (loadError) {
    return <p className="text-muted text-sm attachment-preview-error">Preview unavailable.</p>;
  }

  if (previewKind === 'text') {
    if (textContent === null) {
      return <p className="text-muted text-sm">Loading preview…</p>;
    }
    return <pre className="attachment-text-preview">{textContent}</pre>;
  }

  if (!previewUrl) {
    return <p className="text-muted text-sm">Loading preview…</p>;
  }

  if (previewKind === 'image') {
    return (
      <img
        src={previewUrl}
        alt={attachment.file_name}
        className="attachment-image-preview"
        loading="lazy"
      />
    );
  }

  if (previewKind === 'pdf') {
    return (
      <iframe src={previewUrl} title={attachment.file_name} className="attachment-pdf-preview" />
    );
  }

  if (previewKind === 'audio') {
    return <audio controls src={previewUrl} className="attachment-media-preview" />;
  }

  if (previewKind === 'video') {
    return <video controls src={previewUrl} className="attachment-media-preview" />;
  }

  return null;
}

function ActivityChangeRow({
  change,
  resource,
  fieldLabels,
}: {
  change: ActivityChange;
  resource: string;
  fieldLabels?: Record<string, string>;
}) {
  const hasOldValue = Boolean(change.old_value);

  return (
    <li className="activity-feed-change">
      <span className="activity-feed-change-field">{fieldLabel(change.field, fieldLabels)}</span>
      <span className="activity-feed-change-values">
        {hasOldValue && (
          <>
            <span className="activity-feed-change-old">
              {changeValueLabel(change.field, change.old_value, resource, change.old_display_value)}
            </span>
            <span className="activity-feed-change-arrow" aria-hidden="true">
              →
            </span>
          </>
        )}
        <span className="activity-feed-change-new">
          {changeValueLabel(change.field, change.new_value, resource, change.new_display_value)}
        </span>
      </span>
    </li>
  );
}

export function RecordActivityFeed({
  resource,
  sysId,
  sectionId = 'record-section-activity',
  canComment,
  canManageAttachments,
  fieldLabels,
}: RecordActivityFeedProps) {
  const queryClient = useQueryClient();
  const { dateDisplayFormat } = useUserPreferences();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState('');
  const [expandedPreviewId, setExpandedPreviewId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: string; label: string } | null>(null);

  const { data: activityData, isLoading: activityLoading } = useQuery({
    queryKey: ['activity', resource, sysId],
    queryFn: () => api.listActivity(resource, sysId),
  });

  const { data: attachments = [], isLoading: attachmentsLoading } = useQuery({
    queryKey: ['attachments', resource, sysId],
    queryFn: () => api.listAttachments(resource, sysId),
  });

  const isLoading = activityLoading || attachmentsLoading;

  const feedEntries = useMemo(() => {
    const entries = [
      ...toActivityEntries(activityData?.activity ?? []),
      ...toAttachmentEntries(attachments),
    ];
    entries.sort((a, b) => (a.timestamp || '').localeCompare(b.timestamp || ''));
    return entries;
  }, [activityData, attachments]);

  const createCommentMutation = useMutation({
    mutationFn: (comment: string) => api.createComment(resource, sysId, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activity', resource, sysId] });
      setDraft('');
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAttachment(resource, sysId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attachments', resource, sysId] });
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (attachmentSysId: string) => api.deleteAttachment(resource, sysId, attachmentSysId),
    onSuccess: (_data, attachmentSysId) => {
      queryClient.invalidateQueries({ queryKey: ['attachments', resource, sysId] });
      if (expandedPreviewId === attachmentSysId) {
        setExpandedPreviewId(null);
      }
      setPendingDelete(null);
    },
  });

  async function handleDownload(attachment: AttachmentRecord) {
    const blob = await api.fetchAttachmentBlob(resource, sysId, attachment.sys_id);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = attachment.file_name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <ExpandableDetailSection
      id={sectionId}
      title="Activity"
      icon={<ActivityIcon size={14} />}
      accent="primary"
      count={isLoading ? '…' : feedEntries.length}
    >
      {isLoading && <p className="empty-state">Loading activity…</p>}
      {!isLoading && feedEntries.length === 0 && <p className="empty-state">No activity yet</p>}

      {!isLoading && feedEntries.length > 0 && (
        <ul className="activity-message-list">
          {feedEntries.map((entry) => {
            const timeLabel = entry.timestamp
              ? formatFriendlyTimestamp(entry.timestamp, dateDisplayFormat)
              : '';
            const timeTitle = entry.timestamp
              ? formatExactTimestamp(entry.timestamp, dateDisplayFormat)
              : undefined;
            const userLabel = entry.user || 'System';

            return (
              <li key={`${entry.kind}-${entry.id}`} className="activity-message">
                <span className="activity-message-avatar" aria-hidden="true">
                  {initialsFor(userLabel)}
                </span>
                <div className="activity-message-content">
                  <div className="activity-message-header">
                    <span className="activity-message-user">{userLabel}</span>
                    <span className="activity-message-time text-muted text-sm" title={timeTitle}>
                      {timeLabel}
                    </span>
                  </div>

                  {entry.kind === 'created' && (
                    <p className="activity-message-system">Record created</p>
                  )}

                  {entry.kind === 'comment' && (
                    <div className="activity-message-bubble">
                      <JournalFieldRenderer content={entry.comment} />
                    </div>
                  )}

                  {entry.kind === 'update' &&
                    (() => {
                      const journalChanges = entry.changes.filter((change) =>
                        isJournalField(change.field),
                      );
                      const regularChanges = entry.changes.filter(
                        (change) => !isJournalField(change.field),
                      );

                      return (
                        <div className="activity-update-groups">
                          {journalChanges.map((change, idx) => {
                            const journalLabel = JOURNAL_FIELD_LABELS[change.field];
                            return (
                              <div
                                className="activity-message-bubble"
                                key={`journal-${change.field}-${idx}`}
                              >
                                {journalLabel && (
                                  <span className="activity-message-journal-label">
                                    {journalLabel}
                                  </span>
                                )}
                                <JournalFieldRenderer
                                  content={journalChangeDelta(change.old_value, change.new_value)}
                                />
                              </div>
                            );
                          })}

                          {regularChanges.length > 0 && (
                            <div className="activity-message-updates">
                              <ul className="activity-feed-changes">
                                {regularChanges.map((change, idx) => (
                                  <ActivityChangeRow
                                    key={`${change.field}-${idx}`}
                                    change={change}
                                    resource={resource}
                                    fieldLabels={fieldLabels}
                                  />
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      );
                    })()}

                  {entry.kind === 'attachment' &&
                    (() => {
                      const attachment = entry.attachment;
                      const previewKind = getPreviewKind(attachment.content_type);
                      const isPreviewable = previewKind !== 'none';
                      const isExpanded = expandedPreviewId === attachment.sys_id;

                      return (
                        <div className="activity-message-attachment">
                          <p className="activity-message-attachment-title">
                            File uploaded <strong>{attachment.file_name}</strong>
                          </p>
                          <p className="text-muted text-sm" style={{ margin: '0.25rem 0 0' }}>
                            {formatFileSize(attachment.size_bytes)}
                          </p>
                          <div className="activity-message-attachment-actions">
                            {isPreviewable && (
                              <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                onClick={() =>
                                  setExpandedPreviewId(isExpanded ? null : attachment.sys_id)
                                }
                              >
                                {isExpanded ? 'Hide Preview' : 'Preview'}
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleDownload(attachment)}
                            >
                              Download
                            </button>
                            {canManageAttachments && (
                              <button
                                type="button"
                                className="btn btn-danger btn-sm"
                                disabled={deleteMutation.isPending}
                                onClick={() =>
                                  setPendingDelete({
                                    id: attachment.sys_id,
                                    label: attachment.file_name,
                                  })
                                }
                              >
                                Delete
                              </button>
                            )}
                          </div>

                          {isPreviewable && isExpanded && (
                            <div className="attachment-preview-panel">
                              <AttachmentPreview
                                resource={resource}
                                sysId={sysId}
                                attachment={attachment}
                                previewKind={previewKind}
                              />
                            </div>
                          )}
                        </div>
                      );
                    })()}
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {(canComment || canManageAttachments) && (
        <div className="activity-composer">
          {canComment && (
            <div
              className="form-group"
              style={{ marginBottom: canManageAttachments ? '0.75rem' : 0 }}
            >
              <label htmlFor={`activity-draft-${sysId}`}>Add comment</label>
              <textarea
                id={`activity-draft-${sysId}`}
                rows={3}
                placeholder="Write a comment…"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
              />
            </div>
          )}

          <div className="activity-composer-actions">
            {canManageAttachments && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  id={`activity-attachment-upload-${sysId}`}
                  className="attachment-file-input"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      uploadMutation.mutate(file);
                    }
                  }}
                />
                <button
                  type="button"
                  className="btn btn-secondary"
                  disabled={uploadMutation.isPending}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {uploadMutation.isPending ? 'Uploading…' : 'Attach File'}
                </button>
              </>
            )}
            {canComment && (
              <button
                type="button"
                className="btn btn-primary"
                disabled={!draft.trim() || createCommentMutation.isPending}
                onClick={() => createCommentMutation.mutate(draft.trim())}
              >
                {createCommentMutation.isPending ? 'Posting…' : 'Post Comment'}
              </button>
            )}
          </div>

          {uploadMutation.isError && (
            <p className="error text-sm" style={{ margin: '0.5rem 0 0' }}>
              {(uploadMutation.error as Error).message || 'Upload failed.'}
            </p>
          )}
        </div>
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete attachment"
        message={
          pendingDelete
            ? `Are you sure you want to permanently delete "${pendingDelete.label}"? This action cannot be undone.`
            : ''
        }
        onConfirm={() => {
          if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
        }}
        onCancel={() => setPendingDelete(null)}
        isPending={deleteMutation.isPending}
      />
    </ExpandableDetailSection>
  );
}
