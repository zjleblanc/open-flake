import { isValidElement, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { YamlHighlight } from './YamlHighlight';

type MarkdownRendererProps = {
  content: string;
  className?: string;
};

function extractCodeString(node: ReactNode): string {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(extractCodeString).join('');
  if (isValidElement(node)) {
    const props = node.props as { children?: ReactNode };
    return extractCodeString(props.children);
  }
  return '';
}

/**
 * Overrides fenced-code-block rendering so ```yaml blocks get lightweight syntax
 * highlighting via `YamlHighlight`. Any other language (or inline code, which never
 * hits `pre`) falls through to the default markup, preserved by `.markdown-body pre`.
 */
const components: Components = {
  pre({ children }) {
    const codeElement = Array.isArray(children) ? children[0] : children;
    if (isValidElement(codeElement)) {
      const codeProps = codeElement.props as { className?: string; children?: ReactNode };
      const languageMatch = /language-(\w+)/.exec(codeProps.className ?? '');
      if (languageMatch?.[1] === 'yaml') {
        const code = extractCodeString(codeProps.children).replace(/\n$/, '');
        return <YamlHighlight code={code} />;
      }
    }
    return <pre>{children}</pre>;
  },
};

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  return (
    <div className={`markdown-body ${className}`.trim()}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content || ''}
      </ReactMarkdown>
    </div>
  );
}
