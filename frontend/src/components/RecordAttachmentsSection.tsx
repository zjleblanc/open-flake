import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import {
  formatFileSize,
  getPreviewKind,
  type AttachmentRecord,
  type PreviewKind,
} from "../utils/attachmentUtils";
import { AttachmentsIcon } from "./DetailIcons";
import { DetailSection } from "./DetailSection";

interface RecordAttachmentsSectionProps {
  resource: string;
  sysId: string;
  canManageAttachments: boolean;
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

        if (previewKind === "text") {
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

  if (previewKind === "text") {
    if (textContent === null) {
      return <p className="text-muted text-sm">Loading preview…</p>;
    }
    return <pre className="attachment-text-preview">{textContent}</pre>;
  }

  if (!previewUrl) {
    return <p className="text-muted text-sm">Loading preview…</p>;
  }

  if (previewKind === "image") {
    return (
      <img
        src={previewUrl}
        alt={attachment.file_name}
        className="attachment-image-preview"
        loading="lazy"
      />
    );
  }

  if (previewKind === "pdf") {
    return <iframe src={previewUrl} title={attachment.file_name} className="attachment-pdf-preview" />;
  }

  if (previewKind === "audio") {
    return <audio controls src={previewUrl} className="attachment-media-preview" />;
  }

  if (previewKind === "video") {
    return <video controls src={previewUrl} className="attachment-media-preview" />;
  }

  return null;
}

export function RecordAttachmentsSection({
  resource,
  sysId,
  canManageAttachments,
}: RecordAttachmentsSectionProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [expandedPreviewId, setExpandedPreviewId] = useState<string | null>(null);

  const { data: attachments = [], isLoading } = useQuery({
    queryKey: ["attachments", resource, sysId],
    queryFn: () => api.listAttachments(resource, sysId),
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAttachment(resource, sysId, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["attachments", resource, sysId] });
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (attachmentSysId: string) =>
      api.deleteAttachment(resource, sysId, attachmentSysId),
    onSuccess: (_data, attachmentSysId) => {
      queryClient.invalidateQueries({ queryKey: ["attachments", resource, sysId] });
      if (expandedPreviewId === attachmentSysId) {
        setExpandedPreviewId(null);
      }
    },
  });

  const handleDelete = (attachment: AttachmentRecord) => {
    const confirmed = window.confirm(`Delete "${attachment.file_name}"?`);
    if (!confirmed) return;
    deleteMutation.mutate(attachment.sys_id);
  };

  const countLabel = isLoading ? "…" : String(attachments.length);

  return (
    <DetailSection
      title="Attachments"
      icon={<AttachmentsIcon />}
      accent="info"
      style={{ marginTop: "1rem" }}
      headerActions={<span className="attachment-count-badge">{countLabel}</span>}
    >
      {isLoading && <p className="text-muted text-sm">Loading attachments…</p>}
      {!isLoading && attachments.length === 0 && (
        <p className="text-muted text-sm">No attachments yet.</p>
      )}

      <ul className="attachment-list">
        {attachments.map((attachment) => {
          const previewKind = getPreviewKind(attachment.content_type);
          const isPreviewable = previewKind !== "none";
          const isExpanded = expandedPreviewId === attachment.sys_id;

          return (
            <li key={attachment.sys_id} className="attachment-item">
              <div className="attachment-item-header">
                <div className="attachment-item-meta">
                  <span className="attachment-file-name">{attachment.file_name}</span>
                  <span className="attachment-file-details text-muted text-sm">
                    {formatFileSize(attachment.size_bytes)}
                    {attachment.sys_created_on
                      ? ` · ${new Date(attachment.sys_created_on).toLocaleString()}`
                      : ""}
                  </span>
                </div>
                <div className="attachment-item-actions">
                  {isPreviewable && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() =>
                        setExpandedPreviewId(isExpanded ? null : attachment.sys_id)
                      }
                    >
                      {isExpanded ? "Hide Preview" : "Preview"}
                    </button>
                  )}
                  {canManageAttachments && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm attachment-delete-btn"
                      disabled={deleteMutation.isPending}
                      onClick={() => handleDelete(attachment)}
                    >
                      Delete
                    </button>
                  )}
                </div>
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
            </li>
          );
        })}
      </ul>

      {canManageAttachments && (
        <div className="attachment-upload-row">
          <input
            ref={fileInputRef}
            type="file"
            id={`attachment-upload-${sysId}`}
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
            className="btn btn-primary"
            disabled={uploadMutation.isPending}
            onClick={() => fileInputRef.current?.click()}
          >
            {uploadMutation.isPending ? "Uploading…" : "Upload File"}
          </button>
          {uploadMutation.isError && (
            <p className="error text-sm" style={{ margin: "0.5rem 0 0" }}>
              {(uploadMutation.error as Error).message || "Upload failed."}
            </p>
          )}
        </div>
      )}
    </DetailSection>
  );
}
