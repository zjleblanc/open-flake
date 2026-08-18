export interface AttachmentRecord {
  sys_id: string;
  file_name: string;
  content_type: string;
  size_bytes: string;
  sys_created_on: string;
  sys_created_by?: string;
}

export type PreviewKind = 'image' | 'pdf' | 'text' | 'audio' | 'video' | 'none';

export function getPreviewKind(contentType: string): PreviewKind {
  const type = contentType.toLowerCase();
  if (type.startsWith('image/')) return 'image';
  if (type === 'application/pdf') return 'pdf';
  if (type.startsWith('text/')) return 'text';
  if (type.startsWith('audio/')) return 'audio';
  if (type.startsWith('video/')) return 'video';
  return 'none';
}

export function formatFileSize(sizeBytes: string | number): string {
  const bytes = typeof sizeBytes === 'string' ? Number(sizeBytes) : sizeBytes;
  if (!Number.isFinite(bytes) || bytes < 0) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
