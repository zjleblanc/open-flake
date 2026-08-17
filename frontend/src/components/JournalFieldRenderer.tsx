import { Fragment, useMemo } from 'react';
import DOMPurify from 'dompurify';

interface JournalFieldRendererProps {
  content: string;
  className?: string;
}

type JournalSegment = { kind: 'text'; value: string } | { kind: 'html'; value: string };

const CODE_BLOCK_PATTERN = /\[code\]([\s\S]*?)\[\/code\]/gi;

/**
 * Splits ServiceNow-style journal text (`work_notes`, `comments`, `close_notes`)
 * into plain-text and `[code]...[/code]` segments. Content inside `[code]` blocks
 * is treated as raw HTML (ServiceNow's journal formatting convention); everything
 * else is rendered as plain text with newlines preserved.
 */
function splitJournalContent(content: string): JournalSegment[] {
  const segments: JournalSegment[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  CODE_BLOCK_PATTERN.lastIndex = 0;
  while ((match = CODE_BLOCK_PATTERN.exec(content)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ kind: 'text', value: content.slice(lastIndex, match.index) });
    }
    segments.push({ kind: 'html', value: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    segments.push({ kind: 'text', value: content.slice(lastIndex) });
  }
  return segments;
}

export function JournalFieldRenderer({ content, className }: JournalFieldRendererProps) {
  const segments = useMemo(() => splitJournalContent(content || ''), [content]);

  if (segments.length === 0) {
    return <span className="text-muted">—</span>;
  }

  return (
    <div className={`journal-field-content${className ? ` ${className}` : ''}`}>
      {segments.map((segment, index) => (
        <Fragment key={index}>
          {segment.kind === 'html' ? (
            <div
              className="journal-field-html"
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(segment.value) }}
            />
          ) : (
            <span className="journal-field-text">{segment.value}</span>
          )}
        </Fragment>
      ))}
    </div>
  );
}
